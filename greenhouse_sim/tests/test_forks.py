"""A fork is a new epoch from a past instant of another (P17.8, decision 0065):
it names its parent and what it inherits, computes nothing before that
checkpoint, and leaves the epoch it came from served as it was. It starts through
the scheduler, and a rearranged layout is one."""

import json
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import Harvest, HarvestScope, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.plan import At, Plan, PlannedAction

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import forks, playback, runs_kept
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.interventions import LevelsAsked, TargetsAsked
from greenhouse_sim.services.playback import Playback
from greenhouse_sim.services.run_store import (
    EpochManifest,
    EpochStore,
    FolderStore,
    ForkOf,
    Kind,
    Status,
    StoreCorrupt,
    decompress,
    delete_epoch,
    instant_name,
)
from greenhouse_sim.services.scenarios import MOVES_MARK, plant_ids, scenario
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.stored_playback import Position, StoredEpoch
from greenhouse_sim.services.workers import Free, Stepped, execute, queued, resume

# A worker starts from nothing and imports what it is told to build its
# simulator with by name, so that the module is put where its process finds it.
sys.path.insert(0, str(Path(__file__).parent))

import short_runs
import workers_support

SHORT: Final = "climate_box_short"
TENDED: Final = "climate_box_tended"
DAYS: Final = 3
WAIT_S: Final = 180.0
MOVED: Final = f"default{MOVES_MARK}heater:0.5:0.0"


def _simulator(root: Path | None = None) -> Simulator:
    made = Simulator(runs=None if root is None else FolderStore(root))
    made.catalogue.register(short_runs.one_plant_box(SHORT, DAYS))
    return made


