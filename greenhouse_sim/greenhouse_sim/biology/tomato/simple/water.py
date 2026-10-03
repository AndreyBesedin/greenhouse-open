from greenhouse_sim.biology.tomato.simple.parameters import (
    REFERENCE_TEMPERATURE_C,
    WATER_STRESS_RECOVERY_PER_DAY,
    WATER_STRESS_RISE_PER_DAY,
    WATER_USE_INCREASE_PER_DEGREE,
    WATER_USE_INCREASE_PER_INITIAL_STEM_LENGTH,
    WATER_USE_MIN_TEMPERATURE_FACTOR,
)
from greenhouse_sim.biology.tomato.simple.state import SimplePlantState
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import GreenhouseEnvironment, PlantWorld


def daily_water_use_ml(
    plant: PlantWorld, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> float:
    """Hotter days and bigger plants use more water."""
    temp_factor = 1.0 + WATER_USE_INCREASE_PER_DEGREE * (
        environment.air_temperature_c - REFERENCE_TEMPERATURE_C
    )
    size_factor = 1.0 + WATER_USE_INCREASE_PER_INITIAL_STEM_LENGTH * (
        plant.stem_length_cm / max(config.initial_stem_length_cm, 1.0)
    )
    return (
        config.water_use_ml_per_day_base
        * max(temp_factor, WATER_USE_MIN_TEMPERATURE_FACTOR)
        * size_factor
    )


def advance_water(
    plant: PlantWorld,
    plant_state: SimplePlantState,
    environment: GreenhouseEnvironment,
    config: ScenarioConfig,
) -> tuple[PlantWorld, SimplePlantState]:
    """The day's water use empties the root zone; a low root zone builds stress."""
    use = daily_water_use_ml(plant, environment, config)
    reservoir = plant.water_reservoir_ml - use - config.evaporation_ml_per_day
    reservoir = max(0.0, min(config.water_capacity_ml, reservoir))

    reservoir_pct = 100.0 * reservoir / config.water_capacity_ml
    if reservoir_pct < config.water_stress_threshold_pct:
        water_stress = min(1.0, plant_state.water_stress + WATER_STRESS_RISE_PER_DAY)
    else:
        water_stress = max(0.0, plant_state.water_stress - WATER_STRESS_RECOVERY_PER_DAY)

    return (
        plant.model_copy(update={"water_reservoir_ml": reservoir}),
        plant_state.model_copy(update={"water_stress": water_stress}),
    )
