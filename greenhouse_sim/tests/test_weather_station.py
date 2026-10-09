"""A weather station (P07.2): instruments outside the house that read the
weather the run is under, as the protocol's outside observations, with
their imperfections; a wind vane's readings go round the compass."""

import pytest
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.enums import ObservationType
from pydantic import ValidationError

from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.sensors.air import erred, observe, reads
from greenhouse_sim.services import sensors, weather
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.sensors import Imperfections, PointSensor

BOX = SCENARIO_REGISTRY["climate_box"]
STATION = BOX.layout.weather_station()
FIELD = shear_field("shear", air_grid(BOX))
OUTSIDE = WeatherState(
    air_temperature_c=6.5,
    relative_humidity_pct=88.0,
    wind_speed_m_s=4.2,
    wind_direction_deg=250.0,
    barometric_pressure_hpa=1008.0,
)


def _instrument(kind: SensorKind) -> PointSensor:
    return next(sensor for sensor in STATION if sensor.kind == kind)


def test_the_climate_box_has_a_weather_station_in_front_of_it() -> None:
    assert [sensor.sensor_id for sensor in STATION] == [
        "station_temperature",
        "station_humidity",
        "station_pressure",
        "station_wind_speed",
        "station_wind_direction",
    ]
    assert all(sensor.position.x < 0 for sensor in STATION)
    # The wind is read above the ridge, out of the house's lee.
    assert _instrument(SensorKind.WIND_SPEED).position.z > BOX.envelope.ridge_height


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (SensorKind.OUTSIDE_TEMPERATURE, 6.5),
        (SensorKind.OUTSIDE_HUMIDITY, 88.0),
        (SensorKind.WIND_SPEED, 4.2),
        (SensorKind.WIND_DIRECTION, 250.0),
        (SensorKind.BAROMETRIC_PRESSURE, 1008.0),
    ],
)
def test_each_instrument_reads_its_quantity_of_the_weather(kind: SensorKind, value: float) -> None:
    instrument = _instrument(kind)

    assert reads(instrument, FIELD, OUTSIDE) == value
    # Without a weather, it reads nothing; the air inside is not its.
    assert reads(instrument, FIELD) is None


def test_a_wind_vanes_reading_goes_round_the_compass() -> None:
    vane = _instrument(SensorKind.WIND_DIRECTION).model_copy(
        update={"imperfections": Imperfections(bias=5.0)}
    )

    assert erred(vane, 357.0, 0.0, 0, seed=1) == (2.0, False)
    assert erred(vane, 100.0, 0.0, 0, seed=1) == (105.0, False)


def test_its_readings_are_the_protocols_outside_observations() -> None:
    observed = sensors.observations("climate_box", until_s=120)
    outside = [o for o in observed.observations if o.sensor_id in {s.sensor_id for s in STATION}]

    assert check_observations(observed.observations) == []
    assert {o.observation_type for o in outside} == {
        ObservationType.OUTSIDE_AIR_TEMPERATURE_C,
        ObservationType.OUTSIDE_RELATIVE_HUMIDITY_PCT,
        ObservationType.OUTSIDE_WIND_SPEED_M_S,
        ObservationType.OUTSIDE_WIND_DIRECTION_DEG,
        ObservationType.OUTSIDE_BAROMETRIC_PRESSURE_HPA,
    }
    assert len(outside) == len(STATION) * 3
    freshness = {f.sensor_id: f.state for f in observed.freshness}
    assert {freshness[s.sensor_id] for s in STATION} == {"fresh"}


def test_clean_its_readings_are_the_weather_the_run_is_under() -> None:
    clean = sensors.observations("climate_box", until_s=600, clean=True, weather="cold_spring_day")
    readings = {
        (o.sensor_id, o.timestamp): o.value
        for o in clean.observations
        if o.sensor_id == "station_temperature"
    }

    for (_, taken), value in readings.items():
        seconds = (taken - clean.start).total_seconds()
        outside = weather.at_a_moment("climate_box", seconds, "cold_spring_day").weather
        assert value == pytest.approx(outside.air_temperature_c)
    # Cooling towards the spring day's dawn.
    values = list(readings.values())
    assert values == sorted(values, reverse=True)


def test_its_truth_is_the_weather_and_its_readings_err_about_it() -> None:
    observed = sensors.observations("climate_box", until_s=3600, weather="windy_autumn_day")
    truth = sensors.truth("climate_box", until_s=3600, weather="windy_autumn_day")
    speed = next(t for t in truth.sensors if t.sensor_id == "station_wind_speed")
    readings = [o.value for o in observed.observations if o.sensor_id == "station_wind_speed"]

    assert speed.observation_type == ObservationType.OUTSIDE_WIND_SPEED_M_S
    assert speed.unit == "m/s"
    errors = [reading - true for reading, true in zip(readings, speed.values, strict=True) if true]
    assert len(errors) == 61
    assert max(abs(error) for error in errors) < 4 * 0.2 + 0.05
    assert any(error != 0 for error in errors)


def test_a_weather_station_stands_outside_the_house() -> None:
    inside = _instrument(SensorKind.OUTSIDE_TEMPERATURE).model_copy(
        update={"position": Vector3(x=6.0, y=3.2, z=1.5)}
    )

    with pytest.raises(ValidationError, match="weather station stands outside the house"):
        BOX.model_validate(BOX.model_dump() | {"layout": Layout(sensors=[inside]).model_dump()})


def test_observing_without_a_weather_gives_the_station_nothing() -> None:
    observed = observe(
        STATION,
        lambda _: FIELD,
        120,
        start=BOX.run_start(),
        greenhouse_id="climate_box",
        run_id="run",
    )

    assert observed == []