@pytest.fixture(scope="module")
def parent_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A store holding an epoch worked to its end, for tests that copy it."""
    return tmp_path_factory.mktemp("parent")


@pytest.fixture(scope="module")
def whole(parent_root: Path) -> EpochStore:
    """A finished epoch, of three days, given no change."""
    with _simulator() as made:
        epoch = queued(made, FolderStore(parent_root), SHORT)
        assert execute(made, epoch, Free()) == Status.FINISHED
        return epoch


@pytest.fixture
def simulator(parent_root: Path, whole: EpochStore) -> Iterator[Simulator]:
    with _simulator(parent_root) as made:
        yield made


def _worked(simulator: Simulator, made: EpochStore) -> Status:
    """A fork worked out here, as a worker takes it up."""
    return resume(simulator, made, Free())


def _objects_of(epoch: EpochStore) -> dict[str, bytes | None]:
    home = f"{epoch.run_id}/{epoch.epoch}/"
    return {name: epoch.objects.get(name) for name in epoch.objects.names(home)}


def test_a_fork_names_its_parent_the_instant_and_what_it_inherits(
    simulator: Simulator, whole: EpochStore
) -> None:
    moment = 1.5 * DAY_S
    made = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, moment)

    manifest = made.manifest()
    assert manifest.status == Status.QUEUED
    assert (made.run_id, made.epoch) == (whole.run_id, whole.epoch + 1)
    fork = manifest.fork
    assert fork is not None
    assert (fork.run_id, fork.epoch) == (whole.run_id, whole.epoch)
    assert fork.at_s == moment
    # The nearest checkpoint at or before it, with the parent's digest through it.
    assert fork.start_s == DAY_S
    assert fork.digest == whole.commits()[0].digest
    assert fork.inherited == 0
    assert made.frontier_s() == DAY_S
    assert made.commits() == []


def test_a_fork_computes_nothing_before_its_state_and_is_its_parent_until_it_changes(
    simulator: Simulator, whole: EpochStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    worked: list[int] = []
    work_day = Playback._work_day

    def counted(self: Playback, day: int, *given: Any) -> bool:
        worked.append(day)
        return work_day(self, day, *given)

    monkeypatch.setattr(Playback, "_work_day", counted)
    made = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, DAY_S)

    assert _worked(simulator, made) == Status.FINISHED

    assert worked == [1, 2]
    assert [c.start_s for c in made.commits()] == [DAY_S, 2 * DAY_S]
    assert made.manifest().status == Status.FINISHED
    # Nothing changed: the same records as the parent from that day.
    first = whole.commits()[0].counts[Kind.OBSERVATIONS]
    assert made.observations().records == whole.observations(first).records
    assert made.checkpoint_at(3 * DAY_S) is not None
    made.verify()


def test_a_forks_trajectory_goes_on_from_its_parents_and_differs_by_its_change(
    simulator: Simulator, whole: EpochStore
) -> None:
    plain = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, DAY_S)
    steered = forks.fork(
        simulator,
        whole.objects,
        whole.run_id,
        whole.epoch,
        DAY_S,
        changes=[LevelsAsked(levels={"heater": 0.5})],
    )
    _worked(simulator, plain)
    _worked(simulator, steered)

    assert steered.manifest().fork is not None
    assert [e.what["kind"] for e in steered.logged()] == ["plan"]
    assert steered.log()[0].given_s == DAY_S
    # What the change made differs from what the fork without it computed.
    a = [o.value for o in plain.observations().records]
    b = [o.value for o in steered.observations().records]
    assert a != b
    assert [c.digest for c in plain.commits()] != [c.digest for c in steered.commits()]
    steered.verify()
    outcome = steered.outcomes().records[0]
    assert outcome.run_id == steered.run_id
    assert outcome.epoch == steered.epoch


def _observed_by(epoch: EpochStore, until_s: float, start: Any) -> list[Observation]:
    limit = start + timedelta(seconds=until_s)
    return [o for o in epoch.observations().records if (o.delivered_at or o.timestamp) <= limit]


def test_a_fork_at_a_moment_inside_a_day_changes_nothing_before_it(
    simulator: Simulator, whole: EpochStore
) -> None:
    moment = 1.5 * DAY_S
    made = forks.fork(
        simulator,
        whole.objects,
        whole.run_id,
        whole.epoch,
        moment,
        changes=[LevelsAsked(levels={"heater": 0.5})],
    )
    assert _worked(simulator, made) == Status.FINISHED
    start = StoredEpoch(simulator, whole.objects, made.run_id, made.epoch).start

    before = _observed_by(made, moment, start)
    in_parent = {o.observation_id: o for o in _observed_by(whole, moment, start)}
    assert before
    assert [o.value for o in before] == [in_parent[o.observation_id].value for o in before]
    # And after it the heater's level has done something.
    parent = {o.observation_id: o.value for o in whole.observations().records}
    after = [o for o in made.observations().records if o not in before]
    assert any(o.value != parent[o.observation_id] for o in after)


def test_a_fork_inherits_the_changes_given_by_its_instant_and_not_those_after(
    tmp_path: Path,
) -> None:
    with _simulator(tmp_path) as made:
        epoch = queued(made, FolderStore(tmp_path), SHORT)

        def barriers() -> Iterator[float]:
            for day in range(DAYS):
                # One change a day: at each day's end the worker takes it.
                epoch.ask(LevelsAsked(levels={"heater": 0.1 * (day + 1)}).model_dump(mode="json"))
                yield (day + 1) * DAY_S

        assert execute(made, epoch, Stepped(barriers())) == Status.FINISHED
        assert [entry.given_s for entry in epoch.logged()] == [0.0, DAY_S, 2 * DAY_S]

        fork = forks.fork(made, epoch.objects, epoch.run_id, epoch.epoch, DAY_S)

        assert fork.manifest().fork is not None
        assert fork.manifest().fork.inherited == 2  # type: ignore[union-attr]
        inherited = fork.logged()
        assert [entry.given_s for entry in inherited] == [0.0, DAY_S]
        plans = [entry.what["plan"] for entry in inherited]
        assert {plan["epoch"] for plan in plans} == {fork.epoch}  # type: ignore[index,call-overload]
        assert _worked(made, fork) == Status.FINISHED
        # Its plan is the inherited changes: the third level was never given it.
        given = StoredEpoch(made, epoch.objects, fork.run_id, fork.epoch).plan().commanded()
        assert [level for _, _, level in given] == [0.1, 0.2]
        # Its outcomes are its own from where it started: the day before is its parent's.
        assert fork.outcomes().records == []
        fork.verify()


def test_a_fork_is_refused_outside_what_its_parent_holds(
    simulator: Simulator, whole: EpochStore
) -> None:
    fork = forks.fork
    with pytest.raises(InvalidRequest, match="branches between"):
        fork(simulator, whole.objects, whole.run_id, whole.epoch, DAYS * DAY_S + 1)
    with pytest.raises(Conflict, match="nothing to fork"):
        fork(simulator, whole.objects, whole.run_id, whole.epoch, DAYS * DAY_S)
    with pytest.raises(NotFound):
        fork(simulator, whole.objects, whole.run_id, 99, 0.0)
    with pytest.raises(NotFound):
        fork(simulator, whole.objects, "no-such-run", 0, 0.0)


def test_a_refused_change_refuses_the_fork_and_starts_nothing(
    simulator: Simulator, whole: EpochStore
) -> None:
    before = set(whole.objects.children(whole.run_id))
    with pytest.raises(InvalidRequest):
        # The climate box has no heating loop.
        forks.fork(
            simulator,
            whole.objects,
            whole.run_id,
            whole.epoch,
            DAY_S,
            changes=[TargetsAsked(targets={"heating_day": 21.0})],
        )
    assert set(whole.objects.children(whole.run_id)) == before


def test_a_layout_rearranged_as_a_fork_leaves_its_run_served(
    simulator: Simulator, whole: EpochStore
) -> None:
    before = _objects_of(whole)

    made = forks.fork(
        simulator, whole.objects, whole.run_id, whole.epoch, 1.5 * DAY_S, layout=MOVED
    )

    fork = made.manifest().fork
    assert fork is not None
    # Another layout is another run, and a run has one layout from its start: it
    # acts from the checkpoint, and says so.
    assert made.run_id != whole.run_id
    assert made.manifest().layout == MOVED
    assert fork.layout == MOVED
    assert (fork.at_s, fork.start_s) == (DAY_S, DAY_S)
    # The state it inherits is of the layout it goes on in, or no run takes it up.
    held = made.checkpoint_at(DAY_S)
    assert held is not None
    assert json.loads(decompress(held[0]))["layout"] == MOVED

    assert _worked(simulator, made) == Status.FINISHED

    assert [c.start_s for c in made.commits()] == [DAY_S, 2 * DAY_S]
    assert made.manifest().status == Status.FINISHED
    # The parent is as it was, and read as it was.
    assert _objects_of(whole) == before
    assert whole.manifest().status == Status.FINISHED
    position = Position(StoredEpoch(simulator, whole.objects, whole.run_id, whole.epoch), "p")
    assert position.seek(2.5 * DAY_S).time_s == 2.5 * DAY_S
    # And the fork is listed beside it.
    listed = scheduler_runs(simulator)
    assert {(whole.run_id, whole.epoch), (made.run_id, made.epoch)} <= listed


def scheduler_runs(simulator: Simulator) -> set[tuple[str, int]]:
    from greenhouse_sim.services.runs_kept import runs_of

    return {(run.run_id, run.epoch) for run in runs_of(simulator, SHORT)}


def test_a_fork_is_read_after_its_parent_is_deleted(tmp_path: Path) -> None:
    with _simulator(tmp_path) as made:
        epoch = queued(made, FolderStore(tmp_path), SHORT)
        assert execute(made, epoch, Stepped([DAY_S])) == Status.INTERRUPTED
        fork = forks.fork(made, epoch.objects, epoch.run_id, epoch.epoch, DAY_S)
        delete_epoch(epoch.objects, epoch.run_id, epoch.epoch)
        assert _worked(made, fork) == Status.FINISHED
        fork.verify()
        assert fork.manifest().fork is not None
        assert fork.frontier_s() == DAYS * DAY_S


class StoppingAfterACommit(FolderStore):
    """A store that tells its epoch's worker to stop once a commit is written."""

    def __init__(self, root: Path, stop: threading.Event) -> None:
        super().__init__(root)
        self._stop = stop

    def put(self, name: str, data: bytes) -> None:
        super().put(name, data)
        if "/commits/" in name:
            self._stop.set()


