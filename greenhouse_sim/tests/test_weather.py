"""The weather outside (P07.1): constant, or a series interpolated between
its records, the wind as a vector, read on a run's clock, and what a
climate run exchanges with."""

import json
import math
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.weather.sources import ConstantWeather, RunWeather, WeatherSeries
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.site import DEFAULT_SITE

DAWN = datetime(2026, 4, 1, 4, tzinfo=UTC)
HOUR = timedelta(hours=1)
COLD = WeatherState(
    air_temperature_c=4.0,
    relative_humidity_pct=90.0,
    co2_ppm=420.0,
    wind_speed_m_s=2.0,
    wind_direction_deg=200.0,
    barometric_pressure_hpa=1010.0,
    global_radiation_w_m2=0.0,
    cloud_cover_pct=80.0,
)
MILD = WeatherState(
    air_temperature_c=14.0,
    relative_humidity_pct=60.0,
    co2_ppm=400.0,
    wind_speed_m_s=2.0,
    wind_direction_deg=220.0,
    barometric_pressure_hpa=1014.0,
    global_radiation_w_m2=300.0,
    cloud_cover_pct=40.0,
)
BOX = SCENARIO_REGISTRY["climate_box"]


def _wind(speed: float, direction: float) -> WeatherState:
    return COLD.model_copy(update={"wind_speed_m_s": speed, "wind_direction_deg": direction})


def test_constant_weather_is_the_same_at_every_moment() -> None:
    source = ConstantWeather(air_temperature_c=8.0).source(DEFAULT_SITE)

    assert source.at(DAWN) == source.at(DAWN + 1000 * HOUR)
    assert source.at(DAWN).air_temperature_c == 8.0


def test_constant_weathers_pressure_is_the_sites_unless_given() -> None:
    high = DEFAULT_SITE.model_copy(update={"elevation_m": 1000.0})

    assert ConstantWeather().state(high).barometric_pressure_hpa == pytest.approx(
        high.standard_pressure_hpa()
    )
    given = ConstantWeather(barometric_pressure_hpa=990.0)
    assert given.state(high).barometric_pressure_hpa == 990.0


def test_every_scenario_keeps_its_outside_as_constant_weather() -> None:
    # The climate box's cold, damp night; the others' mild default.
    assert BOX.weather == ConstantWeather(air_temperature_c=8.0, relative_humidity_pct=90.0)
    for config in SCENARIO_REGISTRY.values():
        assert isinstance(config.weather, ConstantWeather)
        assert config.weather.co2_ppm == 420.0


def test_a_series_is_its_record_at_a_records_moment() -> None:
    series = WeatherSeries([(DAWN, COLD), (DAWN + HOUR, MILD)])

    assert series.at(DAWN) == COLD
    assert series.at(DAWN + HOUR) == MILD


def test_a_series_interpolates_linearly_between_its_records() -> None:
    series = WeatherSeries([(DAWN, COLD), (DAWN + HOUR, MILD)])

    quarter = series.at(DAWN + HOUR / 4)

    assert quarter.air_temperature_c == pytest.approx(6.5)
    assert quarter.relative_humidity_pct == pytest.approx(82.5)
    assert quarter.co2_ppm == pytest.approx(415.0)
    assert quarter.barometric_pressure_hpa == pytest.approx(1011.0)
    assert quarter.global_radiation_w_m2 == pytest.approx(75.0)
    assert quarter.cloud_cover_pct == pytest.approx(70.0)


def test_a_series_interpolates_between_the_records_either_side() -> None:
    series = WeatherSeries([(DAWN, COLD), (DAWN + HOUR, MILD), (DAWN + 3 * HOUR, COLD)])

    assert series.at(DAWN + 2 * HOUR).air_temperature_c == pytest.approx(9.0)


def test_the_wind_turns_through_north_not_south() -> None:
    series = WeatherSeries([(DAWN, _wind(5.0, 350.0)), (DAWN + HOUR, _wind(5.0, 10.0))])

    middle = series.at(DAWN + HOUR / 2)

    assert min(middle.wind_direction_deg, 360.0 - middle.wind_direction_deg) < 1e-9
    # The mean of the two vectors, a little slacker than either.
    assert middle.wind_speed_m_s == pytest.approx(5.0 * math.cos(math.radians(10.0)))
    assert series.at(DAWN + HOUR / 4).wind_direction_deg == pytest.approx(355.0, abs=0.1)


def test_the_wind_veers_through_the_bearings_between() -> None:
    series = WeatherSeries([(DAWN, _wind(4.0, 80.0)), (DAWN + HOUR, _wind(4.0, 100.0))])

    assert series.at(DAWN + HOUR / 2).wind_direction_deg == pytest.approx(90.0)


