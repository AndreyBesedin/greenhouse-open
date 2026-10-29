"""A run's own crop actions (P13.5): part of its plan, checked as the run
would carry them out, part of its identity only when it has some, and its
crop's: carried out on it at the start of their days, its crop kept apart
from another run's from the first day their crop actions differ, and from a
kept state whose crop actions up to its day are not its own."""

import re
from collections.abc import Callable
from dataclasses import replace
from typing import Final

import pytest
from greenhouse_protocol.actions import (
    Harvest,
    HarvestScope,
    Inspect,
    Lower,
    RemoveLeaf,
    SetLevel,
)

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop_actions import carry_out
from greenhouse_sim.core.crop_days import CropDone
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.crop import run_crop
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.kept_states import KeptState
from greenhouse_sim.services.runs import (
    PlannedAt,
    RunAction,
    RunPlan,
    RunRequest,
    crop_action_refusal,
    crop_days,
)
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "reference_greenhouse"
REFERENCE: Final = SCENARIO_REGISTRY[SCENARIO]
PLANT: Final = plant_ids(REFERENCE)[0]
RIPE: Final = Harvest(plant_id=PLANT, scope=HarvestScope.RIPE)


def _with(*planned: tuple[float, RunAction]) -> RunRequest:
    return RunRequest(
        SCENARIO, plan=RunPlan(actions=tuple(PlannedAt(at_s=at, action=a) for at, a in planned))
    )


def _run_id(simulator: Simulator, run: RunRequest) -> str:
    return air_through_a_run(simulator, run)[1]


def test_a_run_without_crop_actions_keeps_its_identity_and_one_with_them_has_another(
    simulator: Simulator,
) -> None:
    looked_at = Inspect(plant_id=PLANT, reason="spots on its lowest leaves")
    named = {
        "none": _run_id(simulator, RunRequest(SCENARIO)),
        "day 1": _run_id(simulator, _with((DAY_S, RIPE))),
        "day 2": _run_id(simulator, _with((2 * DAY_S, RIPE))),
        "looked at": _run_id(simulator, _with((DAY_S, looked_at))),
    }

    # As test_run_identity pins it: crop actions leave it as it was.
    assert named["none"] == "reference_greenhouse-climate-7828c7c0"
    assert len(set(named.values())) == len(named)
    assert _run_id(simulator, _with((DAY_S, RIPE))) == named["day 1"]
    # Given in another order, the same actions on different days are the
    # same run; at one moment, their order is how they apply, and another
    # order another run.
    leaf = RemoveLeaf(plant_id=PLANT, leaf_id=f"{PLANT}_n01_leaf")
    both = _run_id(simulator, _with((DAY_S, leaf), (2 * DAY_S, RIPE)))
    assert _run_id(simulator, _with((2 * DAY_S, RIPE), (DAY_S, leaf))) == both
    assert _run_id(simulator, _with((DAY_S, leaf), (DAY_S, RIPE))) != _run_id(
        simulator, _with((DAY_S, RIPE), (DAY_S, leaf))
    )


@pytest.mark.parametrize(
    ("scenario_id", "at_s", "action", "reason"),
    [
        (
            SCENARIO,
            DAY_S + 60,
            RIPE,
            "the run's crop steps a day at a time: it carries out harvest at a day's start, "
            "not at 86460 s",
        ),
        (SCENARIO, 0.0, RIPE, "the run's crop is planted at its start"),
        (SCENARIO, REFERENCE.run_length_s(), RIPE, "the run ends at 10368000 s"),
        (
            SCENARIO,
            DAY_S,
            Harvest(plant_id="nobody", scope=HarvestScope.RIPE),
            "reference_greenhouse has no plant 'nobody'",
        ),
        (
            "climate_box",
            DAY_S,
            Harvest(plant_id="climate_box_plant_001", scope=HarvestScope.RIPE),
            "climate_box grows its crop with the simple model, which takes no harvest",
        ),
    ],
)
def test_a_crop_action_the_run_would_not_carry_out_is_refused_saying_why(
    simulator: Simulator, scenario_id: str, at_s: float, action: RunAction, reason: str
) -> None:
    run = RunRequest(scenario_id, plan=RunPlan(actions=(PlannedAt(at_s=at_s, action=action),)))

    with pytest.raises(InvalidRequest, match=re.escape(reason)):
        air_through_a_run(simulator, run)


