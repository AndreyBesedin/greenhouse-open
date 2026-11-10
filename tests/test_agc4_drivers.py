"""The hourly drivers a tomato model is run on in AGC4 (decision 0076),
built from miniature archives shaped as the real ones are: no data needed."""

import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from greenhouse_adapters.wur.agc4_challenge_2024.compartments import COMPARTMENTS

from research.validation.agc4 import drivers
from research.validation.agc4.drivers import DAYS, Reading, Series, hourly

TIMESERIES = "autonomous_greenhouse_challenge4_timeseries"
COLUMNS = (
    "time",
    drivers.TEMPERATURE,
    drivers.PAR,
    drivers.CO2,
    drivers.DENSITY,
    drivers.HARVEST_DAY,
)
# 4 September 2024, counted from 1 January as day 1: a one-day crop.
HARVEST_DAY_OF_YEAR = 248
LOCAL_SUMMER = timedelta(hours=2)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 9, 3, hour, minute, tzinfo=DAYS)


def test_an_hour_is_the_mean_of_the_rows_stamped_inside_it() -> None:
    readings = [
        Reading(at(0, 0), 20.0, 100.0, 400.0),
        Reading(at(0, 30), 22.0, 300.0, 500.0),
        Reading(at(1, 0), 24.0, 0.0, 600.0),
        # Outside the series: before it, and at its end.
        Reading(at(0) - timedelta(minutes=5), 99.0, 99.0, 99.0),
        Reading(at(2), 99.0, 99.0, 99.0),
    ]

    hours = hourly(readings, [(at(0), 56.0)], at(0), at(2))

    assert [(h.start, h.temperature_c, h.par_above_umol_m2_s, h.co2_ppm) for h in hours] == [
        (at(0), 21.0, 200.0, 450.0),
        (at(1), 24.0, 0.0, 600.0),
    ]
    assert [h.filled for h in hours] == [False, False]


def test_a_driver_missing_from_an_hour_takes_its_mean_of_the_hour_before() -> None:
    readings = [
        Reading(at(0), 20.0, 100.0, 400.0),
        # The hour after has CO₂ alone; the one after that, nothing.
        Reading(at(1, 10), None, None, 410.0),
        Reading(at(3), 23.0, 130.0, 430.0),
    ]

    hours = hourly(readings, [(at(0), 56.0)], at(0), at(4))

    assert [(h.temperature_c, h.par_above_umol_m2_s, h.co2_ppm, h.filled) for h in hours] == [
        (20.0, 100.0, 400.0, False),
        (20.0, 100.0, 410.0, True),
        (20.0, 100.0, 410.0, True),
        (23.0, 130.0, 430.0, False),
    ]


def test_a_series_does_not_begin_with_an_hour_it_must_invent() -> None:
    with pytest.raises(ValueError, match="first hour"):
        hourly([Reading(at(1), 20.0, 100.0, 400.0)], [(at(0), 56.0)], at(0), at(2))


def test_the_density_in_force_is_the_last_written_at_or_before_the_hour() -> None:
    readings = [Reading(at(h), 20.0, 100.0, 400.0) for h in range(4)]
    # Written before the series begins, then at a local midnight in summer,
    # which is 23:00 at the days' fixed offset.
    densities = [(at(0) - timedelta(hours=1), 56.0), (at(2, 0), 42.0)]

    hours = hourly(readings, densities, at(0), at(4))

    assert [h.plants_per_m2 for h in hours] == [56.0, 56.0, 42.0, 42.0]


def _challenge_csv() -> str:
    """A compartment's rows every 5 minutes, stamped in local summer time,
    from 00:00 on 3 September to 12:00 on its harvest day, 4 September."""
    lines = [",".join(COLUMNS)]
    moment = datetime(2024, 9, 3, 0, 0)
    end = datetime(2024, 9, 4, 12, 0)
    first = True
    while moment <= end:
        stamp = f"{moment.isoformat(sep=' ')}+02:00"
        hour_at_days = (moment - LOCAL_SUMMER + timedelta(hours=1)).hour
        density = "56.0" if first else ""
        harvest = str(HARVEST_DAY_OF_YEAR) if moment == end else ""
        lines.append(f"{stamp},{20 + hour_at_days},{10 * hour_at_days},400,{density},{harvest}")
        first = False
        moment += timedelta(minutes=5)
    return "\n".join(lines) + "\n"


def _challenge(tmp_path: Path) -> Path:
    path = tmp_path / "challenge.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for compartment in COMPARTMENTS.values():
            archive.writestr(f"{TIMESERIES}/{compartment.timeseries_member}", _challenge_csv())
        archive.writestr(f"__MACOSX/{TIMESERIES}/timeseries/._reference.csv", "")
    return path


def test_a_compartment_runs_from_3_september_to_the_midnight_before_its_harvest(
    tmp_path: Path,
) -> None:
    series = drivers.challenge_series(_challenge(tmp_path))

    assert [each.name for each in series] == list(COMPARTMENTS)
    hours = series[0].hours
    # 00:00 to 23:00 at UTC+01:00 on 3 September: the files' first local hour,
    # 23:00 on 2 September at the fixed offset, is before the series.
    assert len(hours) == 24
    assert hours[0].start == datetime(2024, 9, 3, 0, tzinfo=DAYS)
    assert hours[-1].start == datetime(2024, 9, 3, 23, tzinfo=DAYS)
    # Each hour's rows are those of the same hour at the fixed offset.
    assert [h.temperature_c for h in hours] == [20.0 + h for h in range(24)]
    assert {h.plants_per_m2 for h in hours} == {56.0}
    assert not any(h.filled for h in hours)


def test_a_series_is_written_the_same_way_every_time(tmp_path: Path) -> None:
    first, again = drivers.challenge_series(_challenge(tmp_path))[:2]

    text = first.csv_text()

    assert text == again.csv_text()
    assert text.splitlines()[:2] == [
        "hour_start,temperature_c,par_above_umol_m2_s,co2_ppm,plants_per_m2,filled",
        "2024-09-03T00:00:00+01:00,20.0,0.0,400.0,56.0,0",
    ]


def test_a_pretrial_row_is_read_at_its_local_moment() -> None:
    row = (datetime(2023, 9, 5, 1, 0), 18.5, 0.0, 420.0)

    reading = drivers._pretrial_reading(row, 0, 1, 2, 3)

    assert reading == Reading(datetime(2023, 9, 4, 23, 0, tzinfo=UTC), 18.5, 0.0, 420.0)
    assert reading is not None
    assert reading.at.astimezone(DAYS).isoformat() == "2023-09-05T00:00:00+01:00"


def test_a_pretrial_time_the_clocks_repeat_is_refused_if_it_holds_a_value() -> None:
    repeated = datetime(2023, 10, 29, 2, 30)

    assert drivers._pretrial_reading((repeated, "NaN", None, "NaN"), 0, 1, 2, 3) is None
    with pytest.raises(ValueError, match="repeat"):
        drivers._pretrial_reading((repeated, 17.0, None, None), 0, 1, 2, 3)


def test_it_refuses_an_archive_not_downloaded(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="greenhouse-data prepare"):
        drivers.main([str(tmp_path / "out"), "--data-dir", str(tmp_path)])


def test_a_series_names_its_hours() -> None:
    series = Series("3.06", hourly([Reading(at(0), 1.0, 2.0, 3.0)], [(at(0), 20.0)], at(0), at(1)))

    assert series.csv_text().splitlines()[1] == "2024-09-03T00:00:00+01:00,1.0,2.0,3.0,20.0,0"
