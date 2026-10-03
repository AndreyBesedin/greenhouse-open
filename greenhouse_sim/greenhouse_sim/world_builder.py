"""A whole greenhouse's day, composed from an environment and a plant model.

The environment advances first, then every plant responds to the new
environment. Each model owns its own rules and randomness; this module only
composes them, and keeps the plant model's own state in
`GreenhouseWorld.plant_model` between days. Without models given, it uses the
simple reference models.
"""

from greenhouse_sim.biology.contract import PlantModel
from greenhouse_sim.biology.tomato.simple.model import SimpleTomatoModel
from greenhouse_sim.environment.contract import EnvironmentModel
from greenhouse_sim.environment.simple import SimpleEnvironmentModel
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseWorld, PlantModelState


def initialize_world(
    config: ScenarioConfig,
    plant_ids: list[str],
    *,
    greenhouse_id: str | None = None,
    environment_model: EnvironmentModel | None = None,
    plant_model: PlantModel[PlantModelState] | None = None,
) -> GreenhouseWorld:
    environment_model = environment_model or SimpleEnvironmentModel()
    plant_model = plant_model or SimpleTomatoModel()
    plants, plant_state = plant_model.initialize(plant_ids, config)
    return GreenhouseWorld(
        greenhouse_id=greenhouse_id or config.greenhouse_id,
        simulated_day=0,
        environment=environment_model.initial(config),
        plants=plants,
        plant_model=plant_state,
    )


def advance_world(
    world: GreenhouseWorld,
    config: ScenarioConfig,
    day: int,
    *,
    environment_model: EnvironmentModel | None = None,
    plant_model: PlantModel[PlantModelState] | None = None,
) -> GreenhouseWorld:
    environment_model = environment_model or SimpleEnvironmentModel()
    plant_model = plant_model or SimpleTomatoModel()
    environment = environment_model.advance(world.environment, config, day)
    plants, plant_state = plant_model.advance(world.plants, world.plant_model, environment, config)
    return world.model_copy(
        update={
            "simulated_day": day,
            "environment": environment,
            "plants": plants,
            "plant_model": plant_state,
        }
    )
