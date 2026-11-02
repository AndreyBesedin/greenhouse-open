"""Recordings a scenario file brings (P17.11): carried by the weather of the
scenario that registers them, never by the process, and read as they are."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.services.scenarios import weather_names
from greenhouse_sim.weather import recorded
from greenhouse_sim.weather.recorded import (
    NAME_DIGEST_LENGTH,
    RecordedWeather,
    checked_recording,
    packaged_recording_is,
    recorded_weathers,
    recording_digest,
)
from greenhouse_sim.world.site import DEFAULT_SITE

CSV: Final = (
    "timestamp,outside_air_temperature_c,outside_relative_humidity_pct\n"
    "2026-04-01T00:00Z,8,90\n2026-04-01T01:00Z,9,85\n"
)
OTHER: Final = CSV.replace(",8,", ",7,")


def test_a_recording_is_read_as_a_packaged_one_is() -> None:
    weather = checked_recording("mine.csv", CSV.encode())

    assert weather.file == "mine.csv"
    assert weather.identity() == recording_digest(CSV.encode())
    state = weather.source(DEFAULT_SITE).at(datetime(2026, 4, 1, tzinfo=UTC))
    assert state.air_temperature_c == pytest.approx(8.0)


def test_a_recording_is_the_weathers_and_not_the_processs() -> None:
    names = weather_names()
    checked_recording("cold_spring_day.csv", CSV.encode())
    checked_recording("default.csv", CSV.encode())

    # Nothing is offered by name, so a selector name cannot be taken over;
    # and the file name alone finds nothing.
    assert weather_names() == names
    assert "default" not in recorded_weathers()
    with pytest.raises(FileNotFoundError, match=r"no recorded weather 'mine\.csv'"):
        RecordedWeather(file="mine.csv").identity()


def test_a_recording_is_not_part_of_the_weathers_written_form() -> None:
    weather = checked_recording("mine.csv", CSV.encode())

    assert weather.model_dump(mode="json") == {"kind": "recorded", "file": "mine.csv"}
    assert "text" not in RecordedWeather.model_json_schema()["properties"]


def test_a_recording_of_a_packaged_ones_name_and_other_content_is_named_by_its_digest() -> None:
    same = (recorded.RECORDED_DIRECTORY / "example_day.csv").read_bytes()
    other = OTHER.encode()

    assert checked_recording("example_day.csv", same).file == "example_day.csv"
    assert (
        checked_recording("example_day.csv", other).file
        == f"example_day-{recording_digest(other)[:NAME_DIGEST_LENGTH]}.csv"
    )
    assert packaged_recording_is("example_day.csv", recording_digest(same))
    assert not packaged_recording_is("example_day.csv", recording_digest(other))


def test_a_name_made_from_a_digest_that_is_taken_too_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recorded, "RECORDED_DIRECTORY", tmp_path)
    digest = recording_digest(OTHER.encode())
    (tmp_path / "mine.csv").write_text(CSV)
    (tmp_path / f"mine-{digest[:NAME_DIGEST_LENGTH]}.csv").write_text(CSV)

    assert checked_recording("mine.csv", OTHER.encode()).file == f"mine-{digest}.csv"
    (tmp_path / f"mine-{digest}.csv").write_text(CSV)
    with pytest.raises(ValueError, match="packaged recording's"):
        checked_recording("mine.csv", OTHER.encode())


@pytest.mark.parametrize("name", ["../mine.csv", "dir/mine.csv", "Mine.csv", "mine.txt", ".csv"])
def test_a_recording_with_a_name_that_is_not_plain_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="not a recording's name"):
        checked_recording(name, CSV.encode())


def test_a_recording_that_is_not_a_weather_file_is_refused() -> None:
    with pytest.raises(ValueError, match="a weather file starts with"):
        checked_recording("mine.csv", b"a,b\n1,2\n")
    with pytest.raises(ValueError, match="UTF-8"):
        checked_recording("mine.csv", b"\xff\xfe")
