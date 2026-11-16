"""The simulator is compared with TiGwerLib as its statement has it
(research/modelica/simulator_comparison.json), without Docker: its house is
TiGwerLib's geometry, its roof windows open as the records of the side
facing the wind or away from it, its heater gives what TiGwerLib's pipes
give, its weather is TiGwerLib's records, and a day is within the bar only
by its own RMSE."""

import math
from pathlib import Path

import pytest
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.weather.recorded import read_records
from greenhouse_sim.world.equipment import Heater

from research.modelica import openmodelica as om
from research.modelica import simulator_comparison as comparison
from research.modelica.sourisseau_2026 import Window

DAY = om.DAY_S
STEP = om.INTERVAL_S
WINDOW = Window("two_days", 32227200, 32227200 + 2 * DAY)


def _recording(at: Window = WINDOW) -> str:
    weather = [
        (float(t), 9.6, 6.0, 82.8, 101325.0, 38.0, 1.4, 0.0, 1.4, 0.0, 360.0, 2.9, 0.0, 0.0)
        for t in range(at.start_s - STEP, at.end_s + 2 * STEP, STEP)
    ]
    return comparison.weather_recording(weather, at)


def _house(at: Window = WINDOW) -> ScenarioConfig:
    return comparison.ctifl_house(at, _recording(at), 290.0, 0.8)


def test_the_house_is_tigwerlibs_greenhouse() -> None:
    config = _house()
    envelope = config.envelope
    assert (envelope.length, envelope.width) == (43.2, 24.0)
    assert (envelope.eave_height, envelope.ridge_height) == (6.97, 7.78)
    # Its slope is TiGwerLib's roof windows' phi, 0.38397 rad, to a tenth of
    # a degree.
    assert math.degrees(envelope.roof_pitch) == pytest.approx(22.0, abs=0.1)
    assert config.site.x_bearing_deg == 331.0
    # 23 windows of TiGwerLib's size on each side of the roof, as many as
    # its two sides have on average for its floor.
    floor = envelope.length * envelope.width
    windows = envelope.openings
    assert (
        len(windows)
        == 46
        == round((comparison.WINDWARD_PER_M2 + comparison.LEEWARD_PER_M2) * floor)
    )
    assert {(w.width, w.height) for w in windows} == {(4.05, 1.4)}
    assert {round(math.degrees(w.largest_angle), 9) for w in windows} == {44.0}
    assert all(w.opening == 0.0 for w in windows)
    facing = comparison.window_facing(config)
    assert sorted({round(f) for f in facing.values()}) == [61, 241]
    assert sum(round(f) == 61 for f in facing.values()) == 23
    # Its heater gives TiGwerLib's three networks' most, together.
    (heater,) = config.layout.equipment
    assert isinstance(heater, Heater)
    assert heater.power_w == 360_000.0
    # Its air starts as TiGwerLib's does.
    assert config.climate.start_temperature_c == pytest.approx(290.0 - 273.15)
    assert config.climate.start_humidity_pct == pytest.approx(80.0)
    assert config.climate.kind == "whole_house"


def test_its_weather_is_tigwerlibs_records_through_the_window_on_its_clock() -> None:
    text = _recording()
    lines = text.splitlines()
    # Both ends included, and nothing beyond them.
    assert len(lines) == 1 + 2 * DAY // STEP + 1
    assert lines[1] == "2015-01-09T00:00:00+01:00,9.6,82.8,1013.25,1.4,2.9,0"
    assert lines[-1].startswith("2015-01-11T00:00:00+01:00,")
    # The simulator reads it: a wind from 360° is from the north, 0°.
    known = read_records(text)
    assert set(known) >= {"air_temperature_c", "wind_direction_deg", "global_radiation_w_m2"}


def test_a_window_faces_the_wind_within_a_quarter_turn() -> None:
    assert comparison.faces_the_wind(61.0, 61.0)
    assert comparison.faces_the_wind(61.0, 350.0)
    assert not comparison.faces_the_wind(241.0, 61.0)
    # Along the ridges, neither side faces it.
    assert not comparison.faces_the_wind(61.0, 151.0)
    assert not comparison.faces_the_wind(241.0, 151.0)