def test_a_plant_that_hangs_from_no_wire_is_not_lowered_to_a_head_room() -> None:
    unwired = SCENARIO_REGISTRY["solar_lab"]
    plant_id = plant_ids(unwired)[0]
    lowering = Lower(plant_id=plant_id, to_head_room_m=0.3)

    assert crop_action_refusal(unwired, lowering) == f"{plant_id} hangs from no wire"
    assert crop_action_refusal(unwired, Lower(plant_id=plant_id, by_internodes=1)) is None
    assert crop_action_refusal(REFERENCE, Lower(plant_id=PLANT, to_head_room_m=0.3)) is None


def test_a_plan_s_crop_actions_by_their_days_and_as_they_stood_before_a_moment() -> None:
    leaf = RemoveLeaf(plant_id=PLANT, leaf_id=f"{PLANT}_n01_leaf")
    plan = RunPlan(
        actions=(
            PlannedAt(at_s=2 * DAY_S, action=RIPE),
            PlannedAt(at_s=DAY_S, action=SetLevel(device_id="heater", level=1.0)),
            PlannedAt(at_s=DAY_S, action=leaf),
            PlannedAt(at_s=DAY_S, action=Inspect(plant_id=PLANT, reason="a look")),
            PlannedAt(at_s=DAY_S, action=RIPE),
        )
    )

    assert [each.action for each in plan.crop_plan()] == [leaf, RIPE, RIPE]
    assert crop_days(plan.crop_plan()) == {1: (leaf, RIPE), 2: (RIPE,)}
    # A crop at a day's start is the crop once that day's work is done: a
    # checkpoint then keeps the crop actions of that moment, not its levels.
    assert [each.action.kind for each in plan.before(DAY_S).actions] == [
        "remove_leaf",
        "inspect",
        "harvest",
    ]


def test_a_kept_state_s_crop_is_a_run_s_only_with_its_crop_actions_up_to_its_day() -> None:
    first, later = PlannedAt(at_s=DAY_S, action=RIPE), PlannedAt(at_s=3 * DAY_S, action=RIPE)
    state = KeptState(
        house=(SCENARIO, "default", "default", ()),
        schedule=Schedule(),
        day=2,
        air=HouseAir(temperature_c=20.0, humidity_g_kg=8.0, co2_ppm=400.0),
        crop_actions=(first,),
    )
    other = PlannedAt(at_s=2 * DAY_S, action=RIPE)

    assert state.crop_agrees((first, later))
    assert not state.crop_agrees(())
    assert not state.crop_agrees((first, other))
    assert replace(state, crop_actions=()).crop_agrees((later,))


def test_a_run_s_crop_carries_out_its_crop_actions_and_takes_over_days_before_them(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    """On the run's second day, after its crop work: every ripe fruit
    picked, of which there is none; the lowest leaf removed, and the stem
    lowered by the internode it leaves bare. Without the opening days kept,
    every crop here works its days out itself, as the plain run's would."""
    leaf = RemoveLeaf(plant_id=PLANT, leaf_id=f"{PLANT}_n01_leaf")
    lowering = Lower(plant_id=PLANT, by_internodes=1)
    plain = run_crop(simulator, RunRequest(SCENARIO))
    plain_day_1 = plain.plants_on(1)
    worked = run_crop(simulator, _with((DAY_S, RIPE), (DAY_S, leaf), (DAY_S, lowering)))
    later = run_crop(simulator, _with((2 * DAY_S, RIPE)))
    training = REFERENCE.layout.trainings()[0]
    pruned = carry_out(plain_day_1[0], leaf, training)
    lowered = carry_out(pruned.plant, lowering, training)

    work = worked.worked_on(1)
    assert work is not None
    assert work.done == (
        CropDone(carry_out(plain_day_1[0], RIPE, training).effect),
        CropDone(pruned.effect),
        CropDone(lowered.effect),
    )
    assert worked.plants_on(1)[0] == lowered.plant
    assert worked.plants_on(1)[1:] == plain_day_1[1:]
    # A run whose own crop actions start a day later shares the first day's
    # crop, taken over rather than worked out again.
    assert later.plants_on(1) is plain_day_1
    assert worked.plants_on(1) is not plain_day_1
