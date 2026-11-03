"""A change given to an epoch is the epoch's own (P17.8, decision 0065): logged
with its number before it is acted on, a part of its trajectory, and applied
again, once, when the epoch is carried on."""

from collections.abc import Iterable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import Action, Harvest, HarvestScope, Inspect, SetLevel
from greenhouse_protocol.plan import At, Plan, PlannedAction
from pydantic import JsonValue

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.playback import Epochs, Playback
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Kind, Status
from greenhouse_sim.services.scenarios import plant_ids, scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Stepped, execute, queued, resume

BOX: Final = "climate_box"
SHORT: Final = "climate_box_short"
DAYS: Final = 3
MINUTE_S: Final = 60.0
REFERENCE: Final = "reference_greenhouse"
REFERENCE_SHORT: Final = "reference_short"


def _simulator() -> Simulator:
    """The climate box cut to a run of three days; a new one is a process
    started again, which keeps none of what the one before worked out."""
    made = Simulator()
    for name, cut in ((BOX, SHORT), (REFERENCE, REFERENCE_SHORT)):
        made.catalogue.register(
            SCENARIO_REGISTRY[name].model_copy(update=dict(greenhouse_id=cut, duration_days=DAYS))
        )
    return made


@pytest.fixture
def simulator() -> Iterator[Simulator]:
    with _simulator() as made:
        yield made


def _digests(epoch: EpochStore) -> list[str]:
    return [commit.digest for commit in epoch.commits()]


def _plan(
    epoch: EpochStore,
    simulator: Simulator,
    at_s: float,
    *,
    action: Action | None = None,
    plan_id: str = "levels",
    number: int | None = None,
) -> Plan:
    """A plan of one action for the run of `epoch` at `at_s`: the heater on."""
    start = run_start(simulator.catalogue, epoch.manifest().scenario_id)
    return Plan(
        plan_id=plan_id,
        run_id=epoch.run_id,
        epoch=epoch.epoch if number is None else number,
        revision=1,
        actions=(
            PlannedAction(
                action_id="on",
                action=SetLevel(device_id="heater", level=0.5) if action is None else action,
                timing=At(at=start + timedelta(seconds=at_s)),
                proposed_by=LOCAL_OPERATOR,
            ),
        ),
    )


def _given(plan: Plan) -> dict[str, JsonValue]:
    return {"kind": "plan", "plan": plan.model_dump(mode="json")}


def _barriers(
    epoch: EpochStore, simulator: Simulator, *, day: int = 1, last: int = DAYS
) -> Iterable[float]:
    """The ends of a run's days to `last`, a change asked on its day `day`,
    before the worker looks: a running epoch given a change at a known moment."""
    for each in range(last):
        if each == day:
            epoch.ask(_given(_plan(epoch, simulator, day * DAY_S + MINUTE_S)))
        yield (each + 1) * DAY_S


def _worked_with_change(root: Path, simulator: Simulator) -> EpochStore:
    epoch = queued(simulator, FolderStore(root), SHORT)
    assert execute(simulator, epoch, Stepped(_barriers(epoch, simulator))) == Status.FINISHED
    return epoch


@pytest.fixture(scope="module")
def steered(tmp_path_factory: pytest.TempPathFactory) -> EpochStore:
    """An epoch given a level on its second day, never interrupted, to end."""
    with _simulator() as made:
        return _worked_with_change(tmp_path_factory.mktemp("steered"), made)


def test_a_change_asked_through_the_store_is_logged_and_named_by_the_next_commit(
    steered: EpochStore,
) -> None:
    (entry,) = steered.log()
    assert entry.seq == 0
    assert entry.given_s == DAY_S
    assert entry.at_s == DAY_S
    assert entry.by == f"person:{LOCAL_OPERATOR.id}"
    assert entry.what["kind"] == "plan"
    assert entry.request is not None
    # The commit whose span ends at the moment it was given does not name it;
    # the one whose records were worked out under it does.
    assert [commit.log_position for commit in steered.commits()] == [0, 1, 1]
    steered.verify()