def test_opposite_winds_meet_in_a_calm_that_keeps_the_earlier_direction() -> None:
    series = WeatherSeries([(DAWN, _wind(3.0, 90.0)), (DAWN + HOUR, _wind(3.0, 270.0))])

    middle = series.at(DAWN + HOUR / 2)

    assert middle.wind_speed_m_s == 0.0
    assert middle.wind_direction_deg == 90.0


def test_a_series_knows_nothing_beyond_its_records() -> None:
    series = WeatherSeries([(DAWN, COLD), (DAWN + HOUR, MILD)])

    with pytest.raises(ValueError, match="known from"):
        series.at(DAWN - timedelta(seconds=1))
    with pytest.raises(ValueError, match="known from"):
        series.at(DAWN + HOUR + timedelta(seconds=1))
    with pytest.raises(ValueError, match="time zone"):
        series.at(DAWN.replace(tzinfo=None))


@pytest.mark.parametrize(
    ("records", "refusal"),
    [
        ([], "at least one record"),
        ([(DAWN.replace(tzinfo=None), COLD)], "no time zone"),
        ([(DAWN, COLD), (DAWN, MILD)], "in order of time"),
        ([(DAWN + HOUR, COLD), (DAWN, MILD)], "in order of time"),
    ],
)
def test_a_series_out_of_order_or_without_a_time_zone_is_refused(
    records: list[tuple[datetime, WeatherState]], refusal: str
) -> None:
    with pytest.raises(ValueError, match=refusal):
        WeatherSeries(records)


def test_a_run_reads_the_weather_on_its_own_clock() -> None:
    series = WeatherSeries([(DAWN, COLD), (DAWN + HOUR, MILD)])
    run = RunWeather(series, DAWN)

    assert run.at(0.0) == COLD
    assert run.at(1800.0) == series.at(DAWN + HOUR / 2)


def test_the_wind_blows_to_the_bearing_opposite_the_one_it_comes_from() -> None:
    # By default x is east and y north: a south-westerly blows north-east.
    south_westerly = _wind(4.0, 225.0).wind_m_s(DEFAULT_SITE)
    northerly = _wind(3.0, 0.0).wind_m_s(DEFAULT_SITE)

    half = 4.0 / math.sqrt(2.0)
    assert (south_westerly.x, south_westerly.y) == pytest.approx((half, half))
    assert (northerly.x, northerly.y) == pytest.approx((0.0, -3.0), abs=1e-12)


def _box_run(weather: RunWeather) -> ClimateRun:
    return ClimateRun(
        base=BOX.airflow,
        equipment=BOX.layout.equipment,
        schedule=Schedule.from_start({}),
        settings=BOX.climate,
        grid=air_grid(BOX),
        solid=cfd.geometry("climate_box").solid(),
        weather=weather,
    )


def test_a_run_under_a_steady_series_is_its_run_under_constant_weather() -> None:
    outside = BOX.weather.state(BOX.site)
    start = BOX.run_start()
    steady = WeatherSeries([(start, outside), (start + HOUR, outside)])

    under_series = _box_run(RunWeather(steady, start)).air_at(600)
    under_constant = _box_run(BOX.run_weather()).air_at(600)

    np.testing.assert_array_equal(under_series.temperature, under_constant.temperature)
    np.testing.assert_array_equal(under_series.humidity, under_constant.humidity)


def test_a_run_follows_the_outside_as_it_changes() -> None:
    outside = BOX.weather.state(BOX.site)
    start = BOX.run_start()
    warming = WeatherSeries(
        [(start, outside), (start + HOUR, outside.model_copy(update={"air_temperature_c": 28.0}))]
    )
    solid = cfd.geometry("climate_box").solid()

    warmed = _box_run(RunWeather(warming, start)).temperature_at(3600)[~solid].mean()
    steady = _box_run(BOX.run_weather()).temperature_at(3600)[~solid].mean()

    assert warmed > steady + 1.0


def test_the_api_serves_a_scenarios_site_and_weather_at_a_moment() -> None:
    response = respond("GET", "/api/scenarios/tomato_compartment/weather?t=600")
    body = json.loads(json.dumps(response.body))

    assert response.status == HTTPStatus.OK
    assert body["site"]["time_zone"] == "Europe/Amsterdam"
    assert body["moment"] == "2025-12-31T23:10:00Z"
    assert body["weather"]["wind_direction_deg"] == 225.0
    assert body["weather"]["barometric_pressure_hpa"] == pytest.approx(1013.25)
    assert body["wind_m_s"]["x"] == pytest.approx(body["wind_m_s"]["y"])


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/scenarios/climate_box/weather?t=4000", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/climate_box/weather?t=soon", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/nowhere/weather", HTTPStatus.NOT_FOUND),
    ],
)
def test_the_api_refuses_a_moment_outside_a_run_or_an_unknown_scenario(
    path: str, status: HTTPStatus
) -> None:
    assert respond("GET", path).status == status