def test_a_fork_interrupted_resumes_to_the_digests_of_one_never_interrupted(
    tmp_path: Path,
) -> None:
    """A fork is carried on as any epoch is, from its own last commit."""
    objects = FolderStore(tmp_path)
    changes = [LevelsAsked(levels={"heater": 0.5})]
    with _simulator(tmp_path) as made:
        parent = queued(made, objects, SHORT)
        assert execute(made, parent, Stepped([DAY_S])) == Status.INTERRUPTED
        whole = forks.fork(made, objects, parent.run_id, parent.epoch, DAY_S, changes=changes)
        assert _worked(made, whole) == Status.FINISHED
        delete_epoch(objects, whole.run_id, whole.epoch)

    # In a store of its own, with the same parent, so that it has the same number.
    root = tmp_path / "again"
    again = FolderStore(root)
    stop = threading.Event()
    with _simulator(root) as made:
        parent = queued(made, again, SHORT)
        assert execute(made, parent, Stepped([DAY_S])) == Status.INTERRUPTED
        cut = forks.fork(made, again, parent.run_id, parent.epoch, DAY_S, changes=changes)
        straight = forks.fork(made, again, parent.run_id, parent.epoch, DAY_S, changes=changes)
        assert _worked(made, straight) == Status.FINISHED
        stopping = EpochStore(StoppingAfterACommit(root, stop), cut.run_id, cut.epoch)
        assert resume(made, stopping, Free(), stop=stop) == Status.INTERRUPTED
    assert len(cut.commits()) == 1
    with _simulator(root) as after:
        assert resume(after, cut, Free()) == Status.FINISHED

    assert len(cut.logged()) == 1
    # A digest names its objects by path: the two forks differ by their numbers,
    # and what they hold is the same.
    assert [(c.start_s, c.end_s, c.counts) for c in cut.commits()] == [
        (c.start_s, c.end_s, c.counts) for c in straight.commits()
    ]
    assert _values(cut) == _values(straight)
    assert cut.checkpoint_at(DAYS * DAY_S) == straight.checkpoint_at(DAYS * DAY_S)
    cut.verify()


