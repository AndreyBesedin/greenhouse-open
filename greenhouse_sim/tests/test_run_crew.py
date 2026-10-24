"""A run's crew (P13.6, decision 0046): so many hands, each crop action
holding one for as long as its kind takes, so that a plan's actions are on
time, late, missed, carried out by their fallbacks or cancelled with what
they wait for, the same way run after run; and the run saying when it
carries each kind out, so that its gateway starts every action then."""

from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Final

import pytest
from greenhouse_protocol.actions import (
    Action,
    ActionKind,
    Harvest,
    HarvestScope,
    Inspect,
    Lower,
    RemoveLeaf,
    SetLevel,
)
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.contracts.execution import check_executor
from greenhouse_protocol.contracts.gateway import check_gateway
from greenhouse_protocol.contracts.memory_gateway import InMemoryGateway
from greenhouse_protocol.outcome import (
    ActionEffect,
    Harvested,
    Inspected,
    LeafRemoved,
    Lowered,
    OutcomeStatus,
)
from greenhouse_protocol.plan import (
    Asap,
    At,
    ExecutorKind,
    ExecutorRef,
    Lateness,
    OnLate,
    Plan,
    PlannedAction,
)

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services import playback
from greenhouse_sim.services.gateway import (
    LOCAL_AUTHORISATION,
    LOCAL_OPERATOR,
    NO_CREW,
    UNLIMITED,
    Carried,
    Crew,
    RunExecutor,
    run_items,
    run_kinds,
    run_unhonoured,
)
from greenhouse_sim.services.playback import Epochs, Playback, PlaybackCommand
from greenhouse_sim.services.scenarios import plant_ids, scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "reference_greenhouse"
CONFIG: Final = scenario(PACKAGED, SCENARIO)
START: Final = run_start(PACKAGED, SCENARIO)
DAY: Final = timedelta(days=1)
HOUR: Final = timedelta(hours=1)
MINUTE: Final = timedelta(minutes=1)
PLANTS: Final = plant_ids(CONFIG)
DEVICE: Final = sorted(run_items(CONFIG).devices)[0]
# One hand: a harvest takes it an hour, an inspection ten minutes.
ONE_HAND: Final = Crew(hands=1, durations_s={ActionKind.HARVEST: 3600.0, ActionKind.INSPECT: 600.0})


def _executor(crew: Crew = NO_CREW, start: datetime = START) -> RunExecutor:
    return RunExecutor(
        start,
        CONFIG.run_length_s(),
        kinds=run_kinds(CONFIG),
        unhonoured=run_unhonoured(CONFIG),
        crew=crew,
    )


def _gateway(
    authorisation: AuthorisationConfig, start: datetime, crew: Crew = NO_CREW
) -> InMemoryGateway:
    return InMemoryGateway(
        authorisation,
        start,
        executor=_executor(crew, start),
        executor_ref=ExecutorRef(kind=ExecutorKind.SIMULATED_RUN, id="run"),
        items=run_items(CONFIG),
    )


def _planned(action_id: str, action: Action, at: datetime, **fields: Any) -> PlannedAction:
    return PlannedAction.model_validate(
        dict(action_id=action_id, action=action, timing=At(at=at), proposed_by=LOCAL_OPERATOR)
        | fields
    )


def _ripe(plant: int) -> Harvest:
    return Harvest(plant_id=PLANTS[plant], scope=HarvestScope.RIPE)


def _look(plant: int) -> Inspect:
    return Inspect(plant_id=PLANTS[plant], reason="spots on its lowest leaves")


