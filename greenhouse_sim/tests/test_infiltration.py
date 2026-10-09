"""A shut house leaks (P07.5): a share of its air an hour, more in a wind,
exchanged with the outside's through the cells against the walls and roof,
with its heat, water and CO₂; with no path for air, no air is exchanged."""

import math

import numpy as np
import pytest

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.projection import conserving, face_flows
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.climate.transport import Transport
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import _climate_day
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.weather.sources import ConstantWeather, RunWeather

BOX = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(BOX)
SOLID = cfd.geometry("climate_box").solid()
AIR = ~SOLID
NX, NY, NZ = GRID.shape
HOUR_S = 3600.0
# Its glass passing nothing, so that only air carries anything in or out.
OPAQUE = BOX.climate.model_copy(update={"glazing_u_w_m2k": 0.0})
SEALED = OPAQUE.model_copy(update={"infiltration_per_h": 0.0, "infiltration_per_h_per_m_s": 0.0})
# Warm and dry outside: nothing condenses, and every path shows.
DRY = ConstantWeather(air_temperature_c=16.0, relative_humidity_pct=30.0, co2_ppm=400.0)


def _run(settings: ClimateSettings, weather: ConstantWeather = DRY) -> ClimateRun:
    return ClimateRun(
        base=BOX.airflow,
        equipment=BOX.layout.equipment,
        schedule=Schedule.from_start({}),
        settings=settings.model_copy(update={"start_co2_ppm": 800.0}),
        grid=GRID,
        solid=SOLID,
        weather=RunWeather(weather.source(BOX.site), BOX.run_start()),
    )


def test_a_house_leaks_a_quarter_of_its_air_an_hour_and_more_in_a_wind() -> None:
    settings = BOX.climate

    assert settings.infiltration_per_s(0.0) * HOUR_S == pytest.approx(0.25)
    assert settings.infiltration_per_s(4.0) * HOUR_S == pytest.approx(0.65)


def test_its_leaks_are_spread_over_the_air_against_the_walls_and_roof() -> None:
    flows = conserving(face_flows(GRID, np.zeros((NZ, NY, NX, 3)), SOLID), SOLID)
    transport = Transport(GRID, flows, SOLID, BOX.climate)
    leaks = transport.leaks_m3_s(wind_m_s=0.0)
    volume = float(AIR.sum()) * transport.cell_volume_m3()

    assert float(leaks.sum()) == pytest.approx(0.25 * volume / HOUR_S)
    # Nothing leaks in the middle of the house, or into a solid cell.
    assert leaks[NZ // 2, NY // 2, NX // 2] == 0.0
    assert (leaks[SOLID] == 0.0).all()
    # A corner cell, against two walls and the roof, leaks more than one
    # against the roof alone.
    assert leaks[-1, 0, 0] > leaks[-1, NY // 2, NX // 2] > 0.0


def test_with_no_path_for_air_the_house_keeps_its_water_and_co2() -> None:
    sealed = _run(SEALED).air_at(1800.0)
    start = _run(SEALED).air_at(0.0)

    np.testing.assert_allclose(sealed.humidity[AIR], start.humidity[AIR], rtol=1e-12)
    np.testing.assert_allclose(sealed.co2[AIR], 800.0, rtol=1e-12)
    # And so does the whole house.
    house = WholeHouse(_run(SEALED))
    assert house.air_at(1800.0).humidity_g_kg == pytest.approx(house.air_at(0.0).humidity_g_kg)
    assert house.air_at(1800.0).co2_ppm == pytest.approx(800.0)


def test_dry_outside_air_dries_a_shut_house_through_its_gaps() -> None:
    leaky, sealed = _run(OPAQUE).air_at(1800.0), _run(SEALED).air_at(1800.0)

    assert leaky.humidity[AIR].mean() < sealed.humidity[AIR].mean() - 0.1
    # A quarter of its air an hour: half an hour draws 47 ppm of its 400 out.
    assert leaky.co2[AIR].mean() < 800.0 - 40.0


def test_the_whole_house_exchanges_its_air_at_the_rate_it_leaks() -> None:
    house = WholeHouse(_run(OPAQUE))
    start, later = house.air_at(0.0), house.air_at(HOUR_S)
    outside_water = float(humidity_ratio_g_kg(16.0, 30.0))

    # Well mixed and leaking a quarter of its air an hour, its CO2 and its
    # water relax towards the outside's as e^-0.25 in that hour.
    kept = math.exp(-0.25)
    assert later.co2_ppm - 400.0 == pytest.approx((800.0 - 400.0) * kept)
    assert later.humidity_g_kg - outside_water == pytest.approx(
        (start.humidity_g_kg - outside_water) * kept
    )


def test_the_grid_leaks_as_the_whole_house_does() -> None:
    run = _run(OPAQUE)
    grid_co2 = float(run.air_at(HOUR_S).co2[AIR].mean())

    assert grid_co2 == pytest.approx(WholeHouse(run).air_at(HOUR_S).co2_ppm, abs=5.0)


def test_a_house_leaks_faster_in_a_wind() -> None:
    windy = DRY.model_copy(update={"wind_speed_m_s": 8.0})

    calm_co2 = float(_run(OPAQUE).air_at(1800.0).co2[AIR].mean())
    windy_co2 = float(_run(OPAQUE, windy).air_at(1800.0).co2[AIR].mean())
    assert windy_co2 < calm_co2 - 50.0


def test_opening_a_vent_under_dry_outside_air_dries_the_house() -> None:
    shut = _climate_day("climate_box", "default", "cold_spring_day", (), (), ()).run
    venting = _climate_day(
        "climate_box", "default", "cold_spring_day", (), (("roof_vent", 1.0),), ()
    ).run

    assert (
        venting.air_at(1800.0).humidity[AIR].mean() < shut.air_at(1800.0).humidity[AIR].mean() - 0.5
    )
