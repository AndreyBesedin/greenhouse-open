"""P13's final scenario, what of it holds without a person looking
(`docs/roadmap/archive/p13-actions.md`): a plan on the reference greenhouse's playing
run carried out, late, on time and refused, given through its gateway as the
local operator and read from its logs by a cursor, as the protocol's documents
alone, and a principal who may set levels only, whose grant is withdrawn while
the run plays."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import ActionKind
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.contracts.consumer import FIRST_CURSOR
from greenhouse_protocol.contracts.gateway import PlanState, Receipt
from greenhouse_protocol.event import Event
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import ActionKey, ActionState, Plan, Principal, PrincipalKind

from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services.gateway import LOCAL_OPERATOR
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.scenarios import plant_ids, scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO: Final = "reference_greenhouse"
START: Final = run_start(PACKAGED, SCENARIO)
PLANT: Final = plant_ids(scenario(PACKAGED, SCENARIO))[29]
ME: Final = LOCAL_OPERATOR.model_dump(mode="json")
GROWER: Final = Principal(kind=PrincipalKind.PERSON, id="grower")
# Every record there is, in one read.
ALL: Final = 10**6
OPERATORS: Final = AuthorisationGroup(
    group_id="local_operators",
    principals=frozenset({LOCAL_OPERATOR}),
    grants=(Grant(kinds=frozenset(ActionKind)),),
)


def _authorisation(version: int, *grower: ActionKind) -> AuthorisationConfig:
    return AuthorisationConfig(
        version=version,
        groups=(
            OPERATORS,
            AuthorisationGroup(
                group_id="growers",
                principals=frozenset({GROWER}),
                grants=(Grant(kinds=frozenset(grower)),) if grower else (),
            ),
        ),
    )


class _Played:
    """A run played back and stepped by hand, given plans as the local
    operator and read by a cursor, each as the protocol's documents write it."""

    def __init__(self, simulator: Simulator, tmp_path: Path) -> None:
        self.simulator = simulator
        self.found: Playback = simulator.playbacks.made_once(
            SCENARIO, lambda _: Playback(simulator, SCENARIO, epochs=Epochs(tmp_path))
        )
        self.state = self.found.state()

    def to(self, hours: float) -> None:
        """Its clock moved on to `hours` into the run."""
        assert self.found.step_to(hours * HOUR_S).time_s == hours * HOUR_S

    def give(self, plan_id: str, *actions: dict[str, Any], revision: int = 1) -> Receipt:
        plan = {
            "plan_id": plan_id,
            "run_id": self.state.run_id,
            "epoch": self.found.state().epoch,
            "revision": revision,
            "actions": list(actions),
        }
        return self.found.submit(Plan.model_validate(plan), by=LOCAL_OPERATOR)

    def listed(self) -> list[ActionState]:
        return list(self.found.actions())

    def cancel(self, plan_id: str, *action_ids: str) -> Receipt:
        keys = [
            {
                "plan_id": plan_id,
                "epoch": self.found.state().epoch,
                "revision": 1,
                "ref": {"action_id": each},
            }
            for each in action_ids
        ]
        return self.found.cancel(
            tuple(ActionKey.model_validate(each) for each in keys), by=LOCAL_OPERATOR
        )

    def plan(self, plan_id: str) -> PlanState:
        return self.found.plan(plan_id)

    def outcomes(self) -> dict[str, ActionOutcome]:
        batch, _ = self.found.outcomes_after(FIRST_CURSOR, ALL)
        return {f"{each.plan_id}/{each.ref}": each for each in batch.outcomes}

    def events(self) -> tuple[Event, ...]:
        return self.found.events_after(FIRST_CURSOR, ALL).records


@pytest.fixture
def played(tmp_path: Path) -> Iterator[_Played]:
    with Simulator(authorisation=_authorisation(1, ActionKind.SET_LEVEL)) as simulator:
        yield _Played(simulator, tmp_path)


def _at(hours: float) -> dict[str, Any]:
    return {"kind": "at", "at": (START + timedelta(hours=hours)).isoformat()}


def _window(from_hours: float, to_hours: float) -> dict[str, Any]:
    return {
        "kind": "window",
        "not_before": (START + timedelta(hours=from_hours)).isoformat(),
        "not_after": (START + timedelta(hours=to_hours)).isoformat(),
    }


def _planned(action_id: str, action: dict[str, Any], timing: dict[str, Any], **more: Any) -> Any:
    return {
        "action_id": action_id,
        "action": action,
        "timing": timing,
        "proposed_by": ME,
        **more,
    }


def _level(device: str, level: float = 1.0) -> dict[str, Any]:
    return {"kind": "set_level", "device_id": device, "level": level}


