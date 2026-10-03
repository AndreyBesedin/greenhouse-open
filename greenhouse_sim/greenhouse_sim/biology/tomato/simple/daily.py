"""One plant's day under the simple tomato model."""

from greenhouse_sim.biology.tomato.simple.growth import (
    advance_stem,
    fruit_mass_g,
    grow_fruit_diameter,
    maybe_initiate_truss,
    truss_stage,
)
from greenhouse_sim.biology.tomato.simple.ripening import advance_ripening
from greenhouse_sim.biology.tomato.simple.water import advance_water
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.state import (
    Fruit,
    FruitStatus,
    GreenhouseEnvironment,
    PlantWorld,
    Truss,
)


def initial_plant(plant_id: str, config: ScenarioConfig) -> PlantWorld:
    rng = seeded_rng(config.random_seed, plant_id, "growth_multiplier")
    return PlantWorld(
        plant_id=plant_id,
        stem_length_cm=config.initial_stem_length_cm,
        water_reservoir_ml=config.initial_water_reservoir_ml,
        growth_multiplier=float(rng.uniform(0.85, 1.15)),
    )


def advance_plant(
    plant: PlantWorld, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> PlantWorld:
    """Advances one plant by a day in the given, already-advanced environment.

    Depends only on the plant, the environment and the scenario: the plant's
    random draws are keyed by its own identity.
    """
    plant = advance_water(plant, environment, config)
    stem_growth = advance_stem(plant, environment, config)
    plant = plant.model_copy(
        update={
            "stem_length_cm": plant.stem_length_cm + stem_growth,
            "age_days": plant.age_days + 1,
        }
    )

    trusses = [_advance_truss(truss, environment, config) for truss in plant.trusses]
    new_truss = maybe_initiate_truss(plant, config, config.random_seed)
    if new_truss is not None:
        trusses.append(new_truss)

    return plant.model_copy(update={"trusses": trusses})


def _advance_truss(
    truss: Truss, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> Truss:
    fruits = [_advance_fruit(fruit, environment, config) for fruit in truss.fruits]
    updated = truss.model_copy(update={"age_days": truss.age_days + 1, "fruits": fruits})
    return updated.model_copy(update={"stage": truss_stage(updated)})


def _advance_fruit(
    fruit: Fruit, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> Fruit:
    if fruit.status == FruitStatus.HARVESTED:
        return fruit

    aged = fruit.model_copy(update={"age_days": fruit.age_days + 1})
    diameter = grow_fruit_diameter(aged, config)
    grown = aged.model_copy(
        update={"diameter_mm": diameter, "mass_g": fruit_mass_g(diameter, config)}
    )
    return advance_ripening(grown, environment)
