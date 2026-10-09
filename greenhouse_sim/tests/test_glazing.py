"""Heat through the glass as the wind changes it (P07.4): U from the air
films on either side, the configured one at 4 m/s; each glazed surface's
temperature and the heat it passes; and a house that a windy night cools
faster than a calm one."""

import json
from datetime import timedelta
from http import HTTPStatus

import numpy as np
import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.glazing import (
    REFERENCE_WIND_M_S,
    glazed_cells,
    glazing_at,
    glazing_u_w_m2k,
    inside_film_w_m2k,
    surface_temperature_c,
)
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import _climate_day, air_grid
from greenhouse_sim.weather.sources import ConstantWeather, RunWeather, WeatherSeries
from greenhouse_sim.weather.state import WeatherState

BOX = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(BOX)
SOLID = cfd.geometry("climate_box").solid()
SINGLE_GLASS = 6.0
NIGHT = BOX.run_weather().at(0.0)


def test_the_configured_u_is_the_glasss_in_a_moderate_wind() -> None:
    assert glazing_u_w_m2k(SINGLE_GLASS, REFERENCE_WIND_M_S) == pytest.approx(SINGLE_GLASS)


def test_wind_thins_the_outside_film_and_the_glass_passes_more() -> None:
    by_wind = [glazing_u_w_m2k(SINGLE_GLASS, wind) for wind in (0.0, 2.0, 4.0, 8.0, 15.0)]

    assert by_wind == sorted(by_wind)
    # Single glass passes about 3.4 W/m²K in still air, and 7 in a gale.
    assert by_wind[0] == pytest.approx(3.4, abs=0.05)
    assert by_wind[-1] == pytest.approx(7.3, abs=0.1)
    # Its inner film is the still air of a room's window.
    assert inside_film_w_m2k(SINGLE_GLASS) == pytest.approx(8.5, abs=0.1)


def test_glass_that_passes_nothing_passes_nothing_in_any_wind() -> None:
    assert glazing_u_w_m2k(0.0, 10.0) == 0.0
    assert surface_temperature_c(20.0, 0.0, 0.0, 10.0) == 20.0


def test_a_u_beyond_what_glass_and_the_outside_film_pass_is_refused() -> None:
    with pytest.raises(ValidationError, match="less than"):
        ClimateSettings(glazing_u_w_m2k=25.0)


def test_a_surface_lies_between_the_air_inside_and_out_nearer_the_outside_in_wind() -> None:
    calm = surface_temperature_c(20.0, 0.0, SINGLE_GLASS, 0.0)
    windy = surface_temperature_c(20.0, 0.0, SINGLE_GLASS, 10.0)

    assert 0.0 < windy < calm < 20.0
    assert surface_temperature_c(12.0, 12.0, SINGLE_GLASS, 5.0) == 12.0


def test_every_wall_and_roof_slope_is_glazed_over_the_grids_sides_and_top() -> None:
    glazed = glazed_cells(BOX.envelope, GRID, SOLID)

    assert set(glazed) == {
        "side_wall_right",
        "side_wall_left",
        "end_wall_front",
        "end_wall_back",
        "roof_1_right",
        "roof_1_left",
    }
    # Two 12 by 4 m sides, two 6.4 by 4 m ends to the eaves and the 12 by
    # 6.4 m top, but for where fixtures fill the cells against them.
    total = sum(surface.area_m2() for surface in glazed.values())
    assert 0.95 * 224.0 < total <= 224.0
    # Each roof slope is over its half of the span.
    roof = glazed["roof_1_right"].area_m2() + glazed["roof_1_left"].area_m2()
    assert glazed["roof_1_right"].area_m2() <= 12.0 * 3.2
    assert 0.8 * 12.0 * 6.4 < roof <= 12.0 * 6.4


def _uniform(temperature: float) -> np.ndarray:
    return np.where(SOLID, 0.0, temperature)


def test_no_difference_passes_no_heat_and_reversing_it_reverses_the_heat() -> None:
    glazed = glazed_cells(BOX.envelope, GRID, SOLID)
    level = glazing_at(glazed, _uniform(NIGHT.air_temperature_c), NIGHT, SINGLE_GLASS, 0.0)
    warm = glazing_at(glazed, _uniform(16.0), NIGHT, SINGLE_GLASS, 0.0)
    reversed_outside = NIGHT.model_copy(update={"air_temperature_c": 16.0})
    cold = glazing_at(glazed, _uniform(8.0), reversed_outside, SINGLE_GLASS, 0.0)

    assert all(surface.loss_w == 0.0 for surface in level.surfaces)
    for out, into in zip(warm.surfaces, cold.surfaces, strict=True):
        assert out.loss_w > 0
        assert into.loss_w == pytest.approx(-out.loss_w)


