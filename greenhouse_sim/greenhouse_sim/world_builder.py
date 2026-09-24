from greenhouse_sim.dynamics.environment import advance_environment, initial_environment
from greenhouse_sim.dynamics.growth import (
    advance_stem,
    fruit_mass_g,
    grow_fruit_diameter,
    maybe_initiate_truss,
    truss_stage,
)
from greenhouse_sim.dynamics.ripening import advance_ripening
from greenhouse_sim.dynamics.water import advance_water
from greenhouse_sim.rng import seeded_rng
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world import (
    Fruit,
    FruitStatus,
    GreenhouseEnvironment,
    GreenhouseWorld,
    PlantWorld,
    Truss,
)


def initialize_world(
    config: ScenarioConfig, plant_ids: list[str], *, greenhouse_id: str | None = None
) -> GreenhouseWorld:
    return GreenhouseWorld(
        greenhouse_id=greenhouse_id or config.greenhouse_id,
        simulated_day=0,
        environment=initial_environment(config),
        plants=[_initial_plant(plant_id, config) for plant_id in plant_ids],
    )


def _initial_plant(plant_id: str, config: ScenarioConfig) -> PlantWorld:
    rng = seeded_rng(config.random_seed, plant_id, "growth_multiplier")
    return PlantWorld(
        plant_id=plant_id,
        stem_length_cm=config.initial_stem_length_cm,
        water_reservoir_ml=config.initial_water_reservoir_ml,
        growth_multiplier=float(rng.uniform(0.85, 1.15)),
    )


def advance_world(world: GreenhouseWorld, config: ScenarioConfig, day: int) -> GreenhouseWorld:
    environment_rng = seeded_rng(config.random_seed, day, "environment")
    environment = advance_environment(world.environment, config, environment_rng)

    plants = [_advance_plant(plant, environment, config) for plant in world.plants]

    return world.model_copy(
        update={"simulated_day": day, "environment": environment, "plants": plants}
    )


def _advance_plant(
    plant: PlantWorld, environment: GreenhouseEnvironment, config: ScenarioConfig
) -> PlantWorld:
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
