"""The house's air as one well-mixed volume (P07.3): it follows the grid
run's mean, closes its energy and water budgets, follows the weather, and
runs a day in well under a second."""

import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from http import HTTPStatus
from typing import NoReturn

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import HouseAir, WholeHouse, grid_mean
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import _climate_day
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.weather.presets import COLD_SPRING_DAY
from greenhouse_sim.world.equipment import Heater

BOX = SCENARIO_REGISTRY["climate_box"]
# Its glass passing nothing, and its gaps leaking nothing.
SEALED = {"glazing_u_w_m2k": 0.0, "infiltration_per_h": 0.0, "infiltration_per_h_per_m_s": 0.0}
DAY_S = 86_400.0
# How closely the whole house follows the grid run's mean, as measured on
# the climate box: in a shut house its temperature to about half a degree,
# its heater's warm air carried along its jet, away from the glass that
# cools the grid's air beside it (#261); with condensation on the cold
# glass, which only the grid has beside the glass, its water to a gram and
# a half a kilogram; with a vent
# open, which on the grid exchanges the cooler air beside it, to three and a
# half degrees, on a still night, when the vent is most of what the heater
# loses.
SHUT_TEMPERATURE_C = 0.6
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
            settings=config.climate.model_copy(update=SEALED),
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

    # Shut and unheated, the house follows the outside through its glass,
    # before dawn; by day the sun, low in January and half clouded, warms it
    # a little above (P08.8).
    assert dawn.temperature_c < afternoon.temperature_c
    assert dawn.temperature_c == pytest.approx(COLD_SPRING_DAY.coldest_c, abs=1.0)
    assert (
        COLD_SPRING_DAY.warmest_c + 1.0 < afternoon.temperature_c < COLD_SPRING_DAY.warmest_c + 3.0
    )


def test_requests_at_once_work_the_house_out_one_at_a_time() -> None:
    # A viewer asks for several moments of one kept run at once: each waits
    # for the others, and all find the air a single request would.
    house = WholeHouse(_run((("heater", 1.0),)))
    times = [3600.0 * hour for hour in range(1, 9)]

    with ThreadPoolExecutor(max_workers=4) as pool:
        together = list(pool.map(house.air_at, times))

    alone = WholeHouse(_run((("heater", 1.0),)))
    assert together == [alone.air_at(time_s) for time_s in times]


def test_it_takes_over_anothers_air_up_to_where_their_schedules_differ() -> None:
    hour = 3600.0
    heated = ((2 * hour, "heater", 1.0),)
    first = WholeHouse(_run())
    first.air_at(4 * hour)
    second = WholeHouse(_climate_day("climate_box", "default", "default", (), (), heated).run)

    second.carry_on_from(first)

    assert second._kept.keys() == {m for m in first._kept if m <= 2 * hour}
    assert second.air_at(2 * hour) == first.air_at(2 * hour)
    assert second.air_at(4 * hour).temperature_c > first.air_at(4 * hour).temperature_c
    alone = WholeHouse(second.run)
    assert second.air_at(4 * hour).temperature_c == pytest.approx(
        alone.air_at(4 * hour).temperature_c, abs=1e-9
    )


def test_it_carries_on_from_another_without_waiting_for_a_request_working_it_on(
    finishes_beside_held: Callable[[AbstractContextManager[bool], Callable[[], object]], bool],
) -> None:
    first = WholeHouse(_run())
    first.air_at(2 * 3600.0)
    second = WholeHouse(_run())

    assert finishes_beside_held(first._working, lambda: second.carry_on_from(first))
    assert second._kept.keys() == first._kept.keys()


