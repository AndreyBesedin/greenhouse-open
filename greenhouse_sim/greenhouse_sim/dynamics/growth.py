import numpy as np

from greenhouse_sim.rng import seeded_rng
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world import Fruit, GreenhouseEnvironment, PlantWorld, Truss, TrussStage


def advance_stem(
    plant: PlantWorld, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> float:
    """Stem length gained today. Stressed or too-hot/cold plants grow slower."""
    water_factor = 1.0 - 0.6 * plant.water_stress
    temp_deviation = abs(environment.air_temperature_c - 24.0)
    temp_factor = max(0.5, 1.0 - temp_deviation * 0.02)
    return config.stem_growth_cm_per_day_base * water_factor * temp_factor * plant.growth_multiplier


def maybe_initiate_truss(plant: PlantWorld, config: ScenarioConfig, seed: int) -> Truss | None:
    """A new truss appears every `truss_interval_days` of plant age, up to `max_trusses`."""
    if len(plant.trusses) >= config.max_trusses:
        return None
    if plant.age_days == 0 or plant.age_days % config.truss_interval_days != 0:
        return None

    truss_index = len(plant.trusses) + 1
    rng = seeded_rng(seed, plant.plant_id, "truss", truss_index)
    truss_id = f"{plant.plant_id}_truss_{truss_index:02d}"
    fruit_low, fruit_high = config.fruits_per_truss_bounds
    fruit_count = int(rng.integers(fruit_low, fruit_high + 1))
    fruits = [
        _new_fruit(plant.plant_id, truss_id, index, config, rng) for index in range(fruit_count)
    ]
    return Truss(truss_id=truss_id, plant_id=plant.plant_id, index=truss_index, fruits=fruits)


def _new_fruit(
    plant_id: str,
    truss_id: str,
    index: int,
    config: ScenarioConfig,
    rng: np.random.Generator,
) -> Fruit:
    diameter_low, diameter_high = config.target_diameter_mm_bounds
    ripening_low, ripening_high = config.ripening_days_bounds
    target_diameter_mm = float(rng.uniform(diameter_low, diameter_high))
    growth_rate_multiplier = float(rng.uniform(0.85, 1.15))
    ripening_day = int(rng.integers(ripening_low, ripening_high + 1))
    return Fruit(
        fruit_id=f"{truss_id}_fruit_{index:02d}",
        truss_id=truss_id,
        plant_id=plant_id,
        target_diameter_mm=target_diameter_mm,
        growth_rate_multiplier=growth_rate_multiplier,
        ripening_day=ripening_day,
    )


def grow_fruit_diameter(fruit: Fruit, config: ScenarioConfig) -> float:
    """A bounded, monotonically increasing growth curve toward target_diameter_mm."""
    effective_age = fruit.age_days * fruit.growth_rate_multiplier
    fraction = effective_age / (effective_age + config.fruit_growth_days_to_target)
    return fruit.target_diameter_mm * fraction


def fruit_mass_g(diameter_mm: float, config: ScenarioConfig) -> float:
    return config.mass_coefficient_g_per_mm3 * diameter_mm**3


def truss_stage(truss: Truss) -> TrussStage:
    if not truss.fruits:
        return TrussStage.INITIATED
    statuses = {fruit.status for fruit in truss.fruits}
    if statuses <= {"HARVESTED"}:
        return TrussStage.INACTIVE
    if "RIPE" in statuses:
        return TrussStage.HARVESTABLE
    return TrussStage.FRUITING
