from datetime import UTC, datetime

from greenhouse_protocol.action import WaterPlantAction
from greenhouse_protocol.enums import EventType

from greenhouse_sim.executor import ActionExecutor, SimulatedOperatorExecutor
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world_builder import initialize_world

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_ID = "gh_001_plant_001"
TIMESTAMP = datetime(2026, 1, 9, tzinfo=UTC)


def test_simulated_operator_executor_satisfies_the_action_executor_protocol() -> None:
    executor: ActionExecutor = SimulatedOperatorExecutor()
    assert executor is not None


def test_simulated_operator_executor_applies_an_action_instantaneously_and_completely() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])
    plant_before = world.plant(PLANT_ID)
    executor = SimulatedOperatorExecutor()

    updated_world, event = executor.apply(
        world,
        WaterPlantAction(plant_id=PLANT_ID, amount_ml=200),
        CONFIG,
        day=1,
        timestamp=TIMESTAMP,
    )

    # The full requested amount lands in one step - no partial completion,
    # no delay, matching the class docstring.
    assert updated_world.plant(PLANT_ID).water_reservoir_ml == plant_before.water_reservoir_ml + 200
    assert event.event_type == EventType.WATERING
