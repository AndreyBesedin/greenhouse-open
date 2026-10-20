"""The reference greenhouse's sensors through its season: a fault in one is
a fault a consumer can find, and still a sensor's, not a reading tens of
degrees off by June. Its back thermometer drifted 0.01 °C an hour from the
run's start, which over 120 days read 42 to 58 °C in a house at 15 to
31 °C (#247)."""

from typing import Final

from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world.sensors import PointSensor

REFERENCE: Final = SCENARIO_REGISTRY["reference_greenhouse"]
HOUR_S: Final = 3600.0
# How far a thermometer of the reference house may read from the air by its
# season's end, its bias and its drift together, in °C: enough for a fault a
# consumer finds against the sensor beside it, not a reading that is no
# longer of the house.
MOST_SEASON_ERROR_C: Final = 5.0
# How far its faulty one reads by then at least, so that the fault is there
# to find.
LEAST_FAULT_C: Final = 1.0


def _errors_by_season_end() -> dict[str, float]:
    """Each thermometer's error at the run's end: its bias, and the drift it
    has gathered since the run's start."""
    hours = REFERENCE.run_length_s() / HOUR_S
    return {
        sensor.sensor_id: sensor.imperfections.bias + sensor.imperfections.drift_per_hour * hours
        for sensor in REFERENCE.layout.sensors
        if isinstance(sensor, PointSensor) and sensor.kind == SensorKind.TEMPERATURE
    }


def test_a_reference_thermometer_errs_by_a_few_degrees_by_the_seasons_end_at_most() -> None:
    errors = _errors_by_season_end()

    assert set(errors) >= {"temperature_front", "temperature_back"}
    assert all(abs(error) <= MOST_SEASON_ERROR_C for error in errors.values()), errors


def test_its_back_thermometer_drifts_far_enough_to_be_found() -> None:
    errors = _errors_by_season_end()

    assert errors["temperature_back"] >= LEAST_FAULT_C
    assert errors["temperature_front"] == 0.0