# A plan given before the run's second day, for one hand: a harvest on
# time; another run late, on the third day; an inspection skipped; one
# carried out by its fallback, a level; and a critical harvest, the leaf
# removal waiting for it cancelled though it would proceed.
CREW_PLAN: Final = (
    _planned("ripe", _ripe(0), START + DAY),
    _planned("again", _ripe(1), START + DAY),
    _planned("look", _look(2), START + DAY, lateness=Lateness(on_late=OnLate.SKIP)),
    _planned(
        "check",
        _look(3),
        START + DAY,
        lateness=Lateness(on_late=OnLate.FALLBACK, fallback=SetLevel(device_id=DEVICE, level=0.0)),
    ),
    _planned("pick", _ripe(4), START + DAY, lateness=Lateness(on_late=OnLate.CRITICAL)),
    PlannedAction(
        action_id="prune",
        action=RemoveLeaf(plant_id=PLANTS[4], leaf_id=f"{PLANTS[4]}_n01_leaf"),
        timing=Asap(),
        after=("pick",),
        if_prerequisite_fails="proceed",
        proposed_by=LOCAL_OPERATOR,
    ),
)
# What each of them ends in: its status, when it started and when it
# finished, as seconds from the run's start.
CREW_ENDS: Final = {
    "ripe": (OutcomeStatus.EXECUTED, DAY_S, DAY_S + 3600),
    "again": (OutcomeStatus.LATE, 2 * DAY_S, 2 * DAY_S + 3600),
    "look": (OutcomeStatus.MISSED, None, None),
    "check": (OutcomeStatus.MISSED, None, None),
    "check/fallback": (OutcomeStatus.EXECUTED, DAY_S, DAY_S),
    "pick": (OutcomeStatus.MISSED, None, None),
    "prune": (OutcomeStatus.CANCELLED, None, None),
}


def _effect(action: Action) -> ActionEffect:
    match action:
        case Harvest():
            return Harvested(fruit_count=0, fresh_mass_g=0.0)
        case Lower():
            return Lowered(by_cm=0.0)
        case RemoveLeaf(leaf_id=leaf_id):
            return LeafRemoved(leaf_id=leaf_id)
        case _:
            return Inspected()


def _worked_out(executor: RunExecutor, day: int) -> None:
    """Its run's crop actions on `day` carried out, as a playback works the
    day out: each done, with its effect."""
    executor.carried_out(
        {
            assignment.assignment_id: Carried(effect=_effect(assignment.action))
            for assignment in executor.crop_actions_on(day)
        }
    )