ASAP: Final = {"kind": "asap"}
HARVEST_TRUSS: Final = {
    "kind": "harvest",
    "plant_id": PLANT,
    "scope": "truss",
    "organ_id": f"{PLANT}_t01",
}
LOWER: Final = {"kind": "lower", "plant_id": PLANT, "by_cm": 10.0}
WARM_DAY: Final = {"kind": "set_target", "target": "heating_day", "value_c": 22.0}


def _the_day_s_plan(day_hours: float = 0.0) -> tuple[dict[str, Any], ...]:
    return (
        _planned("warm_day", WARM_DAY, _at(day_hours + 8)),
        _planned("harvest", HARVEST_TRUSS, ASAP),
        _planned("lower", LOWER, ASAP, after=("harvest",)),
        _planned("open_vent", _level("roof_vent_1"), _window(day_hours + 11, day_hours + 11.5)),
    )


@pytest.mark.slow
def test_a_plan_is_carried_out_each_at_its_moment_and_read_by_a_consumer(played: _Played) -> None:
    """Steps 1 and 2: the target at 08:00, the vent as its window opens, the
    harvest and then the lowering at the next day's start, each with its
    effect; the harvest's event names its action."""
    assert played.give("qa", *_the_day_s_plan()).refused == ()

    played.to(8.5)
    done = played.outcomes()
    assert set(done) == {"qa/warm_day"}
    assert done["qa/warm_day"].status == OutcomeStatus.EXECUTED
    assert done["qa/warm_day"].resolved_at == START + timedelta(hours=8)

    played.to(11.5)
    opened = played.outcomes()["qa/open_vent"]
    assert (opened.status, opened.started_at) == (
        OutcomeStatus.EXECUTED,
        START + timedelta(hours=11),
    )

    played.to(24.5)
    done = played.outcomes()
    next_day = START + timedelta(hours=24)
    assert [done[f"qa/{each}"].started_at for each in ("harvest", "lower")] == [next_day, next_day]
    assert [done[f"qa/{each}"].status for each in ("harvest", "lower")] == [
        OutcomeStatus.EXECUTED,
        OutcomeStatus.EXECUTED,
    ]
    named = {event.event_id: event.parameters for event in played.events()}
    assert named[done["qa/harvest"].event_id or ""]["action"] == "harvest"
    assert named[done["qa/lower"].event_id or ""]["action"] == "lower"


@pytest.mark.slow
def test_what_comes_too_late_or_cannot_be_done_is_refused_saying_why(played: _Played) -> None:
    """Steps 3 and 4: at 10:05, a critical action due at 10:00 is missed and
    what waits for it cancelled; a harvest at 14:00 is refused when given."""
    played.to(10 + 5 / 60)

    late = played.give(
        "critical",
        _planned(
            "too_late",
            _level("door"),
            _at(10),
            lateness={"tolerance_s": 0, "on_late": "critical"},
        ),
        _planned("waits", _level("fan_left", 0.5), ASAP, after=("too_late",)),
    )
    refused = played.give(
        "at_14",
        _planned("harvest_at_14", {"kind": "harvest", "plant_id": PLANT, "scope": "ripe"}, _at(14)),
    )

    assert late.accepted and refused.accepted
    assert [str(each) for each in refused.refused] == ["harvest_at_14"]
    done = played.outcomes()
    assert (done["critical/too_late"].status, done["critical/too_late"].reason) == (
        OutcomeStatus.MISSED,
        "late",
    )
    assert done["critical/waits"].status == OutcomeStatus.CANCELLED
    assert "critical/too_late" in (done["critical/waits"].reason or "")
    assert done["at_14/harvest_at_14"].status == OutcomeStatus.REFUSED
    assert "at a day's start" in (done["at_14/harvest_at_14"].reason or "")


@pytest.mark.slow
def test_a_principal_may_do_what_it_is_granted_until_its_grant_is_withdrawn(
    played: _Played,
) -> None:
    """Steps 5 and 6: one who may set levels gives a harvest, refused when
    given; and an opening at 15:00, refused then, its grant withdrawn at
    14:30, the change's version and instant in the plan's state."""

    def plan(plan_id: str, *actions: dict[str, Any]) -> Plan:
        return Plan.model_validate(
            {
                "plan_id": plan_id,
                "run_id": played.state.run_id,
                "epoch": played.state.epoch,
                "revision": 1,
                "actions": [each | {"proposed_by": GROWER.model_dump()} for each in actions],
            }
        )

    harvest = played.found.submit(
        plan("harvest", _planned("harvest", HARVEST_TRUSS, ASAP)), by=GROWER
    )
    vent = played.found.submit(
        plan("vent", _planned("open", _level("roof_vent_3"), _at(15))), by=GROWER
    )

    assert [str(each) for each in harvest.refused] == ["harvest"]
    assert played.outcomes()["harvest/harvest"].reason == "grower is not authorised to harvest"
    assert vent.refused == ()

    played.to(14.5)
    played.simulator.authorise(_authorisation(2))
    withdrawn_at = played.found.state().simulated_now
    played.to(15.5)

    state = played.plan("vent")
    (refused,) = state.outcomes
    assert (refused.status, refused.reason, refused.resolved_at) == (
        OutcomeStatus.REFUSED,
        "grower is no longer authorised",
        START + timedelta(hours=15),
    )
    assert [(change.version, change.at) for change in state.authorisation] == [
        (1, START),
        (2, withdrawn_at),
    ]


