"""A playback's run carrying out crop actions (P13.5, decision 0046): at the
start of a day after its first, given before its clock reaches it, each
refused otherwise in the run's own words; done once its day is worked out,
with what it did and the event it made, which its outcome names; watering
refused, since its organ crop has no water in its root zone."""

from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Final

import pytest
from greenhouse_protocol.actions import (
    Action,
    ActionKind,
    ActionRef,
    Harvest,
    HarvestScope,
    Inspect,
    Lower,
    RemoveLeaf,
    SetLevel,
    Water,
)
from greenhouse_protocol.assignment import Assignment, ReportStatus
from greenhouse_protocol.contracts.consumer import OutcomeBatch, check_polls
from greenhouse_protocol.contracts.execution import AssignmentStatus, check_executor
from greenhouse_protocol.enums import EventType
from greenhouse_protocol.outcome import (
    Harvested,
    Inspected,
    LeafRemoved,
    Lowered,
    OutcomeStatus,
)
from greenhouse_protocol.plan import At, Plan, PlannedAction

from greenhouse_sim.api.consumer import consumer_respond
from greenhouse_sim.biology.tomato.organ.actions import act, harvest_round
from greenhouse_sim.biology.tomato.organ.topology import HarvestFruit
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.organs import FruitStage
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services import plants, playback
from greenhouse_sim.services.crop_log import _harvest, crop_actions_done
from greenhouse_sim.services.gateway import (
    LOCAL_OPERATOR,
    NO_ROOT_ZONE,
    Carried,
    RunExecutor,
    run_items,
    run_kinds,
    run_unhonoured,
)
from greenhouse_sim.services.playback import Epochs, PlaybackCommand
from greenhouse_sim.services.runs import PlannedAt, RunPlan, RunRequest
from greenhouse_sim.services.scenarios import plant_ids, scenario
from greenhouse_sim.services.sensors import run_start
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "reference_greenhouse"
CONFIG: Final = scenario(PACKAGED, SCENARIO)
START: Final = run_start(PACKAGED, SCENARIO)
DAY: Final = timedelta(days=1)
HOUR: Final = timedelta(hours=1)
PLANT: Final = plant_ids(CONFIG)[0]
RIPE: Final = Harvest(plant_id=PLANT, scope=HarvestScope.RIPE)
LEAF: Final = RemoveLeaf(plant_id=PLANT, leaf_id=f"{PLANT}_n01_leaf")
LOWERING: Final = Lower(plant_id=PLANT, by_internodes=1)
LOOK: Final = Inspect(plant_id=PLANT, reason="spots on its lowest leaves")
HEATING: Final = SetLevel(device_id=sorted(run_items(CONFIG).devices)[0], level=1.0)
# Every record there is, in one batch.
ALL: Final = 10**6


def _executor(scenario_id: str = SCENARIO, start: datetime = START) -> RunExecutor:
    config = scenario(PACKAGED, scenario_id)
    return RunExecutor(
        start,
        config.run_length_s(),
        kinds=run_kinds(config),
        unhonoured=run_unhonoured(config),
    )


def _assigned(assignment_id: str, action: Action, at_s: float) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        run_id="run",
        ref=ActionRef(action_id=assignment_id),
        action=action,
        at=START + timedelta(seconds=at_s),
    )


def test_a_run_says_why_it_does_not_carry_out_what_it_refuses() -> None:
    executor = _executor()
    boxed = _executor("climate_box")

    assert executor.why_not(ActionKind.WATER) == NO_ROOT_ZONE
    assert executor.why_not(ActionKind.HARVEST, START + DAY) is None
    assert executor.honours(ActionKind.HARVEST, START + DAY)
    assert executor.why_not(ActionKind.HARVEST, START + DAY + HOUR) == (
        "the run's crop steps a day at a time: it carries out harvest at a day's start, "
        "not at 90000 s"
    )
    assert executor.why_not(ActionKind.LOWER, START) == (
        "the run's crop is planted at its start: its work begins with its second day"
    )
    assert boxed.why_not(ActionKind.HARVEST) == (
        "climate_box grows its crop with the simple daily model, which takes no harvest"
    )
    assert boxed.why_not(ActionKind.SET_TARGET) == (
        "climate_box has no heating loop to set a target of"
    )
    # A day's start the clock has reached has had its crop's work done.
    executor.advance(START + DAY)
    assert executor.why_not(ActionKind.HARVEST, START + DAY) == (
        "the run's clock has reached that day's start: its crop's work then is done"
    )
    for scenario_id in (SCENARIO, "climate_box"):
        level = SetLevel(
            device_id=sorted(run_items(scenario(PACKAGED, scenario_id)).devices)[0], level=1.0
        )
        assert check_executor(partial(_executor, scenario_id), START, action=level) == []


