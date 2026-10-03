"""Keeping a run's hidden world between steps, with no database."""

from greenhouse_sim.checkpoints import InMemoryWorldCheckpoints, WorldCheckpoints
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import GreenhouseWorld
from greenhouse_sim.world_builder import initialize_world

CONFIG = SCENARIO_REGISTRY["gh_001"]


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
