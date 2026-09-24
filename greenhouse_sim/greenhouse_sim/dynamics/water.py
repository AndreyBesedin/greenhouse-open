from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world import GreenhouseEnvironment, PlantWorld

_STRESS_RISE_PER_DAY = 0.08
_STRESS_RECOVERY_PER_DAY = 0.05


def daily_water_use_ml(
    plant: PlantWorld, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> float:
    """Hotter days and bigger plants use more water."""
    temp_factor = 1.0 + 0.03 * (environment.air_temperature_c - 24.0)
    size_factor = 1.0 + 0.01 * (plant.stem_length_cm / max(config.initial_stem_length_cm, 1.0))
    return config.water_use_ml_per_day_base * max(temp_factor, 0.3) * size_factor


def advance_water(
    plant: PlantWorld, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> PlantWorld:
    use = daily_water_use_ml(plant, environment, config)
    reservoir = plant.water_reservoir_ml - use - config.evaporation_ml_per_day
    reservoir = max(0.0, min(config.water_capacity_ml, reservoir))

    reservoir_pct = 100.0 * reservoir / config.water_capacity_ml
    if reservoir_pct < config.water_stress_threshold_pct:
        water_stress = min(1.0, plant.water_stress + _STRESS_RISE_PER_DAY)
    else:
        water_stress = max(0.0, plant.water_stress - _STRESS_RECOVERY_PER_DAY)

    return plant.model_copy(update={"water_reservoir_ml": reservoir, "water_stress": water_stress})


def apply_irrigation(plant: PlantWorld, amount_ml: float, config: ScenarioConfig) -> PlantWorld:
    reservoir = min(config.water_capacity_ml, plant.water_reservoir_ml + amount_ml)
    return plant.model_copy(update={"water_reservoir_ml": reservoir})
