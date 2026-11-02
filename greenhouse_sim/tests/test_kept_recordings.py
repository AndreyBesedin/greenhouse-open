"""Recordings a scenario file brings (P17.11): offered with the packaged
ones for the life of the process, and read as they are."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Final

import pytest

from greenhouse_sim.weather import recorded
from greenhouse_sim.weather.recorded import (
    RecordedWeather,
    keep_recording,
    recorded_weathers,
    recording_available,
    recording_digest,
)
from greenhouse_sim.world.site import DEFAULT_SITE

CSV: Final = (
    "timestamp,outside_air_temperature_c,outside_relative_humidity_pct\n"
    "2026-04-01T00:00Z,8,90\n2026-04-01T01:00Z,9,85\n"
)


@pytest.fixture(autouse=True)
def _no_recordings_kept(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(recorded, "_KEPT", {})
    yield


def test_a_kept_recording_is_read_as_a_packaged_one_is() -> None:
    name = keep_recording("mine.csv", CSV.encode())
    weather = RecordedWeather(file=name)

    assert weather.identity() == recording_digest(CSV.encode())
    start = datetime(2026, 4, 1, tzinfo=UTC)
    state = weather.source(DEFAULT_SITE).at(start)
    assert state.air_temperature_c == pytest.approx(8.0)


def test_a_recording_that_is_not_kept_is_not_found() -> None:
    with pytest.raises(FileNotFoundError, match=r"no recorded weather 'mine\.csv'"):
        RecordedWeather(file="mine.csv").identity()


def test_a_recording_is_offered_and_kept_under_a_digest_name_on_a_clash() -> None:
    first = keep_recording("mine.csv", CSV.encode())
    assert keep_recording("mine.csv", CSV.encode()) == first == "mine.csv"
    other = CSV.replace(",8,", ",7,").encode()
    second = keep_recording("mine.csv", other)
    packaged = keep_recording("example_day.csv", other)

    assert second == f"mine-{recording_digest(other)[:12]}.csv"
    assert packaged == f"example_day-{recording_digest(other)[:12]}.csv"
    offered = recorded_weathers()
    assert {"example_day", "mine", second.removesuffix(".csv")} <= set(offered)
    assert offered["mine"].identity() == recording_digest(CSV.encode())
    assert offered["example_day"].identity() != recording_digest(other)


def test_a_recording_is_available_by_name_and_content() -> None:
    keep_recording("mine.csv", CSV.encode())

    assert recording_available("mine.csv", recording_digest(CSV.encode()))
    assert not recording_available("mine.csv", recording_digest(b"other"))
    assert not recording_available("absent.csv", recording_digest(CSV.encode()))


@pytest.mark.parametrize("name", ["../mine.csv", "dir/mine.csv", "Mine.csv", "mine.txt", ".csv"])
def test_a_recording_with_a_name_that_is_not_plain_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="not a recording's name"):
        keep_recording(name, CSV.encode())


def test_a_recording_that_is_not_a_weather_file_is_not_kept() -> None:
    with pytest.raises(ValueError, match="a weather file starts with"):
        keep_recording("mine.csv", b"a,b\n1,2\n")
    assert "mine" not in recorded_weathers()
    with pytest.raises(ValueError, match="UTF-8"):
        keep_recording("mine.csv", b"\xff\xfe")
