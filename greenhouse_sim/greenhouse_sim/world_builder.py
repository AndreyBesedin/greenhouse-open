"""A whole greenhouse's day under the simple reference models.

The environment advances first, then every plant responds to the new
environment. Each model owns its own rules and randomness; this module only
composes them.
"""

from greenhouse_sim.biology.tomato.simple.daily import advance_plant, initial_plant
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.environment.simple import advance_environment, initial_environment
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseWorld


def initialize_world(
    config: ScenarioConfig, plant_ids: list[str], *, greenhouse_id: str | None = None
) -> GreenhouseWorld:
    return GreenhouseWorld(
        greenhouse_id=greenhouse_id or config.greenhouse_id,
        simulated_day=0,
        environment=initial_environment(config),
        plants=[initial_plant(plant_id, config) for plant_id in plant_ids],
    )


def advance_world(world: GreenhouseWorld, config: ScenarioConfig, day: int) -> GreenhouseWorld:
    environment_rng = seeded_rng(config.random_seed, day, "environment")
    environment = advance_environment(world.environment, config, environment_rng)

    plants = [advance_plant(plant, environment, config) for plant in world.plants]

    return world.model_copy(
        update={"simulated_day": day, "environment": environment, "plants": plants}
    )