def _run(weather: ConstantWeather | WeatherSeries, levels: dict[str, float]) -> ClimateRun:
    source = weather.source(BOX.site) if isinstance(weather, ConstantWeather) else weather
    return ClimateRun(
        base=BOX.airflow,
        equipment=BOX.layout.equipment,
        schedule=Schedule.from_start(levels),
        settings=BOX.climate,
        grid=GRID,
        solid=SOLID,
        weather=RunWeather(source, BOX.run_start()),
        glazed=glazed_cells(BOX.envelope, GRID, SOLID),
    )


def test_the_surfaces_pass_what_the_glass_passes() -> None:
    run = _run(ConstantWeather(air_temperature_c=8.0), {"heater": 1.0})
    glazing = run.glazing_at(600.0)
    air = run.air_at(600.0)

    passed = sum(surface.loss_w for surface in glazing.surfaces)
    glass = run.transport_at(600.0).glass_m3_s(NIGHT.wind_speed_m_s) * 1.2 * 1005.0
    assert passed == pytest.approx(float((glass * (air.temperature - 8.0)).sum()))


def test_a_windy_night_cools_a_shut_house_faster_than_a_calm_one() -> None:
    calm = _run(ConstantWeather(air_temperature_c=8.0), {})
    windy = _run(ConstantWeather(air_temperature_c=8.0, wind_speed_m_s=8.0), {})
    air = ~SOLID

    calm_c = float(calm.air_at(600.0).temperature[air].mean())
    windy_c = float(windy.air_at(600.0).temperature[air].mean())
    assert 8.0 < windy_c < calm_c - 0.5
    # As the whole house has it too.
    assert (
        WholeHouse(windy).air_at(600.0).temperature_c
        < WholeHouse(calm).air_at(600.0).temperature_c - 0.5
    )


def test_a_cold_spell_cools_the_glass_at_once_and_the_air_more_slowly() -> None:
    start = BOX.run_start()
    night = NIGHT
    frost = night.model_copy(update={"air_temperature_c": -4.0})
    spell = WeatherSeries(
        [(start, night), (start + timedelta(minutes=10), night)]
        + [(start + timedelta(minutes=11), frost), (start + timedelta(hours=1), frost)]
    )
    run = _run(spell, {"heater": 1.0})

    before, after = run.glazing_at(600.0), run.glazing_at(660.0)
    glass = [
        b.surface_c - a.surface_c for b, a in zip(before.surfaces, after.surfaces, strict=True)
    ]
    air = [b.air_c - a.air_c for b, a in zip(before.surfaces, after.surfaces, strict=True)]
    # In that minute the glass falls by degrees, the air beside it by less.
    assert min(glass) > 3.0
    assert all(g > a for g, a in zip(glass, air, strict=True))


def test_the_climate_box_heated_settles_where_its_still_glass_passes_the_heaters_heat() -> None:
    house = _climate_day("climate_box", "default", "default", (("heater", 1.0),), (), ()).house
    still_u = glazing_u_w_m2k(SINGLE_GLASS, 0.0)

    settled = house.air_at(6 * 3600.0).temperature_c
    assert settled == pytest.approx(8.0 + 10_000.0 / (still_u * 224.0), abs=1.0)


def test_the_api_serves_the_glazing_at_a_moment() -> None:
    response = respond("GET", "/api/scenarios/climate_box/climate/glazing?set=heater:1&t=600")
    body = json.loads(json.dumps(response.body))

    assert response.status == HTTPStatus.OK
    assert body["u_w_m2k"] == pytest.approx(glazing_u_w_m2k(SINGLE_GLASS, 0.0))
    back = next(s for s in body["surfaces"] if s["surface_id"] == "end_wall_back")
    front = next(s for s in body["surfaces"] if s["surface_id"] == "end_wall_front")
    # The heater stands at the back.
    assert back["surface_c"] > front["surface_c"] > body["outside_c"]
    assert respond("GET", "/api/scenarios/sensor_lab/climate/glazing").status == 404


def test_its_weathers_wind_reaches_the_glass() -> None:
    windy = WeatherState(
        air_temperature_c=8.0,
        relative_humidity_pct=90.0,
        wind_speed_m_s=12.0,
        barometric_pressure_hpa=1013.25,
    )

    assert glazing_u_w_m2k(SINGLE_GLASS, windy.wind_speed_m_s) > SINGLE_GLASS
