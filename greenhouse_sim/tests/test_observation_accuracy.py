"""Scoring a run's sensing against what was really the case (decision 0059):
each sensor's readings against what it truly sampled, and each day's walk
through the crop against each plant as its crop model measures it."""

from datetime import UTC, datetime, timedelta

import pytest
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import GroundTruth, ground_truth
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.crop_parameters import CropWalk
from greenhouse_sim.services import sensors
from greenhouse_sim.services.crop_log import _walk, crop_records, walked_truly
from greenhouse_sim.services.crop_models import Measured
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO = "climate_box"
RUN = RunRequest(SCENARIO)
# A day and a half: the walks of its first two days, at noon.
UNTIL_S = 1.5 * DAY_S
WALK_KINDS = {
    ObservationType.VISIBLE_FRUIT_COUNT,
    ObservationType.RIPE_FRUIT_COUNT,
    ObservationType.ESTIMATED_RIPE_MASS_G,
    ObservationType.VISIBLE_HEIGHT_CM,
}
# The climate box's back temperature sensor reads 0.5 °C high, and drifts
# 0.6 °C an hour further; its front one is perfect (its layout).
BIAS_C = 0.5
DRIFT_C_PER_HOUR = 0.6


def _observed(simulator: Simulator, until_s: float, clean: bool = False) -> list[Observation]:
    """A run's observation log up to `until_s`: its sensors' readings, and
    each day's walk."""
    log = sensors.observations(simulator, RUN, until_s, clean=clean, from_s=0.0)
    walked = [
        observation
        for day in range(int(until_s // DAY_S) + 1)
        for observation in crop_records(simulator, RUN, day, log.start, log.run_id)[0]
        if observation.timestamp <= log.start + timedelta(seconds=until_s)
    ]
    return [*log.observations, *walked]


@pytest.fixture(scope="module")
def scored(simulator: Simulator) -> tuple[list[Observation], GroundTruth]:
    """The run's observation log and its truth, worked out once."""
    return _observed(simulator, UNTIL_S), ground_truth(simulator, RUN, UNTIL_S)


def test_every_reading_is_scored_against_what_it_truly_measured(
    scored: tuple[list[Observation], GroundTruth],
) -> None:
    observations, truth = scored

    report = observation_accuracy(observations, truth)

    assert report.run_id == observations[0].source.source_id
    assert report.readings == len(observations)
    kinds = {entry.observation_type for entry in report.by_type}
    assert WALK_KINDS < kinds
    assert {ObservationType.AIR_TEMPERATURE_C, ObservationType.OUTSIDE_WIND_DIRECTION_DEG} < kinds


def test_clean_sensors_and_an_exact_walk_read_the_truth() -> None:
    """Each reading is held to its own truth: a clean sensor's is its truth
    exactly, and an exact walk's within the tenth its mass and height are
    written to."""
    config = SCENARIO_REGISTRY[SCENARIO]
    exact = config.model_copy(
        update={
            "crop_walk": CropWalk(
                fruit_count_noise_probability=0.0, ripe_mass_noise_pct=0.0, height_noise_cm=0.0
            )
        }
    )
    with Simulator(Catalogue(PACKAGED.with_config(exact))) as without_errors:
        observations = _observed(without_errors, UNTIL_S, clean=True)
        report = observation_accuracy(observations, ground_truth(without_errors, RUN, UNTIL_S))

    assert report.readings == len(observations)
    for entry in report.by_type:
        written_to = 0.05 if entry.observation_type in WALK_KINDS else 0.0
        assert entry.max_absolute_error <= written_to, entry


def test_the_readings_are_wrong_by_about_their_sensors_imperfections(
    scored: tuple[list[Observation], GroundTruth],
) -> None:
    """The point of the comparison: sensing is imperfect, measurably so. The
    climate box's front temperature sensor is perfect, and its back one
    reads high, more so with every hour."""
    observations, truth = scored

    def temperature(sensor_id: str) -> float:
        of_it = [o for o in observations if o.sensor_id == sensor_id]
        return (
            observation_accuracy(of_it, truth)
            .for_type(ObservationType.AIR_TEMPERATURE_C)
            .mean_absolute_error
        )

    hours = UNTIL_S / HOUR_S
    assert temperature("temperature_front") == 0.0
    assert BIAS_C < temperature("temperature_back") < BIAS_C + DRIFT_C_PER_HOUR * hours
    wind = observation_accuracy(observations, truth).for_type(
        ObservationType.OUTSIDE_WIND_DIRECTION_DEG
    )
    # The shorter way round the compass, never more than half a turn.
    assert 0.0 < wind.max_absolute_error <= 180.0


def test_readings_with_no_true_reading_are_skipped_not_scored(
    simulator: Simulator, scored: tuple[list[Observation], GroundTruth]
) -> None:
    """A gap in the evaluation is not an error in the sensor: readings taken
    after the truth's moment, and readings of another run."""
    observations, _ = scored
    earlier = ground_truth(simulator, RUN, DAY_S / 2)

    report = observation_accuracy(observations, earlier)
    other = observation_accuracy(observations, earlier.model_copy(update={"run_id": "another"}))

    assert 0 < report.readings < len(observations)
    assert other.readings == 0


@pytest.mark.parametrize("kind", sorted(WALK_KINDS))
def test_relative_error_is_never_negative(
    scored: tuple[list[Observation], GroundTruth], kind: ObservationType
) -> None:
    """Zero, where the quantity averages zero: early in a run there is no
    ripe fruit to weigh."""
    observations, truth = scored

    entry = observation_accuracy(observations, truth).for_type(kind)

    assert entry.mean_relative_error >= 0.0


def test_the_walks_truth_is_what_an_exact_walk_records() -> None:
    """Kind by kind, as the walk writes it: a plant with fruit, some ripe,
    walked with no errors."""
    exact = SCENARIO_REGISTRY[SCENARIO].model_copy(
        update={
            "crop_walk": CropWalk(
                fruit_count_noise_probability=0.0, ripe_mass_noise_pct=0.0, height_noise_cm=0.0
            )
        }
    )
    plant = Measured(plant_id="p", fruits=7, ripe=3, ripe_mass_g=212.25, height_cm=88.04)
    source = RecordSource(type=SourceType.SIMULATION, source_id="run")
    at = datetime(2026, 1, 1, 12, tzinfo=UTC)

    walked = {o.observation_type: o.value for o in _walk(plant, exact, 4, at, source)}

    assert walked == {kind: round(value, 1) for kind, value in walked_truly(plant).items()}
