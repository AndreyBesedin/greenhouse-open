"""A whole greenhouse's day under the simple reference models.

The environment advances first, then every plant responds to the new
environment. Each model owns its own rules and randomness; this module only
composes them, and keeps the plant model's own values in
`GreenhouseWorld.plant_model` between days.
"""

from greenhouse_sim.biology.tomato.simple.model import SimpleTomatoModel
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseWorld

_ENVIRONMENT_MODEL = SimpleEnvironmentModel()
_PLANT_MODEL = SimpleTomatoModel()


def initialize_world(
    config: ScenarioConfig, plant_ids: list[str], *, greenhouse_id: str | None = None
) -> GreenhouseWorld:
    plants, plant_model = _PLANT_MODEL.initialize(plant_ids, config)
    return GreenhouseWorld(
        greenhouse_id=greenhouse_id or config.greenhouse_id,
        simulated_day=0,
        environment=_ENVIRONMENT_MODEL.initial(config),
        plants=plants,
        plant_model=plant_model,
    )


def advance_world(world: GreenhouseWorld, config: ScenarioConfig, day: int) -> GreenhouseWorld:
    environment = _ENVIRONMENT_MODEL.advance(world.environment, config, day)
    plants, plant_model = _PLANT_MODEL.advance(world.plants, world.plant_model, environment, config)
    return world.model_copy(
        update={
            "simulated_day": day,
            "environment": environment,
            "plants": plants,
            "plant_model": plant_model,
        }
    )
