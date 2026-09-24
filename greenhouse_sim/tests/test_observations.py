from datetime import UTC, datetime

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation

from greenhouse_sim.observations import generate_observations
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import GreenhouseWorld
from greenhouse_sim.world_builder import advance_world, initialize_world

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_IDS = ["gh_001_plant_001", "gh_001_plant_002"]
TIMESTAMP = datetime(2026, 1, 9, tzinfo=UTC)
SIMULATION_ID = "sim_test"


def _world_at(day: int) -> GreenhouseWorld:
    world = initialize_world(CONFIG, PLANT_IDS)
    for d in range(1, day + 1):
        world = advance_world(world, CONFIG, d)
    return world


def test_generate_observations_is_deterministic_for_the_same_world() -> None:
    world = _world_at(8)

    first = generate_observations(
        world, CONFIG, day=8, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )
    second = generate_observations(
        world, CONFIG, day=8, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )

    assert first.observations == second.observations


def test_generate_observations_differs_across_days() -> None:
    day_8 = generate_observations(
        _world_at(8), CONFIG, day=8, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )
    day_9 = generate_observations(
        _world_at(9), CONFIG, day=9, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )

    assert day_8.observations != day_9.observations


def test_generate_observations_emits_soil_moisture_within_0_to_100() -> None:
    generation = generate_observations(
        _world_at(1), CONFIG, day=1, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )

    moisture_readings = [
        obs.value
        for obs in generation.observations
        if obs.observation_type == ObservationType.SOIL_MOISTURE_PCT
    ]
    assert len(moisture_readings) == len(PLANT_IDS)
    assert all(0.0 <= value <= 100.0 for value in moisture_readings)


def test_generate_observations_emits_one_greenhouse_level_temperature_reading() -> None:
    generation = generate_observations(
        _world_at(1), CONFIG, day=1, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )

    temperature_readings = [
        obs
        for obs in generation.observations
        if obs.observation_type == ObservationType.AIR_TEMPERATURE_C
    ]
    assert len(temperature_readings) == 1
    assert temperature_readings[0].plant_id is None


def test_generate_observations_emits_ripe_mass_that_grows_as_fruit_ripens() -> None:
    early = generate_observations(
        _world_at(30), CONFIG, day=30, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )
    late = generate_observations(
        _world_at(60), CONFIG, day=60, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )

    def total_ripe_mass(observations: list[Observation]) -> float:
        return sum(
            obs.value
            for obs in observations
            if obs.observation_type == ObservationType.ESTIMATED_RIPE_MASS_G
        )

    assert total_ripe_mass(late.observations) > total_ripe_mass(early.observations)


def test_generate_observations_emits_a_visible_height_that_grows_as_the_plant_grows() -> None:
    early = generate_observations(
        _world_at(1), CONFIG, day=1, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )
    late = generate_observations(
        _world_at(30), CONFIG, day=30, timestamp=TIMESTAMP, simulation_id=SIMULATION_ID
    )

    def height_for_plant_one(observations: list[Observation]) -> float:
        return next(
            obs.value
            for obs in observations
            if obs.observation_type == ObservationType.VISIBLE_HEIGHT_CM
            and obs.plant_id == PLANT_IDS[0]
        )

    assert height_for_plant_one(late.observations) > height_for_plant_one(early.observations)
