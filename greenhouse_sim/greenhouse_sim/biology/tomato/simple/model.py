"""The simple tomato model for a whole crop, as the engine uses it."""

from collections.abc import Sequence

from greenhouse_sim.biology.tomato.simple.daily import advance_plant, initial_plant
from greenhouse_sim.biology.tomato.simple.state import SimplePlantState, SimpleTomatoState
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseEnvironment, PlantWorld


class SimpleTomatoModel:
    def initialize(
        self, plant_ids: Sequence[str], config: ScenarioConfig
    ) -> tuple[list[PlantWorld], SimpleTomatoState]:
        initial = [initial_plant(plant_id, config) for plant_id in plant_ids]
        state = SimpleTomatoState(
            plants={plant.plant_id: plant_state for plant, plant_state in initial}
        )
        return [plant for plant, _ in initial], state

    def advance(
        self,
        plants: Sequence[PlantWorld],
        state: SimpleTomatoState,
        environment: GreenhouseEnvironment,
        config: ScenarioConfig,
    ) -> tuple[list[PlantWorld], SimpleTomatoState]:
        advanced_plants: list[PlantWorld] = []
        plant_states: dict[str, SimplePlantState] = {}
        fruit_states = dict(state.fruits)
        for plant in plants:
            advanced, plant_state, new_fruit_states = advance_plant(
                plant, state, environment, config
            )
            advanced_plants.append(advanced)
            plant_states[advanced.plant_id] = plant_state
            fruit_states.update(new_fruit_states)

        return advanced_plants, state.model_copy(
            update={"plants": plant_states, "fruits": fruit_states}
        )