def _values(epoch: EpochStore) -> list[float]:
    return [observation.value for observation in epoch.observations().records]


def test_a_position_over_a_fork_made_mid_day_opens_at_the_moment_it_was_made_from(
    simulator: Simulator, whole: EpochStore
) -> None:
    moment = 1.5 * DAY_S
    made = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, moment)
    fork = made.manifest().fork
    assert fork is not None
    assert (fork.start_s, fork.at_s) == (DAY_S, moment)
    epoch = StoredEpoch(simulator, whole.objects, made.run_id, made.epoch)
    opened_early = Position(epoch, "early")
    moved_early = Position(epoch, "moved")
    played_early = Position(epoch, "played")
    # Nothing past the day it begins with is computed yet.
    assert opened_early.state().time_s == DAY_S
    assert moved_early.seek(DAY_S).time_s == DAY_S
    assert played_early.play().time_s == DAY_S
    played_early.pause()

    _worked(simulator, made)

    # Once its moment is computed it is there, however early it was opened.
    assert opened_early.state().time_s == moment
    assert Position(epoch, "late").state().time_s == moment
    # One that was moved stays where it was moved to, and any move goes on from
    # the place it has.
    assert moved_early.state().time_s == DAY_S
    assert played_early.state().time_s == DAY_S
    assert opened_early.seek(DAY_S).time_s == DAY_S
    assert opened_early.state().time_s == DAY_S


def test_a_position_over_a_fork_stands_inside_what_it_holds(
    simulator: Simulator, whole: EpochStore
) -> None:
    made = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, DAY_S)
    _worked(simulator, made)
    position = Position(StoredEpoch(simulator, whole.objects, made.run_id, made.epoch), "p")

    state = position.state()
    assert state.start_s == DAY_S
    assert state.time_s == DAY_S
    assert state.fork is not None
    assert state.fork.epoch == whole.epoch
    with pytest.raises(InvalidRequest, match="between"):
        position.seek(DAY_S / 2)
    assert position.seek(1.5 * DAY_S).time_s == 1.5 * DAY_S
    # A seek restores the state it inherited.
    assert position.seek(DAY_S).time_s == DAY_S