def test_the_windows_open_as_the_records_of_their_side_of_the_wind() -> None:
    at = Window("hour", WINDOW.start_s, WINDOW.start_s + 3 * STEP)
    moments = range(at.start_s, at.end_s, STEP)
    facing = {"east": 61.0, "west": 241.0}
    wind = dict(zip(moments, (61.0, 61.0, 241.0), strict=True))
    plan = comparison.commands(
        at=at,
        heat_w=dict.fromkeys(moments, 36_000.0),
        leeward=dict.fromkeys(moments, 10.0),
        windward=dict.fromkeys(moments, 50.0),
        wind_from_deg=wind,
        facing_deg=facing,
    )
    assert plan == [
        (0.0, comparison.HEATING, 0.1),
        (0.0, "east", 0.5),
        (0.0, "west", 0.1),
        # Nothing changed at the second step; at the third, the wind turned.
        (2.0 * STEP, "east", 0.1),
        (2.0 * STEP, "west", 0.5),
    ]


def _main_rows(power_kwh_m2: tuple[float, float, float], until_s: int) -> list[tuple[float, ...]]:
    rows = []
    for t in range(om.START_S, until_s + STEP, STEP):
        row = [0.0] * 37
        row[0] = float(t)
        for index, value in zip(comparison.MAIN_HEAT_KWH_M2, power_kwh_m2, strict=True):
            row[index - 1] = value
        rows.append(tuple(row))
    return rows


def _kwh_m2(power_w: float) -> float:
    return power_w * STEP / 3.6e6 / (comparison.LENGTH_M * comparison.WIDTH_M)


def test_the_heat_is_tigwerlibs_pipes_filtered_from_the_seasons_start() -> None:
    # A steady 20 kW on the floor's rails from the season's start: its
    # filter has long reached it by a window weeks later.
    at = Window("later", om.START_S + 10 * DAY, om.START_S + 10 * DAY + 4 * STEP)
    heat = comparison.injected_heat_w(_main_rows((_kwh_m2(20_000.0), 0.0, 0.0), at.end_s), at)
    assert list(heat) == list(range(at.start_s, at.end_s, STEP))
    assert all(value == pytest.approx(20_000.0) for value in heat.values())

    # From the season's start, the first step's mean is the filter's rise
    # over it, which numerical integration agrees with.
    first = Window("first", om.START_S, om.START_S + STEP)
    (mean,) = comparison.injected_heat_w(
        _main_rows((_kwh_m2(20_000.0), 0.0, 0.0), first.end_s), first
    ).values()
    samples = 10_000
    numeric = (
        sum(
            20_000.0 * (1 - math.exp(-(i + 0.5) * STEP / samples / comparison.HEAT_TIME_CONSTANT_S))
            for i in range(samples)
        )
        / samples
    )
    assert mean == pytest.approx(numeric, rel=1e-6)

    # A negative record is no heat.
    heat = comparison.injected_heat_w(_main_rows((-1.0, 0.0, 0.0), at.end_s), at)
    assert set(heat.values()) == {0.0}


def test_the_heat_is_held_below_each_networks_limit() -> None:
    # Far above the PE tubes' 50 kW for long: held at it.
    at = Window("later", om.START_S + 10 * DAY, om.START_S + 10 * DAY + STEP)
    heat = comparison.injected_heat_w(_main_rows((0.0, 0.0, _kwh_m2(80_000.0)), at.end_s), at)
    assert list(heat.values()) == [pytest.approx(50_000.0)]