def test_a_crop_action_is_done_once_its_day_is_worked_out_with_what_it_did() -> None:
    executor = _executor()
    executor.perform(_assigned("ripe", RIPE, DAY_S))
    executor.perform(_assigned("look", LOOK, DAY_S))
    executor.perform(_assigned("heat", HEATING, DAY_S))
    executor.advance(START + DAY + HOUR)

    assert [report.assignment_id for report in executor.reports()] == ["heat"]
    assert executor.status("ripe") == AssignmentStatus.RECEIVED
    assert [each.assignment_id for each in executor.crop_actions_on(1)] == ["ripe", "look"]
    picked = Harvested(fruit_count=2, fresh_mass_g=150.0)
    executor.carried_out(
        {
            "ripe": Carried(effect=picked, event_id="picked"),
            "look": Carried(refusal="no one to look"),
        }
    )
    executor.advance(START + DAY + HOUR)

    ends = {report.assignment_id: report for report in executor.reports()}
    assert (ends["ripe"].status, ends["ripe"].effect, ends["ripe"].event_id) == (
        ReportStatus.DONE,
        picked,
        "picked",
    )
    assert (ends["look"].status, ends["look"].reason) == (ReportStatus.REFUSED, "no one to look")


def test_what_a_crop_action_did_is_worked_out_again_when_the_plan_changes_before_it() -> None:
    executor = _executor()
    executor.perform(_assigned("ripe", RIPE, 2 * DAY_S))
    executor.carried_out({"ripe": Carried(effect=Harvested(fruit_count=0, fresh_mass_g=0.0))})
    executor.perform(_assigned("leaf", LEAF, DAY_S))
    executor.advance(START + 2 * DAY + HOUR)

    assert executor.reports() == ()


def test_each_crop_action_done_is_an_event_of_its_own_naming_it(simulator: Simulator) -> None:
    """On the run's second day: every ripe fruit picked, of which there is
    none; the lowest leaf removed; the stem lowered by the internode it
    leaves bare; a look; and a leaf the plant has not, refused."""
    missing = RemoveLeaf(plant_id=PLANT, leaf_id=f"{PLANT}_n99_leaf")
    given: list[Action] = [RIPE, LEAF, LOWERING, LOOK, missing]
    run = RunRequest(
        SCENARIO, plan=RunPlan(actions=tuple(PlannedAt(at_s=DAY_S, action=a) for a in given))
    )
    assigned = [_assigned(f"e0-a{n}", action, DAY_S) for n, action in enumerate(given)]

    done = crop_actions_done(simulator, run, 1, START, assigned)

    effects = [each.carried.effect for each in done]
    assert effects[:2] == [
        Harvested(fruit_count=0, fresh_mass_g=0.0),
        LeafRemoved(leaf_id=LEAF.leaf_id),
    ]
    assert isinstance(effects[2], Lowered) and effects[2].by_cm > 0
    assert effects[3:] == [Inspected(), None]
    assert done[4].carried.refusal == f"{PLANT} has no leaf {missing.leaf_id}"
    events = [each.event for each in done]
    assert events[4] is None
    assert [event.event_type for event in events[:4] if event is not None] == [
        EventType.HARVEST,
        EventType.PRUNING,
        EventType.LOWERING,
        EventType.MANUAL_INSPECTION,
    ]
    for each, event in zip(done[:4], events[:4], strict=True):
        assert event is not None and event.event_id == each.carried.event_id
        assert event.parameters["action"] == each.assignment_id
        assert event.event_id.endswith(f"_{each.assignment_id}")
    assert events[3] is not None and events[3].parameters["reason"] == LOOK.reason


