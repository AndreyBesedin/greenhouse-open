from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import FruitStatus, GreenhouseWorld
from greenhouse_sim.world_builder import advance_world, initialize_world

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_IDS = ["gh_001_plant_001", "gh_001_plant_002"]


def _run_days(num_days: int) -> list[GreenhouseWorld]:
    world = initialize_world(CONFIG, PLANT_IDS)
    worlds = []
    for day in range(1, num_days + 1):
        world = advance_world(world, CONFIG, day)
        worlds.append(world)
    return worlds


def test_initialize_world_creates_one_plant_world_per_plant_id() -> None:
    world = initialize_world(CONFIG, PLANT_IDS)

    assert world.simulated_day == 0
    assert {p.plant_id for p in world.plants} == set(PLANT_IDS)
    assert all(p.stem_length_cm == CONFIG.initial_stem_length_cm for p in world.plants)
    assert all(p.trusses == [] for p in world.plants)


def test_advance_world_is_deterministic_for_the_same_inputs() -> None:
    first = advance_world(initialize_world(CONFIG, PLANT_IDS), CONFIG, 1)
    second = advance_world(initialize_world(CONFIG, PLANT_IDS), CONFIG, 1)

    assert first == second


def test_advance_world_grows_the_plant_across_days() -> None:
    worlds = _run_days(5)

    stem_lengths = [w.plant(PLANT_IDS[0]).stem_length_cm for w in worlds]
    assert stem_lengths == sorted(stem_lengths)
    assert stem_lengths[-1] > CONFIG.initial_stem_length_cm


def test_a_truss_initiates_at_the_configured_interval_and_persists() -> None:
    worlds = _run_days(CONFIG.truss_interval_days + 2)

    plant_at_interval = worlds[CONFIG.truss_interval_days - 1].plant(PLANT_IDS[0])
    assert len(plant_at_interval.trusses) == 1
    assert len(plant_at_interval.trusses[0].fruits) > 0

    # The truss (and its fruits) is the same object carried forward, not regenerated.
    plant_after = worlds[-1].plant(PLANT_IDS[0])
    assert plant_after.trusses[0].truss_id == plant_at_interval.trusses[0].truss_id
    assert (
        plant_after.trusses[0].fruits[0].fruit_id == plant_at_interval.trusses[0].fruits[0].fruit_id
    )


def test_fruit_diameter_grows_monotonically_and_stays_bounded() -> None:
    worlds = _run_days(CONFIG.truss_interval_days + 15)

    plant_id = PLANT_IDS[0]
    diameters = []
    for world in worlds[CONFIG.truss_interval_days - 1 :]:
        plant = world.plant(plant_id)
        if plant.trusses and plant.trusses[0].fruits:
            fruit = plant.trusses[0].fruits[0]
            diameters.append((fruit.diameter_mm, fruit.target_diameter_mm))

    values = [d for d, _ in diameters]
    assert values == sorted(values)
    assert all(d <= target for d, target in diameters)


def test_ripe_fruit_eventually_appears() -> None:
    worlds = _run_days(60)

    plant = worlds[-1].plant(PLANT_IDS[0])
    ripe_fruits = [
        fruit
        for truss in plant.trusses
        for fruit in truss.fruits
        if fruit.status == FruitStatus.RIPE
    ]
    assert ripe_fruits
