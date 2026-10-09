"""Recorded weather (P07.7): read from a CSV named after the protocol's
outside observation types, each bad file refused naming its row, a short
gap interpolated and a long one refused, replayed at a run's start, and a
run told apart by its file."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_sim.climate.openings import opening_flows, opening_sites
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.sensors.air import reads
from greenhouse_sim.services import scenarios, sensors, weather
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.services.scenarios import SceneChanges, changed
from greenhouse_sim.weather.recorded import (
    RecordedWeather,
    WeatherFileError,
    read_records,
    recorded_weathers,
)
from greenhouse_sim.world.site import DEFAULT_SITE

BOX = SCENARIO_REGISTRY["climate_box"]
HEADER = "timestamp,outside_air_temperature_c,outside_relative_humidity_pct"
HOUR = timedelta(hours=1)


def _at(tmp_path: Path) -> RecordedWeather:
    class _Here(RecordedWeather):
        def path(self) -> Path:
            return tmp_path / self.file

    return _Here(file="day.csv")


def _write(tmp_path: Path, text: str) -> RecordedWeather:
    (tmp_path / "day.csv").write_text(text)
    return _at(tmp_path)


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        ("time,outside_air_temperature_c\n", "row 1: a weather file starts with a 'timestamp'"),
        (HEADER + ",outside_snow_cm\n", "row 1: no outside quantity is called 'outside_snow_cm'"),
        ("timestamp,outside_air_temperature_c\n", "row 1: a weather file gives outside_relative"),
        (HEADER + "\n2026-04-01T00:00,8,90\n", "row 2: its timestamp has no time zone"),
        (HEADER + "\nsoon,8,90\n", "row 2: 'soon' is no ISO 8601 timestamp"),
        (
            HEADER + "\n2026-04-01T01:00Z,8,90\n2026-04-01T00:00Z,8,90\n",
            "row 3: its timestamp is not after the row's before",
        ),
        (HEADER + "\n2026-04-01T00:00Z,warm,90\n", "row 2: outside_air_temperature_c is not a"),
        (HEADER + "\n2026-04-01T00:00Z,8,140\n", "row 2: outside_relative_humidity_pct is 140,"),
    ],
    ids=[
        "no timestamp",
        "unknown column",
        "no humidity",
        "no time zone",
        "no timestamp at all",
        "out of order",
        "not a number",
        "out of range",
    ],
)
def test_a_bad_file_is_refused_naming_its_row(text: str, refusal: str) -> None:
    with pytest.raises(WeatherFileError, match=refusal):
        read_records(text)


def test_a_short_gap_is_interpolated_across(tmp_path: Path) -> None:
    source = _write(
        tmp_path,
        HEADER + "\n2026-04-01T00:00Z,8,90\n2026-04-01T00:30Z,,80\n2026-04-01T01:00Z,10,70\n",
    ).source(DEFAULT_SITE)

    halfway = source.at(datetime(2026, 4, 1, 0, 30, tzinfo=UTC))
    assert halfway.air_temperature_c == pytest.approx(9.0)
    assert halfway.relative_humidity_pct == pytest.approx(80.0)


def test_a_long_gap_is_not_invented(tmp_path: Path) -> None:
    source = _write(
        tmp_path,
        HEADER + "\n2026-04-01T00:00Z,8,90\n2026-04-01T01:00Z,,80\n2026-04-01T03:00Z,10,70\n",
    ).source(DEFAULT_SITE)

    # The humidity is known throughout; the temperature not for two hours.
    with pytest.raises(ValueError, match="does not know outside_air_temperature_c"):
        source.at(datetime(2026, 4, 1, 1, 30, tzinfo=UTC))
    with pytest.raises(ValueError, match="known from"):
        source.at(datetime(2026, 4, 1, 4, tzinfo=UTC))


def test_what_a_file_leaves_out_takes_its_default(tmp_path: Path) -> None:
    state = (
        _write(tmp_path, HEADER + "\n2026-04-01T00:00Z,8,90\n2026-04-01T01:00Z,8,90\n")
        .source(DEFAULT_SITE)
        .at(datetime(2026, 4, 1, 0, 30, tzinfo=UTC))
    )

    assert state.co2_ppm == 420.0
    assert state.barometric_pressure_hpa == pytest.approx(DEFAULT_SITE.standard_pressure_hpa())
    # No wind vane: a wind without a direction.
    assert state.wind_speed_m_s == 0.0
    assert state.wind_direction_deg is None


def test_a_wind_without_a_direction_drives_no_flow_and_a_vane_reads_none(tmp_path: Path) -> None:
    breezy = (
        HEADER + ",outside_wind_speed_m_s\n2026-04-01T00:00Z,8,90,6\n2026-04-01T01:00Z,8,90,6\n"
    )
    state = _write(tmp_path, breezy).source(DEFAULT_SITE).at(datetime(2026, 4, 1, tzinfo=UTC))
    config = changed(BOX, SceneChanges(openings={"side_vent": 1.0, "side_vent_left": 1.0}))
    sites = list(opening_sites(config.envelope, config.site).values())
    vane = next(s for s in BOX.layout.weather_station() if s.sensor_id == "station_wind_direction")

    flows = opening_flows(sites, 8.0, state)
    assert all(flow.net_m3_s == 0.0 for flow in flows)
    assert all(flow.exchange_m3_s > 0.0 for flow in flows)
    assert state.wind_m_s(DEFAULT_SITE).x == 0.0
    assert reads(vane, shear_field("shear", air_grid(BOX)), state) is None


def test_the_wind_vane_turns_the_shorter_way_round(tmp_path: Path) -> None:
    text = (
        HEADER
        + ",outside_wind_speed_m_s,outside_wind_direction_deg\n"
        + "2026-04-01T00:00Z,8,90,4,350\n2026-04-01T01:00Z,8,90,4,10\n"
    )
    state = _write(tmp_path, text).source(DEFAULT_SITE).at(datetime(2026, 4, 1, 0, 30, tzinfo=UTC))

    assert state.wind_direction_deg == pytest.approx(0.0, abs=1e-9)


def test_a_recorded_day_is_replayed_from_its_midnight_at_a_runs_start(tmp_path: Path) -> None:
    text = HEADER + "\n2026-03-31T22:00Z,8,90\n2026-04-01T00:00Z,12,70\n"
    start = BOX.run_start()
    source = _write(tmp_path, text).source(DEFAULT_SITE, 0, start)

    # Midnight in Amsterdam on 1 April is 22:00 UTC the day before.
    assert source.at(start).air_temperature_c == pytest.approx(8.0)
    assert source.at(start + 2 * HOUR).air_temperature_c == pytest.approx(12.0)


def test_the_example_day_is_a_scenarios_weather_by_name() -> None:
    assert "example_day" in recorded_weathers()
    assert "example_day" in scenarios.weather_names()
    day = weather.through_the_day("climate_box", "example_day")

    assert len(day.weather) == 145
    assert all(state.wind_direction_deg is not None for state in day.weather)
    # Its half hour without humidity is interpolated across.
    assert all(0 < state.relative_humidity_pct <= 100 for state in day.weather)


def test_a_run_is_told_apart_by_its_recorded_file(tmp_path: Path) -> None:
    first = _write(tmp_path, HEADER + "\n2026-04-01T00:00Z,8,90\n")
    before = first.identity()
    second = _write(tmp_path, HEADER + "\n2026-04-01T00:00Z,9,90\n")

    assert second.identity() != before
    own = sensors.observations("climate_box", until_s=60).run_id
    recorded = sensors.observations("climate_box", until_s=60, weather="example_day").run_id
    assert own != recorded