def test_a_day_s_harvest_event_counts_its_crop_work_alone() -> None:
    """The fruit a run's own harvest picks after the day's harvest round is
    its own event's, not the round's."""
    plant = plants.structure(plants.LabRun(day=85))
    worked = harvest_round(plant)
    unripe = next(
        flower.fruit.fruit_id
        for phytomer in worked.stem.phytomers
        if phytomer.truss is not None
        for flower in phytomer.truss.flowers
        if flower.fruit is not None and flower.fruit.stage == FruitStage.ATTACHED
    )
    after = act(worked, HarvestFruit(fruit_id=unripe))

    whole = _harvest(after, plant, START, "lab")
    round_only = _harvest(after, plant, START, "lab", len(worked.history))

    assert whole is not None and round_only is not None
    assert round_only.parameters["harvested_fruit_count"] == len(worked.history)
    assert whole.parameters["harvested_fruit_count"] == len(worked.history) + 1


@pytest.mark.slow
def test_crop_actions_given_to_a_playback_end_in_outcomes_naming_their_events(
    simulator: Simulator, tmp_path: Path
) -> None:
    clock = _Clock()
    started = playback.start(
        simulator, SCENARIO, 24.0, clock=clock, hold=True, epochs=Epochs(tmp_path)
    )
    played = playback.playback(simulator, SCENARIO)
    day_1 = START + DAY
    given: list[tuple[str, Action, object]] = [
        ("ripe", RIPE, day_1),
        ("leaf", LEAF, day_1),
        ("lower", LOWERING, day_1),
        ("look", LOOK, day_1),
        ("water", Water(plant_id=PLANT, amount_ml=100.0), day_1),
        ("noon", RIPE, day_1 + 12 * HOUR),
    ]
    receipt = played.submit(
        Plan(
            plan_id="crop",
            run_id=started.run_id,
            epoch=started.epoch,
            revision=1,
            actions=tuple(
                PlannedAction(action_id=key, action=a, timing=At(at=at), proposed_by=LOCAL_OPERATOR)
                for key, a, at in given
            ),
        )
    )

    assert receipt.accepted
    refused = {o.ref.action_id: o.reason for o in played.plan("crop").outcomes}
    assert refused == {
        "water": f"no executor carries out water: {NO_ROOT_ZONE}",
        "noon": f"no executor honours harvest at {(day_1 + 12 * HOUR).isoformat()}: the run's "
        "crop steps a day at a time: it carries out harvest at a day's start, not at 129600 s",
    }
    assert played.work_day(0) and played.work_day(1)
    played.command(PlaybackCommand.PLAY)
    clock.now = 25.0
    ends = {o.ref.action_id: o for o in played.plan("crop").outcomes}

    assert {key: ends[key].status for key in ("ripe", "leaf", "lower", "look")} == dict.fromkeys(
        ("ripe", "leaf", "lower", "look"), OutcomeStatus.EXECUTED
    )
    assert ends["ripe"].effect == Harvested(fruit_count=0, fresh_mass_g=0.0)
    assert ends["leaf"].effect == LeafRemoved(leaf_id=LEAF.leaf_id)
    assert ends["ripe"].resolved_at == day_1
    events = {event.event_id: event for event in played.events_after(0, ALL).records}
    for key in ("ripe", "leaf", "lower", "look"):
        event_id = ends[key].event_id
        assert event_id is not None and event_id in events
        assert events[event_id].timestamp == day_1
    path = f"/consumer/v1/runs/{started.run_id}/outcomes"
    polls = [_poll(simulator, path)]
    polls.append(_poll(simulator, f"{path}?after={polls[-1].next}"))
    assert check_polls(polls) == []


def _poll(simulator: Simulator, path: str) -> OutcomeBatch:
    answer = consumer_respond(simulator, "GET", path)
    assert answer is not None and answer.status == 200, answer
    return OutcomeBatch.model_validate(answer.body)


class _Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now