@pytest.mark.parametrize(
    ("start_w", "towards_w"),
    [
        # Rising through the limit within the step, then held at it.
        (48_000.0, 100_000.0),
        # Held at first, then falling below it within the step.
        (52_000.0, 0.0),
    ],
)
def test_a_step_crossing_the_limit_is_held_from_the_crossing(
    start_w: float, towards_w: float
) -> None:
    limit = 50_000.0
    # The filter's output at the step's end lies across the limit from its start.
    end_w = towards_w + (start_w - towards_w) * math.exp(-STEP / comparison.HEAT_TIME_CONSTANT_S)
    assert (start_w - limit) * (end_w - limit) < 0
    samples = 100_000
    numeric = (
        sum(
            min(
                towards_w
                + (start_w - towards_w)
                * math.exp(-(i + 0.5) * STEP / samples / comparison.HEAT_TIME_CONSTANT_S),
                limit,
            )
            for i in range(samples)
        )
        / samples
    )
    assert comparison._held_below(start_w, towards_w, limit) == pytest.approx(numeric, rel=1e-8)


def test_a_day_is_within_the_bar_by_its_own_rmse() -> None:
    moments = range(WINDOW.start_s, WINDOW.end_s + STEP, STEP)
    tigwerlib = dict.fromkeys(moments, 290.0)
    measured = dict.fromkeys(moments, 289.0)
    simulator = dict.fromkeys(moments, 291.0)
    # The second day 3 K off; its midnight, the window's end, belongs to no day.
    for t in range(WINDOW.start_s + DAY, WINDOW.end_s + STEP, STEP):
        simulator[t] = 293.0
    simulator.pop(WINDOW.start_s + STEP)
    sunlit = [t for t in moments if (t - WINDOW.start_s) % DAY >= DAY // 2]

    found = comparison.compare(simulator, tigwerlib, measured, sunlit=sunlit, at=WINDOW, bar=1.6)
    assert (found["moments"], found["missing"]) == (2 * DAY // STEP + 1, 1)
    first, second = found["days"]
    assert (first["rmse_difference"], first["within_bar"]) == (pytest.approx(1.0), True)
    assert (second["rmse_difference"], second["within_bar"]) == (pytest.approx(3.0), False)
    assert first["compared"] == DAY // STEP - 1
    assert first["simulator_vs_measured"] == pytest.approx(2.0)
    assert first["tigwerlib_vs_measured"] == pytest.approx(1.0)
    assert found["days_within_bar"] == 1
    assert (found["largest_difference"], found["largest_at_s"]) == (3.0, WINDOW.start_s + DAY)
    # The sun's hours are told apart from the night's.
    assert found["sun_up"]["compared"] + found["sun_down"]["compared"] == found["compared"]
    assert found["sun_up"]["mean_difference"] == pytest.approx(2.0)


def test_the_sun_is_up_by_day_at_carquefou() -> None:
    config = _house()
    up = comparison.sun_up(config, WINDOW)
    first_day = [t - WINDOW.start_s for t in up if t < WINDOW.start_s + DAY]
    # In January, from about 8:45 to 17:30 in UTC+1.
    assert 8 * 3600 < first_day[0] < 9 * 3600
    assert 17 * 3600 < first_day[-1] < 18 * 3600


def test_tigwerlibs_tables_are_read_without_their_comments(tmp_path: Path) -> None:
    table = tmp_path / "table.txt"
    table.write_text(
        "#1\t\t\ndouble tab1(2,3) #Time|a|b\n#C1 Time\n\n29030400\t1.5\t-2\n29030700\t2\t3e-1\n"
    )
    rows = comparison.read_table(table)
    assert rows == [(29030400.0, 1.5, -2.0), (29030700.0, 2.0, 0.3)]
    assert comparison.column(rows, 3) == {29030400: -2.0, 29030700: 0.3}


def test_the_heat_is_checked_against_tigwerlibs_run(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    results.write_text(
        '"time","CanopyPipesTotDissip","LowPipesTotDissip","MainAir.T","PEPipesTotDissip"\n'
        "100,1,10,290,0\n400,1,20,290,0\n700,1,30,290,0\n"
    )
    pipes = comparison.pipes_heat_w(results)
    assert pipes == {100: 11.0, 400: 21.0, 700: 31.0}
    # A step whose end the run does not hold is not compared.
    found = comparison.heat_check({100: 16.0, 400: 27.0, 700: 31.0}, pipes)
    assert found == {"steps": 3, "compared": 2, "largest_difference_w": 1.0}