def test_a_position_over_a_fork_says_whether_the_epoch_it_came_from_is_kept(
    simulator: Simulator, whole: EpochStore
) -> None:
    parent = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, DAY_S)
    assert _worked(simulator, parent) == Status.FINISHED
    made = forks.fork(simulator, whole.objects, parent.run_id, parent.epoch, 2 * DAY_S)
    assert _worked(simulator, made) == Status.FINISHED
    position = Position(StoredEpoch(simulator, whole.objects, made.run_id, made.epoch), "fork")
    no_fork = Position(StoredEpoch(simulator, whole.objects, whole.run_id, whole.epoch), "whole")
    assert no_fork.state().parent_kept is False
    assert position.state().parent_kept is True

    runs_kept.delete_epoch(simulator, parent.run_id, parent.epoch)

    assert position.state().parent_kept is False
    assert position.state().fork is not None


def test_a_stored_run_says_it_is_a_fork(simulator: Simulator, whole: EpochStore) -> None:
    made = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, DAY_S)
    listed = {
        (run["run_id"], run["epoch"]): run
        for run in respond_list(simulator, f"/api/scenarios/{SHORT}/runs")
    }
    assert listed[(made.run_id, made.epoch)]["fork"]["epoch"] == whole.epoch
    assert listed[(made.run_id, made.epoch)]["frontier_s"] == DAY_S
    assert listed[(whole.run_id, whole.epoch)]["fork"] is None


def respond_list(simulator: Simulator, path: str) -> list[Any]:
    answer = respond(simulator, "GET", path)
    assert answer.status == HTTPStatus.OK
    assert isinstance(answer.body, list)
    return answer.body


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        time.sleep(0.05)