def _played(gateway: InMemoryGateway, until: datetime, step: timedelta) -> None:
    """The gateway's clock moved to `until`, `step` at a time, each day its
    clock reaches worked out first, as a playback has it."""
    assert isinstance(gateway._executor, RunExecutor)
    at = gateway.now
    while at < until:
        at = min(at + step, until)
        for _ in range(3):
            # A day's actions, its late ones and fallbacks among them, are
            # worked out as they are given, the clock waiting there.
            _worked_out(gateway._executor, int(gateway._executor.seconds(at) // DAY_S))
            gateway.advance(at)


def _ends(
    gateway: InMemoryGateway,
) -> dict[str, tuple[OutcomeStatus, float | None, float | None]]:
    def seconds(instant: datetime | None) -> float | None:
        return None if instant is None else (instant - START).total_seconds()

    return {
        str(o.ref): (o.status, seconds(o.started_at), seconds(o.finished_at))
        for o in gateway.outcomes().outcomes
    }


def test_a_run_says_when_it_carries_out_each_kind() -> None:
    executor = _executor()
    end = START + timedelta(seconds=CONFIG.run_length_s())

    half_a_minute = START + timedelta(seconds=30)
    assert executor.earliest(ActionKind.SET_LEVEL, half_a_minute) == half_a_minute
    assert executor.earliest(ActionKind.SET_TARGET, START + MINUTE / 2) == START + MINUTE
    assert executor.earliest(ActionKind.HARVEST, START) == START + DAY
    assert executor.earliest(ActionKind.HARVEST, START + DAY) == START + DAY
    assert executor.earliest(ActionKind.LOWER, START + DAY + HOUR) == START + 2 * DAY
    assert executor.earliest(ActionKind.HARVEST, START + DAY + HOUR, START + DAY + 2 * HOUR) is None
    assert executor.earliest(ActionKind.INSPECT, end - HOUR) is None
    assert executor.earliest(ActionKind.SET_LEVEL, end + HOUR) is None
    assert executor.earliest(ActionKind.WATER, START) is None
    # A day's start its clock has passed is gone: its crop's work is done.
    executor.advance(START + DAY + HOUR)
    assert executor.earliest(ActionKind.HARVEST, START + DAY) == START + 2 * DAY


def test_a_crew_times_crop_work_only_and_holds_its_hands() -> None:
    executor = _executor(Crew(hands=2, durations_s={ActionKind.HARVEST: 3600.0}))

    assert (executor.capacity(), _executor().capacity()) == (2, UNLIMITED)
    assert executor.longest_duration_s(ActionKind.HARVEST) == 3600.0
    assert executor.longest_duration_s(ActionKind.SET_LEVEL) == 0.0
    with pytest.raises(ValueError, match="a crew times crop actions only, not set_level"):
        Crew(durations_s={ActionKind.SET_LEVEL: 10.0})
    with pytest.raises(ValueError, match="greater than 0"):
        Crew(hands=0)


def test_a_crop_action_ends_once_its_crews_time_for_it_has_passed() -> None:
    gateway = _gateway(LOCAL_AUTHORISATION, START, ONE_HAND)
    gateway.submit(
        Plan(
            plan_id="p",
            run_id=gateway.run_id,
            epoch=gateway.epoch,
            revision=1,
            actions=(
                _planned("ripe", _ripe(0), START + DAY),
                _planned("vent", SetLevel(device_id=DEVICE, level=1.0), START + DAY),
            ),
        ),
        by=LOCAL_OPERATOR,
    )
    _played(gateway, START + DAY + HOUR / 2, MINUTE)
    assert _ends(gateway) == {"vent": (OutcomeStatus.EXECUTED, DAY_S, DAY_S)}

    _played(gateway, START + DAY + HOUR, MINUTE)
    assert _ends(gateway)["ripe"] == (OutcomeStatus.EXECUTED, DAY_S, DAY_S + 3600)


def test_a_run_with_a_crew_keeps_the_executor_and_gateway_contracts() -> None:
    level = SetLevel(device_id=DEVICE, level=1.0)

    assert check_executor(partial(_executor, ONE_HAND), START, action=level) == []
    assert check_gateway(partial(_gateway, crew=ONE_HAND), START) == []


@pytest.mark.parametrize("step", [HOUR, MINUTE * 7, DAY])
def test_a_plan_for_one_hand_ends_on_time_late_missed_and_cancelled(step: timedelta) -> None:
    """The same outcomes, however the clock moves."""
    gateway = _gateway(LOCAL_AUTHORISATION, START, ONE_HAND)
    receipt = gateway.submit(
        Plan(
            plan_id="p", run_id=gateway.run_id, epoch=gateway.epoch, revision=1, actions=CREW_PLAN
        ),
        by=LOCAL_OPERATOR,
    )
    assert receipt.accepted and receipt.refused == ()
    _played(gateway, START + 3 * DAY, step)

    assert _ends(gateway) == CREW_ENDS


@pytest.mark.slow
def test_a_playback_with_a_crew_ends_a_plan_the_same_after_it_starts_over(
    tmp_path: Path,
) -> None:
    """On the reference greenhouse, for one hand: the plan's outcomes as
    the gateway alone gives them, and the same again once the playback
    starts over and is given it again."""
    clock = _Clock()
    with Simulator(crew=ONE_HAND) as simulator:
        playback.start(simulator, SCENARIO, 24.0, clock=clock, hold=True, epochs=Epochs(tmp_path))
        played = playback.playback(simulator, SCENARIO)
        ends = []
        for _ in range(2):
            state = played.state()
            receipt = played.submit(
                Plan(
                    plan_id="crop",
                    run_id=state.run_id,
                    epoch=state.epoch,
                    revision=1,
                    actions=CREW_PLAN,
                )
            )
            assert receipt.accepted and receipt.refused == ()
            ends.append(_played_through(played, clock))
            played.command(PlaybackCommand.RESTART)

    assert ends[0] == ends[1] == CREW_ENDS


def _played_through(
    played: Playback, clock: _Clock
) -> dict[str, tuple[OutcomeStatus, float | None, float | None]]:
    """Its run worked out and played through its first three days, each day
    worked out again as its plan changes; its crop plan's ends."""
    played.command(PlaybackCommand.PLAY)
    begun = clock.now
    for hours in range(1, 3 * 24 + 1):
        clock.now = begun + hours
        while played.state().worked_out_s <= played.state().time_s < 3 * DAY_S:
            assert played.work_day(int(played.state().worked_out_s // DAY_S))
    played.command(PlaybackCommand.PAUSE)

    def seconds(instant: datetime | None) -> float | None:
        return None if instant is None else (instant - played.start).total_seconds()

    return {
        str(o.ref): (o.status, seconds(o.started_at), seconds(o.finished_at))
        for o in played.plan("crop").outcomes
    }


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now
