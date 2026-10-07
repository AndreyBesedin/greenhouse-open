"""Keeping a run's hidden world between steps, with no database."""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.action import HarvestPlantAction, RequestedAction

from greenhouse_sim.checkpoints import InMemoryWorldCheckpoints, WorldCheckpoints
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import GreenhouseWorld
from greenhouse_sim.world_builder import initialize_world

CONFIG = SCENARIO_REGISTRY["tomato_compartment"]


def _world(greenhouse_id: str, simulated_day: int = 0) -> GreenhouseWorld:
    world = initialize_world(CONFIG, ["plant_001"], greenhouse_id=greenhouse_id)
    return world.model_copy(update={"simulated_day": simulated_day})


def test_the_latest_saved_world_is_kept_per_greenhouse() -> None:
    checkpoints: WorldCheckpoints = InMemoryWorldCheckpoints()
    earlier, later, other = _world("gh_a", 1), _world("gh_a", 2), _world("gh_b", 1)

    checkpoints.save(earlier)
    checkpoints.save(later)
    checkpoints.save(other)

    assert checkpoints.get_latest("gh_a") == later
    assert checkpoints.get_latest("gh_b") == other


def test_a_greenhouse_with_no_saved_world_has_no_checkpoint() -> None:
    assert InMemoryWorldCheckpoints().get_latest("gh_a") is None


def test_deleting_a_greenhouse_forgets_only_that_greenhouse() -> None:
    checkpoints = InMemoryWorldCheckpoints()
    checkpoints.save(_world("gh_a"))
    checkpoints.save(_world("gh_b"))

    checkpoints.delete_for_greenhouse("gh_a")
    checkpoints.delete_for_greenhouse("gh_a")

    assert checkpoints.get_latest("gh_a") is None
    assert checkpoints.get_latest("gh_b") == _world("gh_b")


def test_a_world_saved_as_json_loads_back_unchanged() -> None:
    """A store that persists worlds outside the process, such as a database,
    keeps them as JSON. Everything a run needs to continue, including the
    values a model keeps for itself, must survive the round trip."""
    # The compartment's season is long enough for fruit to ripen and be
    # harvested.
    config = SCENARIO_REGISTRY["tomato_compartment"]
    engine = SimulationEngine(config)
    plant_ids = ["tomato_compartment_plant_001", "tomato_compartment_plant_002"]
    world = engine.initialize(plant_ids, greenhouse_id="tomato_compartment")
    start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    for day in range(1, config.duration_days + 1):
        timestamp = start + timedelta(days=day - 1)
        world = engine.advance(world, day=day, timestamp=timestamp, simulation_id="sim").world
        harvest: list[RequestedAction] = [HarvestPlantAction(plant_id=plant_ids[0])]
        world = engine.apply_actions(world, harvest, day=day, timestamp=timestamp).world
    assert any(f.status == "HARVESTED" for p in world.plants for t in p.trusses for f in t.fruits)

    assert GreenhouseWorld.model_validate_json(world.model_dump_json()) == world