def test_two_epochs_of_a_run_with_different_logs_have_different_trajectories(
    tmp_path: Path, simulator: Simulator, steered: EpochStore
) -> None:
    objects = FolderStore(tmp_path)
    other = queued(simulator, objects, SHORT)
    assert execute(simulator, other, Free()) == Status.FINISHED
    assert other.run_id == steered.run_id

    # The two hold the same path, the first epoch of the run, in stores of
    # their own: what differs is the change.
    assert (other.run_id, other.epoch) == (steered.run_id, steered.epoch)
    assert _digests(other)[0] == _digests(steered)[0]
    assert _digests(other)[1:] != _digests(steered)[1:]
    assert [o.value for o in other.observations().records] != [
        o.value for o in steered.observations().records
    ]


def test_what_a_day_recorded_before_the_change_is_the_same(
    tmp_path: Path, simulator: Simulator, steered: EpochStore
) -> None:
    other = queued(simulator, FolderStore(tmp_path), SHORT)
    assert execute(simulator, other, Free()) == Status.FINISHED
    until = steered.commits()[0].counts[Kind.OBSERVATIONS]
    assert other.observations(0, until).records == steered.observations(0, until).records


def test_a_change_is_logged_before_it_is_acted_on(tmp_path: Path, simulator: Simulator) -> None:
    """A log that cannot be written leaves the plan unchanged."""

    class NoLog(FolderStore):
        def put(self, name: str, data: bytes) -> None:
            if name.endswith("interventions.jsonl"):
                raise OSError("disk full")
            super().put(name, data)

    run = Playback(simulator, SHORT, epochs=Epochs(objects=NoLog(tmp_path)))
    assert run._store is not None
    with pytest.raises(OSError, match="disk full"):
        run.submit(_plan(run._store, simulator, MINUTE_S))
    assert run.state().commands == []


def test_a_refused_change_is_not_logged_and_is_answered(
    tmp_path: Path, simulator: Simulator
) -> None:
    epoch = queued(simulator, FolderStore(tmp_path), SHORT)
    # The climate box has no heating loop to set a target of.
    request = epoch.ask({"kind": "targets", "targets": {"heating_day": 21.0}})
    bad = epoch.ask({"kind": "no such kind"})
    assert execute(simulator, epoch, Free()) == Status.FINISHED

    assert epoch.logged() == []
    reasons = {answer.request: answer.reason for answer in epoch.answers()}
    assert reasons[request]
    assert reasons[bad].startswith("not a change")


def test_a_plan_refused_whole_is_logged_as_given_and_answered(
    tmp_path: Path, simulator: Simulator
) -> None:
    epoch = queued(simulator, FolderStore(tmp_path), SHORT)
    request = epoch.ask(_given(_plan(epoch, simulator, MINUTE_S, number=epoch.epoch + 7)))
    assert execute(simulator, epoch, Free()) == Status.FINISHED

    (entry,) = epoch.log()
    assert entry.request == request
    (answer,) = epoch.answers()
    assert answer.request == request
    assert "epoch" in answer.reason


def test_an_epoch_with_a_log_resumes_to_the_digests_of_one_never_interrupted(
    tmp_path: Path, steered: EpochStore
) -> None:
    # Stopped after its second day, whose change is in its log and its commit.
    with _simulator() as before:
        epoch = queued(before, FolderStore(tmp_path), SHORT)
        barriers = _barriers(epoch, before, last=2)
        assert execute(before, epoch, Stepped(barriers)) == Status.INTERRUPTED
    assert epoch.frontier_s() == 2 * DAY_S

    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    assert _digests(epoch) == _digests(steered)
    assert len(epoch.log()) == 1
    epoch.verify()


class Crash(BaseException):
    """The process dying: not an error any handler of the epoch's catches."""


class CrashingStore(FolderStore):
    """A folder store whose process dies as it writes the first object after
    the log whose name holds `pattern`, once."""

    def __init__(self, root: Path, pattern: str) -> None:
        super().__init__(root)
        self._pattern = pattern
        self.logged = False

    def put(self, name: str, data: bytes) -> None:
        if name.endswith("interventions.jsonl"):
            self.logged = True
        elif self.logged and self._pattern in name:
            self._pattern = "\0"
            raise Crash(name)
        super().put(name, data)