def test_a_fork_starts_through_the_scheduler_in_a_process_of_its_own(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        made.runs = objects
        made.scheduler = Scheduler(made, tmp_path, limit=1)
        parent = queued(made, objects, workers_support.SHORT)
        assert execute(made, parent, Free()) == Status.FINISHED

        answer = respond(
            made,
            "POST",
            f"/api/runs/{parent.run_id}/epochs/{parent.epoch}/forks?t={DAY_S}",
            b'[{"kind": "levels", "levels": {"heater": 0.5}}]',
        )

        assert answer.status == HTTPStatus.OK
        assert isinstance(answer.body, dict)
        body: dict[str, Any] = answer.body
        assert body["fork"]["epoch"] == parent.epoch
        kept = EpochStore(objects, parent.run_id, body["epoch"])
        _until(lambda: kept.manifest().status == Status.FINISHED, "the fork to finish")
    assert kept.frontier_s() == workers_support.SHORT_DAYS * DAY_S
    assert len(kept.log()) == 1
    assert len(kept.commits()) == workers_support.SHORT_DAYS - 1
    kept.verify()


@pytest.mark.parametrize(
    ("path", "body", "status"),
    [
        ("forks", b"", HTTPStatus.BAD_REQUEST),  # no instant
        ("forks?t=0&layout=no_such_layout", b"", HTTPStatus.NOT_FOUND),
        ("forks?t=0", b"not json", HTTPStatus.BAD_REQUEST),
        ("forks?t=0", b'[{"kind": "cancel", "keys": []}]', HTTPStatus.BAD_REQUEST),
    ],
)
def test_what_is_no_fork_is_refused_over_the_api(
    simulator: Simulator, whole: EpochStore, path: str, body: bytes, status: HTTPStatus
) -> None:
    before = set(whole.objects.children(whole.run_id))
    url = f"/api/runs/{whole.run_id}/epochs/{whole.epoch}/{path}"

    assert respond(simulator, "POST", url, body).status == status
    assert set(whole.objects.children(whole.run_id)) == before


def test_a_playback_rearranged_says_it_came_from_the_epoch_it_replaced(tmp_path: Path) -> None:
    """Starting a played run over with its equipment moved is a fork of the
    epoch it plays, at its start, which stays in the store."""
    with _simulator(tmp_path) as made:
        started = playback.start(made, SHORT, hold=True)
        moved = playback.command(made, SHORT, playback.PlaybackCommand.RESTART, layout=MOVED)
        kept = EpochStore(FolderStore(tmp_path), moved.run_id, moved.epoch)
        fork = kept.manifest().fork
        assert fork is not None
        assert (fork.run_id, fork.epoch) == (started.run_id, started.epoch)
        assert fork.at_s == 0.0
        assert fork.layout == MOVED
        assert EpochStore(FolderStore(tmp_path), started.run_id, started.epoch).manifest()


def test_a_fork_of_a_fork_inherits_as_far_back_as_its_parent_holds(
    simulator: Simulator, whole: EpochStore
) -> None:
    first = forks.fork(
        simulator,
        whole.objects,
        whole.run_id,
        whole.epoch,
        DAY_S,
        changes=[LevelsAsked(levels={"heater": 0.5})],
    )
    # Before its first commit, it has the state it inherited to give.
    early = forks.fork(simulator, whole.objects, first.run_id, first.epoch, DAY_S)
    assert early.manifest().fork.start_s == DAY_S  # type: ignore[union-attr]
    assert early.manifest().fork.digest == first.manifest().fork.digest  # type: ignore[union-attr]
    assert _worked(simulator, first) == Status.FINISHED

    second = forks.fork(simulator, whole.objects, first.run_id, first.epoch, 2 * DAY_S)

    fork = second.manifest().fork
    assert fork is not None
    assert (fork.start_s, fork.digest) == (2 * DAY_S, first.commits()[0].digest)
    # Its parent's change comes with it, and it holds nothing before its state.
    assert fork.inherited == 1
    assert _worked(simulator, second) == Status.FINISHED
    assert [c.start_s for c in second.commits()] == [2 * DAY_S]
    with pytest.raises(InvalidRequest, match="branches between"):
        forks.fork(simulator, whole.objects, second.run_id, second.epoch, DAY_S)
    second.verify()


def test_a_forks_trajectory_goes_on_from_the_digest_it_inherits(tmp_path: Path) -> None:
    held = {}
    for digest in ("one", "other", None):
        made = EpochStore(FolderStore(tmp_path / str(digest)), "run", 1)
        made.write_fork(
            EpochManifest(
                run_id="run",
                epoch=1,
                scenario_id=SHORT,
                layout="default",
                fork=ForkOf(run_id="run", epoch=0, at_s=0.0, start_s=0.0, digest=digest),
            ),
            state=None,
            log=[],
            outcomes=[],
        )
        held[digest] = made.commit(0.0, DAY_S).digest
        made.verify()

    assert len(set(held.values())) == 3


def test_a_state_inherited_that_is_not_what_it_says_is_refused(
    simulator: Simulator, whole: EpochStore
) -> None:
    made = forks.fork(simulator, whole.objects, whole.run_id, whole.epoch, DAY_S)
    fork = made.manifest().fork
    assert fork is not None
    name = f"{made.run_id}/{made.epoch}/checkpoints/{instant_name(fork.start_s)}.json.zst"
    made.objects.put(name, b"not what it was")

    with pytest.raises(StoreCorrupt, match="inherited"):
        _worked(simulator, made)


def test_what_a_fork_inherits_is_kept_after_a_discard(simulator: Simulator, tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    parent = queued(simulator, objects, SHORT)
    assert execute(simulator, parent, Stepped([DAY_S, 2 * DAY_S])) == Status.INTERRUPTED
    made = forks.fork(simulator, objects, parent.run_id, parent.epoch, DAY_S)
    held = _objects_of(made)

    assert made.discard_uncommitted() == []

    assert _objects_of(made) == held
    assert made.checkpoint_at(DAY_S) is not None


def test_a_fork_is_told_what_its_parents_crop_actions_before_its_state_did(tmp_path: Path) -> None:
    """A harvest behind the state a fork inherits is not worked out again: what
    its parent's outcome says of it comes with the fork, and it needs its parent
    no longer."""
    objects = FolderStore(tmp_path)
    with Simulator(runs=objects) as made:
        made.catalogue.register(short_runs.tended_box(TENDED, DAYS))
        parent = queued(made, objects, TENDED)
        plant = plant_ids(scenario(made.catalogue, TENDED))[0]
        start = run_start(made.catalogue, TENDED)
        harvest = Plan(
            plan_id="crop",
            run_id=parent.run_id,
            epoch=parent.epoch,
            revision=1,
            actions=(
                PlannedAction(
                    action_id="pick",
                    action=Harvest(plant_id=plant, scope=HarvestScope.RIPE),
                    timing=At(at=start + timedelta(seconds=DAY_S)),
                    proposed_by=LOCAL_OPERATOR,
                ),
            ),
        )
        parent.ask({"kind": "plan", "plan": harvest.model_dump(mode="json")})
        assert execute(made, parent, Stepped([DAY_S, 2 * DAY_S])) == Status.INTERRUPTED
        assert parent.outcomes().records

        fork = forks.fork(made, objects, parent.run_id, parent.epoch, 2 * DAY_S)
        delete_epoch(objects, parent.run_id, parent.epoch)
        assert _worked(made, fork) == Status.FINISHED

    # Its outcome is its parent's, before the fork begins.
    assert fork.outcomes().records == []
    assert [c.start_s for c in fork.commits()] == [2 * DAY_S]


def test_a_fork_asks_of_the_server_what_a_worker_would_not_refuse(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with _simulator(tmp_path) as made:
        parent = queued(made, objects, SHORT)
        assert execute(made, parent, Stepped([DAY_S])) == Status.INTERRUPTED
        before = set(objects.children(parent.run_id))
        made.authorisation = AuthorisationConfig(version=1, groups=())

        with pytest.raises(InvalidRequest, match="may not set heater"):
            forks.fork(
                made,
                objects,
                parent.run_id,
                parent.epoch,
                DAY_S,
                changes=[LevelsAsked(levels={"heater": 0.5})],
            )
        assert set(objects.children(parent.run_id)) == before


def test_a_plan_its_parent_refused_as_another_epochs_is_not_given_by_its_fork(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    with _simulator(tmp_path) as made:
        parent = queued(made, objects, SHORT)
        start = run_start(made.catalogue, SHORT)
        fork_number = parent.epoch + 1

        def stale(plan_id: str, *, run_id: str, epoch: int) -> Plan:
            return Plan(
                plan_id=plan_id,
                run_id=run_id,
                epoch=epoch,
                revision=1,
                actions=(
                    PlannedAction(
                        action_id="on",
                        action=SetLevel(device_id="heater", level=0.5),
                        timing=At(at=start + timedelta(seconds=DAY_S)),
                        proposed_by=LOCAL_OPERATOR,
                    ),
                ),
            )

        # One names the epoch the fork will have; the other another run, in the
        # parent's own: both are refused as they are given.
        for plan in (
            stale("next", run_id=parent.run_id, epoch=fork_number),
            stale("other", run_id="another-run", epoch=parent.epoch),
        ):
            parent.ask({"kind": "plan", "plan": plan.model_dump(mode="json")})
        assert execute(made, parent, Stepped([DAY_S])) == Status.INTERRUPTED
        assert len(parent.logged()) == 2
        assert len(parent.answers()) == 2

        fork = forks.fork(made, objects, parent.run_id, parent.epoch, DAY_S)

        assert fork.epoch == fork_number
        assert fork.logged() == []
        assert fork.manifest().fork.inherited == 0  # type: ignore[union-attr]
        assert _worked(made, fork) == Status.FINISHED
        assert fork.outcomes().records == []


def test_a_playback_at_another_seed_is_another_run_and_no_fork(tmp_path: Path) -> None:
    with _simulator(tmp_path) as made:
        playback.start(made, SHORT, hold=True)
        other = playback.start(made, SHORT, hold=True, seed=7)
        kept = EpochStore(FolderStore(tmp_path), other.run_id, other.epoch)
        assert kept.manifest().seed == 7
        assert kept.manifest().fork is None
