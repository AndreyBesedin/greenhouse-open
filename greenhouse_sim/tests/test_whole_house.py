"""The house's air as one well-mixed volume (P07.3): it follows the grid
run's mean, closes its energy and water budgets, follows the weather, and
runs a day in well under a second."""

import json
import time
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import WholeHouse, grid_mean
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import _climate_day, air_grid
from greenhouse_sim.weather.presets import COLD_SPRING_DAY
from greenhouse_sim.world.equipment import Heater

BOX = SCENARIO_REGISTRY["climate_box"]
DAY_S = 86_400.0
# How closely the whole house follows the grid run's mean, as measured on
# the climate box: in a shut house its temperature to a few tenths of a
# degree; with condensation on the cold glass, which only the grid has
# beside the glass, its water to a gram and a half a kilogram; with a vent
# open, which on the grid exchanges the cooler air beside it, to three and a
# half degrees, on a still night, when the vent is most of what the heater
# loses.
SHUT_TEMPERATURE_C = 0.3
CONDENSING_WATER_G_KG = 1.5
VENTING_TEMPERATURE_C = 3.5


def _run(
    levels: tuple[tuple[str, float], ...] = (), openings: tuple[tuple[str, float], ...] = ()
) -> ClimateRun:
    return _climate_day("climate_box", "default", "default", levels, openings, ()).run


@pytest.mark.parametrize(
    "levels",
    [(), (("heater", 1.0),), (("dehumidifier", 1.0),), (("fan", 1.0), ("heater", 1.0))],
    ids=["nothing", "heater", "dehumidifier", "heater and fan"],
)
def test_in_a_shut_house_it_follows_the_grid_runs_mean(
    levels: tuple[tuple[str, float], ...],
) -> None:
    run = _run(levels)
    house = WholeHouse(run)

    for moment in (1800.0, 3600.0):
        mixed, mean = house.air_at(moment), grid_mean(run, moment)
        assert mixed.temperature_c == pytest.approx(mean.temperature_c, abs=SHUT_TEMPERATURE_C)
        assert mixed.humidity_g_kg == pytest.approx(mean.humidity_g_kg, abs=CONDENSING_WATER_G_KG)
        assert mixed.co2_ppm == pytest.approx(mean.co2_ppm)
        # What equipment takes, it takes alike.
        assert mixed.removed_kg == pytest.approx(mean.removed_kg, rel=1e-6)


def test_with_a_vent_open_it_follows_the_grid_runs_mean_more_loosely() -> None:
    run = _run((("heater", 1.0),), (("roof_vent", 1.0),))
    mixed, mean = WholeHouse(run).air_at(3600.0), grid_mean(run, 3600.0)

    assert mixed.temperature_c == pytest.approx(mean.temperature_c, abs=VENTING_TEMPERATURE_C)
    # The well-mixed air loses more of the heater's heat through the vent.
    assert mixed.temperature_c < mean.temperature_c


def _shut(levels: dict[str, float], weather: object = None) -> WholeHouse:
    config = BOX if weather is None else BOX.model_copy(update={"weather": weather})
    return WholeHouse(
        ClimateRun(
            base=config.airflow,
            equipment=config.layout.equipment,
            schedule=Schedule.from_start(levels),
            settings=config.climate.model_copy(update={"glazing_u_w_m2k": 0.0}),
            grid=air_grid(config),
            solid=cfd.geometry("climate_box").solid(),
            weather=config.run_weather(),
        )
    )


def test_shut_off_from_the_outside_the_heat_it_gains_is_the_heaters() -> None:
    house = _shut({"heater": 1.0})
    heater = next(piece for piece in BOX.layout.equipment if isinstance(piece, Heater))
    start, later = house.air_at(0.0), house.air_at(3600.0)

    gained = house.heat_j(later) - house.heat_j(start)
    assert gained == pytest.approx(heater.power_w * 3600.0, rel=1e-9)


def test_shut_off_from_the_outside_the_water_it_loses_is_removed_or_condensed() -> None:
    house = _shut({"dehumidifier": 1.0})
    start, later = house.air_at(0.0), house.air_at(3600.0)

    lost = house.water_kg(start) - house.water_kg(later)
    assert lost == pytest.approx(later.removed_kg + later.condensed_kg, rel=1e-9)
    assert later.removed_kg > 0


def test_it_follows_the_weather_through_a_day() -> None:
    house = _climate_day("climate_box", "default", "cold_spring_day", (), (), ()).house
    dawn, afternoon = house.air_at(6.5 * 3600), house.air_at(15.5 * 3600)

    # Shut and unheated, the house follows the outside through its glass.
    assert dawn.temperature_c < afternoon.temperature_c
    assert dawn.temperature_c == pytest.approx(COLD_SPRING_DAY.coldest_c, abs=1.0)
    assert afternoon.temperature_c == pytest.approx(COLD_SPRING_DAY.warmest_c, abs=1.0)


def test_it_runs_a_day_in_well_under_a_second() -> None:
    house = WholeHouse(_run((("heater", 1.0),)))
    house.air_at(60.0)

    started = time.perf_counter()
    house.air_at(DAY_S)
    assert time.perf_counter() - started < 1.0


def test_the_api_serves_the_houses_air_beside_the_run_all_off() -> None:
    response = respond("GET", "/api/scenarios/climate_box/climate/house?set=heater:1&t=600")
    body = json.loads(json.dumps(response.body))

    assert response.status == HTTPStatus.OK
    assert body["times_s"] == [60.0 * minute for minute in range(11)]
    heated, unheated = body["controlled"], body["all_off"]
    assert heated["temperature_c"][0] == unheated["temperature_c"][0] == 16.0
    assert heated["temperature_c"][-1] > unheated["temperature_c"][-1] + 5.0
    assert len(heated["humidity_pct"]) == len(heated["co2_ppm"]) == 11


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/scenarios/climate_box/climate/house?t=90000", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/sensor_lab/climate/house", HTTPStatus.NOT_FOUND),
        ("/api/scenarios/climate_box/climate/house?weather=foggy", HTTPStatus.NOT_FOUND),
    ],
)
def test_the_api_refuses_the_houses_air_as_it_refuses_the_climate(
    path: str, status: HTTPStatus
) -> None:
    assert respond("GET", path).status == status