def test_a_crash_between_the_log_and_the_commit_applies_the_entry_once(
    tmp_path: Path, steered: EpochStore
) -> None:
    store = CrashingStore(tmp_path, "commits/")
    with _simulator() as before:
        epoch = queued(before, store, SHORT)
        with pytest.raises(Crash):
            execute(before, epoch, Stepped(_barriers(epoch, before)))
    # Logged, and named by no commit.
    assert epoch.frontier_s() == DAY_S
    assert epoch.log() == []
    assert len(epoch.logged()) == 1
    epoch.set_status(Status.INTERRUPTED)

    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    # The request is not taken twice, and the log is as if nothing had happened.
    assert len(epoch.logged()) == 1
    assert _digests(epoch) == _digests(steered)
    epoch.verify()


def test_a_crash_after_a_commit_that_names_the_entry_and_before_the_next_segment(
    tmp_path: Path, steered: EpochStore
) -> None:
    store = CrashingStore(tmp_path, "segments/")
    with _simulator() as before:
        epoch = queued(before, store, SHORT)
        with pytest.raises(Crash):
            execute(before, epoch, Stepped(_barriers(epoch, before)))
    epoch.set_status(Status.INTERRUPTED)

    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    assert len(epoch.logged()) == 1
    assert _digests(epoch) == _digests(steered)


def _played_with_change(root: Path, simulator: Simulator, *, until_s: float | None) -> EpochStore:
    """An epoch played by a clock the test moves, given a target in the middle
    of its second day; stopped at `until_s` if given, as a crash stops it."""
    now = [0.0]
    run = Playback(
        simulator,
        SHORT,
        seconds_per_day=DAY_S,
        clock=lambda: now[0],
        epochs=Epochs(objects=FolderStore(root)),
    )
    store = run._store
    assert store is not None
    store.set_status(Status.RUNNING)
    run.step_to(1.5 * DAY_S)
    run.keep()
    run.submit(_plan(store, simulator, 1.6 * DAY_S))
    if until_s is None:
        run.step_to(DAYS * DAY_S)
        run.keep()
    return store


def test_an_entry_past_the_last_commit_is_applied_at_the_moment_it_was_given(
    tmp_path: Path,
) -> None:
    with _simulator() as made:
        whole = _played_with_change(tmp_path / "whole", made, until_s=None)
    assert whole.manifest().status == Status.FINISHED

    with _simulator() as before:
        epoch = _played_with_change(tmp_path / "cut", before, until_s=1.5 * DAY_S)
    (entry,) = epoch.logged()
    assert entry.given_s == 1.5 * DAY_S
    assert epoch.frontier_s() == DAY_S
    epoch.set_status(Status.INTERRUPTED)

    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    assert len(epoch.logged()) == 1
    assert _digests(epoch) == _digests(whole)


def _reference_barriers(
    epoch: EpochStore, simulator: Simulator, *, last: int = DAYS
) -> Iterable[float]:
    """A target changed on the run's first day, and a harvest given for the
    start of its second: the kinds a heating loop and a crop take."""
    for each in range(last):
        if each == 0:
            epoch.ask({"kind": "targets", "targets": {"heating_day": 23.0}})
            epoch.ask(
                _given(
                    _plan(
                        epoch,
                        simulator,
                        DAY_S,
                        action=Harvest(plant_id=_plant(simulator), scope=HarvestScope.RIPE),
                        plan_id="crop",
                    )
                )
            )
        yield (each + 1) * DAY_S


def _plant(simulator: Simulator) -> str:
    return plant_ids(scenario(simulator.catalogue, REFERENCE_SHORT))[0]


def test_targets_and_crop_actions_are_applied_again_as_the_epoch_is_carried_on(
    tmp_path: Path,
) -> None:
    with _simulator() as made:
        whole = queued(made, FolderStore(tmp_path / "whole"), REFERENCE_SHORT)
        status = execute(made, whole, Stepped(_reference_barriers(whole, made)))
    assert status == Status.FINISHED
    assert [entry.what["kind"] for entry in whole.log()] == ["targets_changed", "plan"]
    (harvested,) = whole.outcomes().records[-1:]
    assert harvested.plan_id == "crop"
    assert harvested.effect is not None

    with _simulator() as before:
        cut = queued(before, FolderStore(tmp_path / "cut"), REFERENCE_SHORT)
        barriers = _reference_barriers(cut, before, last=2)
        assert execute(before, cut, Stepped(barriers)) == Status.INTERRUPTED
    # Its harvest is behind its last commit, and is not worked out again.
    assert cut.frontier_s() == 2 * DAY_S

    with _simulator() as after:
        assert resume(after, cut, Free()) == Status.FINISHED

    assert _digests(cut) == _digests(whole)
    assert cut.outcomes().records == whole.outcomes().records


