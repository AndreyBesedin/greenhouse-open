from greenhouse_protocol.action import LowerPlantAction, ScheduleInspectionAction, WaterPlantAction

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.validation import validate_action
from greenhouse_sim.world import GreenhouseWorld
from greenhouse_sim.world_builder import advance_world, initialize_world

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_ID = "gh_001_plant_001"


def _grown_world(days: int = 60) -> GreenhouseWorld:
    world = initialize_world(CONFIG, [PLANT_ID])
    for day in range(1, days + 1):
        world = advance_world(world, CONFIG, day)
    return world


def test_validate_action_rejects_an_unknown_plant() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])
    result = validate_action(world, WaterPlantAction(plant_id="does_not_exist", amount_ml=500))

    assert result.accepted is False


def test_validate_water_action_rejects_non_positive_amount() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])
    result = validate_action(world, WaterPlantAction(plant_id=PLANT_ID, amount_ml=0))

    assert result.accepted is False


def test_validate_lower_action_rejects_an_amount_exceeding_visible_height() -> None:
    world = _grown_world()
    plant = world.plant(PLANT_ID)
    visible_height = plant.stem_length_cm - plant.lowered_length_cm

    result = validate_action(
        world, LowerPlantAction(plant_id=PLANT_ID, amount_cm=visible_height + 1)
    )

    assert result.accepted is False


def test_validate_inspection_action_rejects_an_empty_reason() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])

    result = validate_action(world, ScheduleInspectionAction(plant_id=PLANT_ID, reason=""))

    assert result.accepted is False
