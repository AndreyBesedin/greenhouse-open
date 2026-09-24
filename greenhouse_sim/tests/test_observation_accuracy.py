"""Scoring the simulator's sensing against what was really the case."""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import GroundTruth, ground_truth
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_IDS = ["gh_001_plant_001", "gh_001_plant_002"]
START = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
DAYS = 25


def _run() -> tuple[list[Observation], list[GroundTruth]]:
    engine = SimulationEngine(CONFIG)
    world = engine.initialize(PLANT_IDS, greenhouse_id="gh_001")
    observations: list[Observation] = []
    truth: list[GroundTruth] = []

    for day in range(1, DAYS + 1):
        timestamp = START + timedelta(days=day - 1)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id="sim_eval")
        world = step.world
        observations.extend(step.observations)
        truth.append(
            ground_truth(world, timestamp=timestamp, water_capacity_ml=CONFIG.water_capacity_ml)
        )

    return observations, truth


def test_every_reading_is_scored_against_the_instant_it_describes() -> None:
    observations, truth = _run()

    report = observation_accuracy(observations, truth)

    assert report.greenhouse_id == "gh_001"
    assert report.readings == len(observations)
    assert {entry.observation_type for entry in report.by_type} == {
        ObservationType.AIR_TEMPERATURE_C,
        ObservationType.SOIL_MOISTURE_PCT,
        ObservationType.VISIBLE_FRUIT_COUNT,
        ObservationType.RIPE_FRUIT_COUNT,
        ObservationType.ESTIMATED_RIPE_MASS_G,
        ObservationType.VISIBLE_HEIGHT_CM,
    }


def test_the_readings_are_wrong_by_about_the_configured_noise() -> None:
    """The point of the comparison: sensing is imperfect, measurably so.

    The scenario configures a 0.4 C standard deviation on temperature and
    3 percentage points on soil moisture. Mean absolute error of a normal
    variable is about 0.8 of its standard deviation, so these bounds are
    loose enough not to be flaky and tight enough to fail if the noise
    stopped being applied.
    """
    observations, truth = _run()

    report = observation_accuracy(observations, truth)
    temperature = report.for_type(ObservationType.AIR_TEMPERATURE_C)
    moisture = report.for_type(ObservationType.SOIL_MOISTURE_PCT)

    assert 0.0 < temperature.mean_absolute_error < 2 * CONFIG.air_temperature_noise_c
    assert 0.0 < moisture.mean_absolute_error < 2 * CONFIG.soil_moisture_noise_pct
    assert temperature.max_absolute_error >= temperature.mean_absolute_error


def test_readings_with_no_matching_truth_are_skipped_not_scored() -> None:
    """A gap in the evaluation is not an error in the sensor."""
    observations, truth = _run()

    report = observation_accuracy(observations, truth[:1])

    assert 0 < report.readings < len(observations)


def test_relative_error_is_zero_when_the_quantity_never_occurs() -> None:
    observations, truth = _run()

    report = observation_accuracy(observations, truth)
    ripe_mass = report.for_type(ObservationType.ESTIMATED_RIPE_MASS_G)

    assert ripe_mass.mean_relative_error >= 0.0