def test_the_days_kept_are_not_worked_again_when_the_log_is_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, steered: EpochStore
) -> None:
    with _simulator() as before:
        epoch = queued(before, FolderStore(tmp_path), SHORT)
        barriers = _barriers(epoch, before, last=2)
        assert execute(before, epoch, Stepped(barriers)) == Status.INTERRUPTED
    worked: list[int] = []
    work_day = Playback._work_day

    def counted(self: Playback, day: int, *given: Any) -> bool:
        worked.append(day)
        return work_day(self, day, *given)

    monkeypatch.setattr(Playback, "_work_day", counted)
    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    # The change lies on a day committed, and only the day after it is worked.
    assert worked == [2]
    assert _digests(epoch) == _digests(steered)


def test_a_log_that_does_not_give_the_outcomes_kept_is_not_carried_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _simulator() as before:
        epoch = queued(before, FolderStore(tmp_path), SHORT)
        barriers = _barriers(epoch, before, day=0, last=2)
        assert execute(before, epoch, Stepped(barriers)) == Status.INTERRUPTED
    assert epoch.outcomes().records

    # As a build whose gateway answered otherwise would apply it.
    monkeypatch.setattr(Playback, "_apply", lambda _self, _entry: None)
    with _simulator() as after, pytest.raises(Conflict, match="does not give"):
        resume(after, epoch, Free())


def test_a_change_waits_for_those_logged_before_a_crash(tmp_path: Path) -> None:
    with _simulator() as before:
        epoch = _played_with_change(tmp_path, before, until_s=1.5 * DAY_S)
        request = epoch.ask(_given(_plan(epoch, before, 2.5 * DAY_S, plan_id="later")))
    epoch.set_status(Status.INTERRUPTED)

    with _simulator() as after:
        assert resume(after, epoch, Free()) == Status.FINISHED

    # In the order they were given, so that a commit's prefix of them is what
    # its span was worked out under.
    first, second = epoch.logged()
    assert (first.given_s, first.request) == (1.5 * DAY_S, None)
    assert second.request == request
    assert second.given_s >= first.given_s
    epoch.verify()


def _inspections(epoch: EpochStore, simulator: Simulator, *, last: int = DAYS) -> Iterable[float]:
    """Two plans, on the second day's start, each asking for the same action
    under the same identifier, due at once."""
    plant = _plant(simulator)
    for each in range(last):
        if each == 1:
            for plan_id in ("one", "two"):
                action = Inspect(plant_id=plant, reason="seen")
                plan = _plan(epoch, simulator, DAY_S, action=action, plan_id=plan_id)
                epoch.ask(_given(plan))
        yield (each + 1) * DAY_S


def test_crop_actions_due_as_they_are_given_are_told_apart_and_end_at_their_moment(
    tmp_path: Path,
) -> None:
    with _simulator() as made:
        whole = queued(made, FolderStore(tmp_path / "whole"), REFERENCE_SHORT)
        assert execute(made, whole, Stepped(_inspections(whole, made))) == Status.FINISHED
    one, two = whole.outcomes().records
    assert one.event_id != two.event_id
    assert one.resolved_at == two.resolved_at

    with _simulator() as before:
        cut = queued(before, FolderStore(tmp_path / "cut"), REFERENCE_SHORT)
        barriers = _inspections(cut, before, last=2)
        assert execute(before, cut, Stepped(barriers)) == Status.INTERRUPTED
    assert cut.frontier_s() == 2 * DAY_S

    with _simulator() as after:
        assert resume(after, cut, Free()) == Status.FINISHED

    assert cut.outcomes().records == whole.outcomes().records
    assert _digests(cut) == _digests(whole)