def test_it_takes_over_what_another_works_out_after_it_carried_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A branch made while a request works its source on does not wait for
    # it (above): what the source works out afterwards, up to where their
    # schedules differ, is the branch's air too, and is not worked out again.
    hour = 3600.0
    heated = ((4 * hour, "heater", 1.0),)
    first = WholeHouse(_run())
    second = WholeHouse(_climate_day("climate_box", "default", "default", (), (), heated).run)
    second.carry_on_from(first)
    first.air_at(3 * hour)

    def not_again(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("the branch worked out a stretch its source had")

    monkeypatch.setattr(second, "_advance", not_again)
    assert second.air_at(3 * hour) == first.air_at(3 * hour)


def test_it_waits_for_another_working_the_stretch_it_needs_and_no_longer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Its source is working the very stretch it needs when it is asked: it
    # waits for that rather than work it out beside the source, and goes on
    # as soon as the source is past it, not when the source is done.
    hour = 3600.0
    heated = ((2 * hour, "heater", 1.0),)
    first = WholeHouse(_run())
    second = WholeHouse(_climate_day("climate_box", "default", "default", (), (), heated).run)
    second.carry_on_from(first)
    advance = first._advance

    def slowly(*args: object, **kwargs: object) -> HouseAir:
        time.sleep(0.01)
        return advance(*args, **kwargs)  # type: ignore[arg-type]

    def not_again(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("the branch worked out a stretch its source was working")

    monkeypatch.setattr(first, "_advance", slowly)
    monkeypatch.setattr(second, "_advance", not_again)
    working = threading.Thread(target=first.air_at, args=(12 * hour,))
    working.start()
    while first._stretch is None:
        time.sleep(0.001)

    taken = second.air_at(2 * hour)

    assert working.is_alive()
    working.join()
    assert taken == first.air_at(2 * hour)


def test_its_air_is_the_same_whatever_moments_were_asked_for_before() -> None:
    # A viewer scrubbing a run asks for moments between its minutes: the air
    # later is worked out from the minutes kept, never from those, under a
    # weather and a sun that change through the stretch.
    run = _climate_day("climate_box", "default", "cold_spring_day", (), (), ()).run
    scrubbed = WholeHouse(run)
    for moment in (90.0, 3_599.5, 43_230.0):
        scrubbed.air_at(moment)
    alone = WholeHouse(run)

    for moment in (120.0, 3_660.0, 43_230.0, 43_260.0, DAY_S):
        assert scrubbed.air_at(moment) == alone.air_at(moment)
    assert all(moment % 60.0 == 0 for moment in scrubbed._kept)


def test_its_mean_through_a_stretch_weighs_each_minute_alike() -> None:
    house = _climate_day("climate_box", "default", "cold_spring_day", (), (), ()).house
    minutes = [house.air_at(60.0 * minute) for minute in range(1441)]
    day = house.mean_between(0.0, DAY_S)

    inner = sum(air.temperature_c for air in minutes[1:-1])
    ends = (minutes[0].temperature_c + minutes[-1].temperature_c) / 2
    assert day.temperature_c == pytest.approx((inner + ends) / 1440)
    assert day.co2_ppm == pytest.approx(sum(air.co2_ppm for air in minutes) / 1441, rel=1e-3)
    assert day.condensed_kg == minutes[-1].condensed_kg
    # A stretch is read every minute from its start, and at its end.
    stretch = house.mean_between(30.0, 120.0)
    readings = [house.air_at(moment).temperature_c for moment in (30.0, 90.0, 120.0)]
    assert stretch.temperature_c == pytest.approx(
        ((readings[0] + readings[1]) / 2 * 60 + (readings[1] + readings[2]) / 2 * 30) / 90
    )
    with pytest.raises(ValueError, match="a stretch"):
        house.mean_between(DAY_S, DAY_S)


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
        ("/api/scenarios/climate_box/climate/house?t=1300000", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/sensor_lab/climate/house", HTTPStatus.NOT_FOUND),
        ("/api/scenarios/climate_box/climate/house?weather=foggy", HTTPStatus.NOT_FOUND),
    ],
)
def test_the_api_refuses_the_houses_air_as_it_refuses_the_climate(
    path: str, status: HTTPStatus
) -> None:
    assert respond("GET", path).status == status