@pytest.mark.slow
def test_a_revision_steers_the_playing_run_and_changes_nothing_delivered(played: _Played) -> None:
    """Step 7: a revision drops the window before it opens: superseded, in the
    same run and epoch, and what was delivered before it stays as it was."""
    played.give("steered", _planned("window", _level("roof_vent_2"), _window(16, 16.5)))
    played.to(15)
    before = played.found.state()
    delivered = played.found.records_after(0, 100_000).records

    receipt = played.give("steered", revision=2)

    after = played.found.state()
    assert receipt.accepted
    assert played.outcomes()["steered/window"].status == OutcomeStatus.SUPERSEDED
    assert (after.run_id, after.epoch) == (before.run_id, before.epoch)
    assert played.found.records_after(0, 100_000).records[: len(delivered)] == delivered


@pytest.mark.slow
def test_what_is_still_to_come_is_listed_and_chosen_actions_cancelled(played: _Played) -> None:
    """Step 9: each listed with its state, due instant, principal and what
    waits for it; two cancelled by key, one waited for and one not: those two
    name who cancelled them, the one that waited goes with its prerequisite,
    and nothing else changes."""
    played.give(
        "listed",
        _planned("first", _level("fan_right", 0.5), _at(33)),
        _planned("second", _level("fan_right", 0.2), _at(34), after=("first",)),
        _planned("third", _level("fan_left", 0.2), _at(35)),
        _planned("fourth", _level("fan_left", 0.4), _at(36)),
    )
    first, second, third, fourth = played.listed()
    assert [each.principal for each in (first, second, third, fourth)] == [LOCAL_OPERATOR] * 4
    assert first.due == START + timedelta(hours=33)
    assert [str(each) for each in first.waited_on_by] == ["second"]
    assert [str(each) for each in second.waiting_for] == ["first"]

    receipt = played.cancel("listed", "first", "third")

    assert [str(each) for each in receipt.cancelled] == ["first", "third"]
    assert [str(each.ref) for each in played.listed()] == ["fourth"]
    done = played.outcomes()
    for each in ("first", "third"):
        assert done[f"listed/{each}"].status == OutcomeStatus.CANCELLED
        assert done[f"listed/{each}"].cancelled_by == LOCAL_OPERATOR
    assert done["listed/second"].status == OutcomeStatus.CANCELLED
    assert "listed/first" in (done["listed/second"].reason or "")


@pytest.mark.slow
def test_a_run_started_over_drops_what_was_still_to_come(played: _Played) -> None:
    """Step 10's first half: a new epoch from its start, each action still to
    come cancelled because the run started over, and nothing given before it
    applies."""
    played.give("qa", *_the_day_s_plan())
    played.to(9)

    restarted = played.found.command(PlaybackCommand.RESTART)

    assert (restarted.epoch, restarted.time_s) == (played.state.epoch + 1, 0.0)
    assert (restarted.targets, restarted.commands, restarted.crop) == ([], [], [])
    assert played.listed() == []
    done = played.outcomes()
    assert sorted(done) == ["qa/harvest", "qa/lower", "qa/open_vent"]
    for each in done.values():
        assert (each.status, each.epoch) == (OutcomeStatus.CANCELLED, restarted.epoch)
        assert each.reason == "the run started over"


@pytest.mark.slow
def test_the_same_plan_through_the_routes_or_the_service_ends_the_same(tmp_path: Path) -> None:
    """Step 8: a client that has only the gateway's and the consumer's routes
    gives the same plan as the simulator's own service: the same outcomes."""

    def ended(through_routes: bool, folder: Path) -> list[tuple[Any, ...]]:
        with Simulator() as simulator:
            played = _Played(simulator, folder)
            if through_routes:
                assert played.give("qa", *_the_day_s_plan()).refused == ()
            else:
                plan = {
                    "plan_id": "qa",
                    "run_id": played.state.run_id,
                    "epoch": played.state.epoch,
                    "revision": 1,
                    "actions": list(_the_day_s_plan()),
                }
                assert played.found.submit(Plan.model_validate(plan)).refused == ()
            played.to(24.5)
            return [
                (
                    each.plan_id,
                    str(each.ref),
                    each.status,
                    each.started_at,
                    each.resolved_at,
                    each.effect,
                    each.event_id,
                )
                for each in played.outcomes().values()
            ]

    one = ended(through_routes=True, folder=tmp_path / "routes")
    other = ended(through_routes=False, folder=tmp_path / "service")

    assert len(one) == 4
    assert one == other
