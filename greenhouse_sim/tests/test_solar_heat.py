"""The sun's heat (P08.8): of the light reaching the floor, the air above it
takes 70% as heat, on the grid and in the whole house alike; nothing at
night; and a shut house on a clear day warms well above the outside."""

import json
from http import HTTPStatus

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.run import SOLAR_HEAT_SHARE, ClimateRun
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import _climate_day
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.sunlight import plant_light

LAB = SCENARIO_REGISTRY["solar_lab"]
# Solar noon in the solar lab's run, on the site's clock, and an hour after.
NOON_S = 12 * 3600 + 50 * 60
AFTERNOON_S = NOON_S + 3600


def _lab_run(*, sunlit: bool) -> ClimateRun:
    grid = air_grid(LAB)
    return ClimateRun(
        base=LAB.airflow,
        equipment=LAB.layout.equipment,
        schedule=Schedule.from_start({}),
        settings=LAB.climate,
        grid=grid,
        solid=cfd.geometry("solar_lab").solid(),
        weather=LAB.run_weather(),
        sunlight=plant_light("solar_lab", "default", "default").sunlight if sunlit else None,
    )


def test_the_air_above_the_floor_takes_seventy_percent_of_its_light_as_heat() -> None:
    run = _lab_run(sunlit=True)
    assert run.sunlight is not None
    floor = run.sunlight.floor_irradiance(NOON_S)
    size = run.grid.cell_size
    solid = run.solid
    # Every column has air: the crates stand on the floor, and their column's
    # heat goes to the air above them.
    columns_with_air = (~solid).any(axis=0)

    heat = run.solar_heat_w(NOON_S)

    assert heat is not None
    assert SOLAR_HEAT_SHARE == 0.7
    assert heat.sum() == pytest.approx(
        SOLAR_HEAT_SHARE * float(floor[columns_with_air].sum()) * size.x * size.y
    )
    # All of it in each column's lowest cell of air.
    lowest = (~solid).argmax(axis=0)
    in_lowest = np.zeros_like(heat)
    ys, xs = np.nonzero(columns_with_air)
    in_lowest[lowest[ys, xs], ys, xs] = heat[lowest[ys, xs], ys, xs]
    assert np.array_equal(heat, in_lowest)
    assert not heat[solid].any()
    # A clear equinox noon's light on 77 m² of floor: some 25 kW.
    assert 20_000.0 < heat.sum() < 30_000.0
    assert run.solar_heat_total_w(NOON_S) == pytest.approx(float(heat.sum()))


def test_at_night_the_sun_adds_nothing() -> None:
    run = _lab_run(sunlit=True)
    dark = _lab_run(sunlit=False)

    assert run.solar_heat_w(600.0) is None
    assert run.solar_heat_total_w(600.0) == 0.0
    np.testing.assert_array_equal(run.air_at(600.0).temperature, dark.air_at(600.0).temperature)
    assert WholeHouse(run).air_at(3600.0) == WholeHouse(dark).air_at(3600.0)


def test_a_weather_without_light_adds_nothing_by_day() -> None:
    # The climate box's own weather, constant, gives no light: its runs keep
    # every number they had before the sun.
    box = SCENARIO_REGISTRY["climate_box"]
    nx, ny, _ = air_grid(box).shape
    floor = plant_light("climate_box", "default", "default").sunlight.floor_irradiance(NOON_S)

    assert floor.shape == (ny, nx)
    assert not floor.any()


def test_the_whole_house_takes_the_grids_total() -> None:
    run = _lab_run(sunlit=True)
    dark = _lab_run(sunlit=False)
    house, unlit = WholeHouse(run), WholeHouse(dark)

    # Shut, on a clear equinox day, the house warms by noon well above the
    # outside, which is 14 °C then; without the sun it would follow it.
    outside = LAB.run_weather().at(NOON_S).air_temperature_c
    assert house.air_at(NOON_S).temperature_c > outside + 10.0
    assert unlit.air_at(NOON_S).temperature_c == pytest.approx(outside, abs=1.5)


def test_by_day_the_sun_warms_the_shut_house_on_the_grid_too() -> None:
    day = _climate_day("solar_lab", "default", "default", (), (), ())
    field = day.field("noon", AFTERNOON_S)
    house = day.house.air_at(AFTERNOON_S)
    temperature = field.channels[AirQuantity.TEMPERATURE][~day.run.solid]
    outside = LAB.run_weather().at(AFTERNOON_S).air_temperature_c

    assert temperature.mean() > outside + 10.0
    # The grid run, started from the whole house an hour and more before,
    # follows it.
    assert temperature.mean() == pytest.approx(house.temperature_c, abs=2.0)
    # Warmest low down, where the floor gives the air its heat.
    layers = [field.channels[AirQuantity.TEMPERATURE][k][~day.run.solid[k]].mean() for k in (0, 6)]
    assert layers[0] > layers[1]


def test_the_api_serves_the_sunlit_houses_air() -> None:
    response = respond("GET", f"/api/scenarios/solar_lab/climate/house?t={NOON_S}")
    weather = respond("GET", f"/api/scenarios/solar_lab/weather?t={NOON_S}")
    body = json.loads(json.dumps(response.body))
    outside = json.loads(json.dumps(weather.body))["weather"]["air_temperature_c"]

    assert response.status == HTTPStatus.OK
    assert body["controlled"]["temperature_c"][-1] > outside + 10.0
