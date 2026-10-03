"""A whole greenhouse's day under the simple reference models.

The environment advances first, then every plant responds to the new
environment. Each model owns its own rules and randomness; this module only
composes them, and keeps the plant model's own values in
`GreenhouseWorld.plant_model` between days.
"""

from greenhouse_sim.biology.tomato.simple.daily import advance_plant, initial_plant
from greenhouse_sim.biology.tomato.simple.state import SimplePlantState, SimpleTomatoState
from greenhouse_sim.environment.simple import advance_environment, initial_environment
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseWorld, PlantWorld


def initialize_world(
    config: ScenarioConfig, plant_ids: list[str], *, greenhouse_id: str | None = None
) -> GreenhouseWorld:
    initial = [initial_plant(plant_id, config) for plant_id in plant_ids]
    return GreenhouseWorld(
        greenhouse_id=greenhouse_id or config.greenhouse_id,
        simulated_day=0,
        environment=initial_environment(config),
        plants=[plant for plant, _ in initial],
        plant_model=SimpleTomatoState(plants={plant.plant_id: state for plant, state in initial}),
    )


def advance_world(world: GreenhouseWorld, config: ScenarioConfig, day: int) -> GreenhouseWorld:
    environment = advance_environment(world.environment, config, day)

    plants: list[PlantWorld] = []
    plant_states: dict[str, SimplePlantState] = {}
    fruit_states = dict(world.plant_model.fruits)
    for plant in world.plants:
        advanced, plant_state, new_fruit_states = advance_plant(
            plant, world.plant_model, environment, config
        )
        plants.append(advanced)
        plant_states[advanced.plant_id] = plant_state
        fruit_states.update(new_fruit_states)

    plant_model = world.plant_model.model_copy(
        update={"plants": plant_states, "fruits": fruit_states}
    )
    return world.model_copy(
        update={
            "simulated_day": day,
            "environment": environment,
            "plants": plants,
            "plant_model": plant_model,
        }
    )
