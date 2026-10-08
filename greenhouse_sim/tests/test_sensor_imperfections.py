"""How sensors err (P06.3): noise, quantization, bias, linear drift, dropout
and latency, each as configured, seeded per sensor and sample, so a run errs
the same way every time it is asked for."""

import math
import statistics
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from greenhouse_protocol.enums import ObservationQuality

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.field import EnvironmentField, FieldGrid
from greenhouse_sim.sensors.air import observe
from greenhouse_sim.services import sensors
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.sensors import Imperfections, PointSensor

START = datetime(2026, 1, 1, tzinfo=UTC)
GRID = FieldGrid.over(Vector3(x=0, y=0, z=0), Vector3(x=2, y=2, z=2), 1.0)
TRUE_C = 20.0
HUMID_PCT = 99.0


def _steady(temperature: float = TRUE_C, humidity: float = HUMID_PCT) -> EnvironmentField:
    shape = (2, 2, 2)
    return EnvironmentField(
        field_id="steady",
        source="test",
        grid=GRID,
        time_s=0.0,
        channels={
            AirQuantity.VELOCITY: np.zeros((*shape, 3)),
            AirQuantity.TEMPERATURE: np.full(shape, temperature),
            AirQuantity.HUMIDITY: np.full(shape, humidity),
        },
    )


def _sensor(
    kind: SensorKind = SensorKind.TEMPERATURE, cadence_s: float = 1.0, **how: float
) -> PointSensor:
    return PointSensor(
        sensor_id=f"{kind.value}_1",
        kind=kind,
        position=Vector3(x=1, y=1, z=1),
        cadence_s=cadence_s,
        imperfections=Imperfections(**how),
    )


def _readings(sensor: PointSensor, until_s: float = 3600, seed: int = 7) -> list[float]:
    observed = observe(
        [sensor],
        lambda _: _steady(),
        until_s,
        start=START,
        greenhouse_id="g",
        run_id="r",
        seed=seed,
    )
    return [o.value for o in observed]


def test_noise_has_the_configured_spread_around_the_truth() -> None:
    readings = _readings(_sensor(noise_sd=0.3))

    assert statistics.mean(readings) == pytest.approx(TRUE_C, abs=3 * 0.3 / math.sqrt(3601))
    assert statistics.stdev(readings) == pytest.approx(0.3, rel=0.05)


def test_readings_are_rounded_to_the_quantization_step() -> None:
    readings = _readings(_sensor(noise_sd=0.3, quantization=0.1), until_s=120)

    assert all(round(value * 10) == pytest.approx(value * 10) for value in readings)
    assert all(len(repr(value).partition(".")[2]) <= 1 for value in readings)


def test_bias_adds_and_drift_grows_linearly_with_time() -> None:
    readings = _readings(_sensor(cadence_s=900, bias=0.5, drift_per_hour=0.8))

    assert readings == pytest.approx([20.5, 20.7, 20.9, 21.1, 21.3])


def test_dropout_loses_the_configured_share_of_samples() -> None:
    kept = len(_readings(_sensor(dropout=0.2)))

    assert kept / 3601 == pytest.approx(0.8, abs=3 * math.sqrt(0.2 * 0.8 / 3601))


def test_a_reading_is_delivered_its_latency_after_it_was_taken() -> None:
    sensor = _sensor(cadence_s=60, latency_s=90)

    observed = observe(
        [sensor], lambda _: _steady(), 600, start=START, greenhouse_id="g", run_id="r"
    )

    # Taken every minute; by ten minutes, those taken by 8.5 have arrived.
    assert [o.timestamp for o in observed] == [START + timedelta(minutes=m) for m in range(9)]
    assert all(o.delivered_at == o.timestamp + timedelta(seconds=90) for o in observed)


def test_a_reading_beyond_the_instruments_range_is_held_there_and_flagged() -> None:
    sensor = _sensor(SensorKind.HUMIDITY, cadence_s=60, noise_sd=2.0)

    observed = observe(
        [sensor], lambda _: _steady(), 3600, start=START, greenhouse_id="g", run_id="r"
    )
    held = [o for o in observed if ObservationQuality.CLIPPED in o.quality]

    assert held
    assert all(o.value == 100.0 for o in held)
    assert max(o.value for o in observed) == 100.0
    assert all(o.value < 100.0 for o in observed if o not in held)


def test_the_same_seed_errs_the_same_way_however_the_run_is_asked_for() -> None:
    sensor = _sensor(noise_sd=0.3, dropout=0.2)

    whole = _readings(sensor, until_s=600)
    first = _readings(sensor, until_s=300)

    assert _readings(sensor, until_s=600) == whole
    assert whole[: len(first)] == first
    assert _readings(sensor, until_s=600, seed=8) != whole


def test_two_sensors_never_share_their_noise_and_one_changes_no_others() -> None:
    a = _sensor(noise_sd=0.3)
    b = a.model_copy(update={"sensor_id": "temperature_2"})

    alone = observe(
        [a], lambda _: _steady(), 60, start=START, greenhouse_id="g", run_id="r", seed=7
    )
    both = observe(
        [a, b], lambda _: _steady(), 60, start=START, greenhouse_id="g", run_id="r", seed=7
    )

    assert [o.value for o in both if o.sensor_id == a.sensor_id] == [o.value for o in alone]
    assert [o.value for o in both if o.sensor_id == b.sensor_id] != [o.value for o in alone]


def test_turning_noise_on_moves_no_dropout() -> None:
    quiet = observe(
        [_sensor(dropout=0.3)], lambda _: _steady(), 300, start=START, greenhouse_id="g", run_id="r"
    )
    noisy = observe(
        [_sensor(dropout=0.3, noise_sd=0.5)],
        lambda _: _steady(),
        300,
        start=START,
        greenhouse_id="g",
        run_id="r",
    )

    assert [o.timestamp for o in noisy] == [o.timestamp for o in quiet]


def test_clean_readings_are_the_truth_for_qa() -> None:
    observed = sensors.observations("climate_box", levels={"heater": 1.0}, until_s=600, clean=True)
    truth = {
        t.sensor_id: t
        for t in sensors.truth("climate_box", levels={"heater": 1.0}, until_s=600).sensors
    }

    back = [o.value for o in observed.observations if o.sensor_id == "temperature_back"]
    assert back == [value for value in truth["temperature_back"].values]


def test_the_climate_boxs_imperfect_sensor_errs_as_configured() -> None:
    observed = sensors.observations("climate_box", levels={"heater": 1.0}, until_s=600).observations
    truth = sensors.truth("climate_box", levels={"heater": 1.0}, until_s=600).sensors
    back = [o for o in observed if o.sensor_id == "temperature_back"]
    true_back = dict(
        zip(
            next(t for t in truth if t.sensor_id == "temperature_back").times_s,
            next(t for t in truth if t.sensor_id == "temperature_back").values,
            strict=True,
        )
    )

    # Late by 30 s: the reading taken at ten minutes is not in yet.
    assert all(o.delivered_at == o.timestamp + timedelta(seconds=30) for o in back)
    assert back[-1].timestamp < START + timedelta(minutes=10)
    # Biased by 0.5 °C, drifting 0.6 °C an hour, within its noise.
    for o in back:
        moment = (o.timestamp - START).total_seconds()
        expected = (true_back[moment] or 0) + 0.5 + 0.6 * moment / 3600
        assert o.value == pytest.approx(expected, abs=4 * 0.2 + 0.05)
