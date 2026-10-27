"""A run's crop actions as its address spells them (P13.8): `&crop=`, each
read as the protocol's own action, refused in the request's words when it is
none, written back as it was read, and the same run as the plan of those
actions."""

import re
from typing import Final

import pytest
from greenhouse_protocol.actions import Harvest, HarvestScope, Inspect, Lower, RemoveLeaf

from greenhouse_sim.api.routes.runs import run_request
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import (
    PlannedAt,
    RunPlan,
    RunRequest,
    crop_spelling,
    spelled_crop_action,
)
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "reference_greenhouse"
PLANT: Final = plant_ids(SCENARIO_REGISTRY[SCENARIO])[0]
LEAF: Final = f"{PLANT}_n01_leaf"
WHY: Final = "spots on its lowest leaves"
RIPE: Final = Harvest(plant_id=PLANT, scope=HarvestScope.RIPE)


@pytest.mark.parametrize(
    ("kind", "target", "action"),
    [
        ("harvest_ripe", "", RIPE),
        (
            "harvest_fruit",
            f"{PLANT}_t01_f01",
            Harvest(plant_id=PLANT, scope=HarvestScope.FRUIT, organ_id=f"{PLANT}_t01_f01"),
        ),
        (
            "harvest_truss",
            f"{PLANT}_t01",
            Harvest(plant_id=PLANT, scope=HarvestScope.TRUSS, organ_id=f"{PLANT}_t01"),
        ),
        ("lower_stem", "2", Lower(plant_id=PLANT, by_internodes=2)),
        ("lower_cm", "15", Lower(plant_id=PLANT, by_cm=15.0)),
        ("lower_to", "0.3", Lower(plant_id=PLANT, to_head_room_m=0.3)),
        ("remove_leaf", LEAF, RemoveLeaf(plant_id=PLANT, leaf_id=LEAF)),
        ("inspect", WHY, Inspect(plant_id=PLANT, reason=WHY)),
    ],
)
def test_each_crop_action_is_read_as_the_protocols_and_spelled_back(
    kind: str, target: str, action: Harvest | Lower | RemoveLeaf | Inspect
) -> None:
    assert spelled_crop_action(PLANT, kind, target) == action
    assert crop_spelling(action) == (kind, target)


@pytest.mark.parametrize(
    ("kind", "target", "said"),
    [
        ("prune", "", "a crop action is one of harvest_ripe, harvest_fruit"),
        ("harvest_ripe", "t01", "harvest_ripe acts on nothing, not 't01'"),
        ("harvest_fruit", "", "harvest_fruit of 'p01' wants a fruit, not ''"),
        ("lower_stem", "two", "lower_stem of 'p01' wants how many internodes, not 'two'"),
        ("lower_cm", "-1", "lower_cm of 'p01' wants how many centimetres, not '-1'"),
        ("inspect", "", "inspect of 'p01' wants why, not ''"),
    ],
)
def test_what_is_no_crop_action_is_refused_saying_what_it_wants(
    kind: str, target: str, said: str
) -> None:
    with pytest.raises(InvalidRequest, match=re.escape(said.replace("p01", PLANT))):
        spelled_crop_action(PLANT, kind, target)


def test_a_run_asked_for_with_its_crop_actions_is_the_run_of_their_plan(
    simulator: Simulator,
) -> None:
    spelled = f"{DAY_S:.0f}:{PLANT}:lower_stem:1,{2 * DAY_S:.0f}:{PLANT}:harvest_ripe:"
    asked = run_request(SCENARIO, {"crop": [spelled]})
    planned = RunRequest(
        SCENARIO,
        plan=RunPlan(
            actions=(
                PlannedAt(at_s=DAY_S, action=Lower(plant_id=PLANT, by_internodes=1)),
                PlannedAt(at_s=2 * DAY_S, action=RIPE),
            )
        ),
    )

    run_id = air_through_a_run(simulator, asked)[1]
    assert run_id == air_through_a_run(simulator, planned)[1]
    assert run_id != air_through_a_run(simulator, RunRequest(SCENARIO))[1]
    assert asked.plan.crop_spelled() == (
        (DAY_S, PLANT, "lower_stem", "1"),
        (2 * DAY_S, PLANT, "harvest_ripe", ""),
    )


def test_a_crop_action_not_spelled_whole_is_refused() -> None:
    with pytest.raises(InvalidRequest, match="crop wants seconds:plant:kind:organ actions"):
        run_request(SCENARIO, {"crop": [f"86400:{PLANT}:lower_stem"]})
