"""The reference greenhouse's sensors through its season: a fault in one is
a fault a consumer can find, and still a sensor's, not a reading tens of
degrees off by June. Its back thermometer drifted 0.01 °C an hour from the
run's start, which over 120 days read 42 to 58 °C in a house at 15 to
31 °C (#247)."""

from typing import Final

import numpy as np

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.field import EnvironmentField
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.fields import field
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.sensors import delivered_between
from greenhouse_sim.world.sensors import PointSensor

SCENARIO: Final = "reference_greenhouse"
REFERENCE: Final = SCENARIO_REGISTRY[SCENARIO]
HOUR_S: Final = 3600.0
# How far a thermometer of the reference house may read from the air by its
# season's end, its bias and its drift together, in °C: enough for a fault a
# consumer finds against the sensor beside it, not a reading that is no
# longer of the house.
MOST_SEASON_ERROR_C: Final = 5.0
# How far its faulty one reads by then at least, so that the fault is there
# to find.
LEAST_FAULT_C: Final = 1.0
# The run's first two hours, when its sensors read the house's air cell by
# cell, as the grid run carries it from the start, and a minute in, when its
# heater has warmed the cells it blows into past 100 °C.
FROM_THE_START_S: Final = 2 * HOUR_S
HEATER_PAST_BOILING_S: Final = (60.0, 120.0)


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


def test_its_air_past_boiling_by_the_heater_keeps_a_humidity_the_air_can_have() -> None:
    # A cell the heater warmed past 100 °C used to lose more water than it
    # held, and the house's humidity cell by cell ran to ±10⁸ % (#198).
    for time_s in HEATER_PAST_BOILING_S:
        air = EnvironmentField.from_document(field(RunRequest(SCENARIO), "climate", time_s=time_s))
        temperature = air.channels[AirQuantity.TEMPERATURE]
        relative = air.channels[AirQuantity.HUMIDITY]

        assert np.nanmax(temperature) > 100.0
        assert np.all(np.isfinite(relative[np.isfinite(temperature)]))
        assert np.nanmin(relative) >= 0.0 and np.nanmax(relative) <= 100.0


def test_its_hygrometers_read_a_house_s_humidity_from_the_runs_start() -> None:
    # Through its first two hours they read 0% and then 100% for an hour
    # and more, from the grid run that ran wild (#198).
    readings, _ = delivered_between(RunRequest(SCENARIO), None, FROM_THE_START_S, 60.0)
    humidity = [r.value for r in readings if r.sensor_id in {"humidity_front", "humidity_back"}]

    assert len(humidity) >= 2 * FROM_THE_START_S / HOUR_S * 60
    assert 0.0 < min(humidity) and max(humidity) < 100.0
