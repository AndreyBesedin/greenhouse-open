import numpy as np

from greenhouse_sim.biology.tomato.simple.parameters import (
    FRUIT_GROWTH_RATE_RANGE,
    REFERENCE_TEMPERATURE_C,
    STEM_GROWTH_LOSS_AT_FULL_WATER_STRESS,
    STEM_GROWTH_LOSS_PER_DEGREE,
    STEM_GROWTH_MIN_TEMPERATURE_FACTOR,
)
from greenhouse_sim.biology.tomato.simple.state import SimpleFruitState, SimplePlantState
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import Fruit, GreenhouseEnvironment, PlantWorld, Truss, TrussStage


def advance_stem(
    plant_state: SimplePlantState, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> float:
    """Stem length gained today. Stressed or too-hot/cold plants grow slower."""
    water_factor = 1.0 - STEM_GROWTH_LOSS_AT_FULL_WATER_STRESS * plant_state.water_stress
    temp_deviation = abs(environment.air_temperature_c - REFERENCE_TEMPERATURE_C)
    temp_factor = max(
        STEM_GROWTH_MIN_TEMPERATURE_FACTOR, 1.0 - temp_deviation * STEM_GROWTH_LOSS_PER_DEGREE
    )
    return (
        config.stem_growth_cm_per_day_base
        * water_factor
        * temp_factor
        * plant_state.growth_multiplier
    )


def maybe_initiate_truss(
    plant: PlantWorld, config: ScenarioConfig, seed: int
) -> tuple[Truss, dict[str, SimpleFruitState]] | None:
    """A new truss appears every `truss_interval_days` of plant age, up to `max_trusses`.

    Returns the truss with its fruits, and the model's values for each new fruit.
    """
    if len(plant.trusses) >= config.max_trusses:
        return None
    if plant.age_days == 0 or plant.age_days % config.truss_interval_days != 0:
        return None

    truss_index = len(plant.trusses) + 1
    rng = seeded_rng(seed, plant.plant_id, "truss", truss_index)
    truss_id = f"{plant.plant_id}_truss_{truss_index:02d}"
    fruit_low, fruit_high = config.fruits_per_truss_bounds
    fruit_count = int(rng.integers(fruit_low, fruit_high + 1))
    new_fruits = [
        _new_fruit(plant.plant_id, truss_id, index, config, rng) for index in range(fruit_count)
    ]
    truss = Truss(
        truss_id=truss_id,
        plant_id=plant.plant_id,
        index=truss_index,
        fruits=[fruit for fruit, _ in new_fruits],
    )
    return truss, {fruit.fruit_id: state for fruit, state in new_fruits}


def _new_fruit(
    plant_id: str,
    truss_id: str,
    index: int,
    config: ScenarioConfig,
    rng: np.random.Generator,
) -> tuple[Fruit, SimpleFruitState]:
    diameter_low, diameter_high = config.target_diameter_mm_bounds
    ripening_low, ripening_high = config.ripening_days_bounds
    target_diameter_mm = float(rng.uniform(diameter_low, diameter_high))
    growth_rate_multiplier = float(rng.uniform(*FRUIT_GROWTH_RATE_RANGE))
    ripening_day = int(rng.integers(ripening_low, ripening_high + 1))
    fruit = Fruit(fruit_id=f"{truss_id}_fruit_{index:02d}", truss_id=truss_id, plant_id=plant_id)
    state = SimpleFruitState(
        target_diameter_mm=target_diameter_mm,
        growth_rate_multiplier=growth_rate_multiplier,
        ripening_day=ripening_day,
    )
    return fruit, state


def grow_fruit_diameter(
    fruit: Fruit, fruit_state: SimpleFruitState, config: ScenarioConfig
) -> float:
    """A bounded, monotonically increasing growth curve toward target_diameter_mm."""
    effective_age = fruit.age_days * fruit_state.growth_rate_multiplier
    fraction = effective_age / (effective_age + config.fruit_growth_days_to_target)
    return fruit_state.target_diameter_mm * fraction


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
