"""Builds the hourly drivers a tomato model is run on in AGC4, as decision
0076 fixes them: per 2024 compartment, and per 2023 light zone.

    python -m research.validation.agc4.drivers OUT_DIR [--data-dir DIR] \\
        > research/validation/agc4/drivers.json

Each series is a CSV in `OUT_DIR`, an hour to a row: the hour's start at
UTC+01:00, the mean of each driver over the 5-minute rows stamped inside
it, and the plants per m² in force at its start. A driver with no rows in
an hour takes its mean of the hour before, and the hour says so. The days
are 24 hours, at a fixed UTC+01:00, whatever the clocks said.

- **2024,** per compartment: `compartment/air_temperature`,
  `compartment/par` and `compartment/co2_concentration`, and
  `dwarf_tomato/plant_density` carried forward from where it is written.
  From 00:00 on 3 September to the midnight that begins the compartment's
  harvest day, the day its `dwarf_tomato/harvest_date` names.
- **2023,** per light zone: the compartment's `t_air` and `co2`, and the
  zone's own PAR column (`part1`, `par2`, `par3` or `par4`). Its times are
  local wall clock, without an offset; one the clocks repeat is refused if
  it holds a value. From 00:00 on 5 September, the first whole day of its
  climate, to 00:00 on 9 November, its last destructive sample. The density
  is the destructive workbook's `Info` sheet's.

The CSVs are data derived from AGC4 (CC BY 4.0), and are not committed.
What is committed is the JSON this prints: each series' file, hours, span,
the hours filled and the sha256 of its bytes, which are the same on every
run.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

import openpyxl
from greenhouse_adapters.manifests import load_manifest
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_adapters.wur.agc4_challenge_2024.compartments import COMPARTMENTS

from research.validation.agc4.archives import (
    CHALLENGE,
    CHALLENGE_ARCHIVE,
    PRETRIAL,
    PRETRIAL_ARCHIVE,
    PRETRIAL_CLIMATE,
    PRETRIAL_CLIMATE_SHEET,
    archive_path,
    holds,
    members,
    provenance,
)

# Decision 0076's days: 24 hours each, whatever the clocks said.
DAYS: Final = timezone(timedelta(hours=1))
LOCAL: Final = ZoneInfo("Europe/Amsterdam")
HOUR: Final = timedelta(hours=1)
DIGITS: Final = 6

CHALLENGE_START: Final = datetime(2024, 9, 3, tzinfo=DAYS)
TEMPERATURE: Final = "compartment/air_temperature"
PAR: Final = "compartment/par"
CO2: Final = "compartment/co2_concentration"
DENSITY: Final = "dwarf_tomato/plant_density"
HARVEST_DAY: Final = "dwarf_tomato/harvest_date"
# `dwarf_tomato/harvest_date` counts the year's days from 1 January, day 1.
HARVEST_YEAR: Final = 2024

PRETRIAL_START: Final = datetime(2023, 9, 5, tzinfo=DAYS)
PRETRIAL_END: Final = datetime(2023, 11, 9, tzinfo=DAYS)
PRETRIAL_TIME: Final = "date"
PRETRIAL_TEMPERATURE: Final = "t_air"
PRETRIAL_CO2: Final = "co2"
# Each light zone's PAR column, as the climate sheet spells them; its `Info`
# sheet calls the first `par1`.
PRETRIAL_ZONES: Final = {"high": "part1", "medium": "par2", "low": "par3", "none": "par4"}
# The plants per m² from each date on (`DestructiveHarvest.xlsx`, `Info`):
# 48 from 4 September, 36 from 18, 25 from 22, and 20 from 9 October. The
# sheet gives none from 29 September to 9 October: 25 is carried through.
PRETRIAL_DENSITY: Final = (
    (date(2023, 9, 4), 48.0),
    (date(2023, 9, 18), 36.0),
    (date(2023, 9, 22), 25.0),
    (date(2023, 10, 9), 20.0),
)

HEADER: Final = (
    "hour_start",
    "temperature_c",
    "par_above_umol_m2_s",
    "co2_ppm",
    "plants_per_m2",
    "filled",
)


@dataclass(frozen=True)
class Reading:
    """A 5-minute row's drivers, at its moment; a driver it lacks is None."""

    at: datetime
    temperature_c: float | None
    par_umol_m2_s: float | None
    co2_ppm: float | None


@dataclass(frozen=True)
class Hour:
    """An hour of a run's drivers: its start, each driver's mean over it,
    the plants per m² in force at its start, and whether its means are the
    hour before's, for want of rows of its own."""

    start: datetime
    temperature_c: float
    par_above_umol_m2_s: float
    co2_ppm: float
    plants_per_m2: float
    filled: bool


@dataclass(frozen=True)
class Series:
    """A run's drivers, an hour to a row."""

    name: str
    hours: list[Hour]

    def csv_text(self) -> str:
        written = io.StringIO()
        writer = csv.writer(written, lineterminator="\n")
        writer.writerow(HEADER)
        for hour in self.hours:
            writer.writerow(
                (
                    hour.start.isoformat(),
                    _number(hour.temperature_c),
                    _number(hour.par_above_umol_m2_s),
                    _number(hour.co2_ppm),
                    _number(hour.plants_per_m2),
                    int(hour.filled),
                )
            )
        return written.getvalue()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=None, help="override GREENHOUSE_DATA_DIR")
    arguments = parser.parse_args(argv)
    data = DataDirectory(arguments.data_dir)
    arguments.out_dir.mkdir(parents=True, exist_ok=True)
    built = {
        CHALLENGE: (
            provenance(load_manifest(CHALLENGE), CHALLENGE_ARCHIVE),
            challenge_series(archive_path(data, CHALLENGE, CHALLENGE_ARCHIVE)),
        ),
        PRETRIAL: (
            provenance(load_manifest(PRETRIAL), PRETRIAL_ARCHIVE),
            pretrial_series(archive_path(data, PRETRIAL, PRETRIAL_ARCHIVE)),
        ),
    }
    manifest: dict[str, object] = {}
    for dataset, (source, series) in built.items():
        written: dict[str, object] = {}
        for each in series:
            text = each.csv_text()
            name = f"{dataset}_{each.name}.csv"
            (arguments.out_dir / name).write_text(text, encoding="utf-8")
            written[each.name] = {
                "file": name,
                "hours": len(each.hours),
                "first": each.hours[0].start.isoformat(),
                "last": each.hours[-1].start.isoformat(),
                "filled": [hour.start.isoformat() for hour in each.hours if hour.filled],
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        manifest[dataset] = {**source, "series": written}
    json.dump(manifest, sys.stdout, indent=1, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def challenge_series(archive: Path) -> list[Series]:
    """Each 2024 compartment's drivers, from 3 September to its harvest day."""
    series: list[Series] = []
    with zipfile.ZipFile(archive) as opened:
        names = members(opened)
        for number, compartment in COMPARTMENTS.items():
            (member,) = [n for n in names if n.endswith("/" + compartment.timeseries_member)]
            reader = csv.DictReader(io.StringIO(opened.read(member).decode("utf-8")))
            rows = list(reader)
            readings = [
                Reading(
                    datetime.fromisoformat(row["time"]),
                    _value(row[TEMPERATURE]),
                    _value(row[PAR]),
                    _value(row[CO2]),
                )
                for row in rows
            ]
            densities = [
                (datetime.fromisoformat(row["time"]), float(row[DENSITY]))
                for row in rows
                if holds(row[DENSITY])
            ]
            (day_of_year,) = {
                int(float(row[HARVEST_DAY])) for row in rows if holds(row[HARVEST_DAY])
            }
            harvest_day = date(HARVEST_YEAR, 1, 1) + timedelta(days=day_of_year - 1)
            end = datetime.combine(harvest_day, datetime.min.time(), DAYS)
            series.append(Series(number, hourly(readings, densities, CHALLENGE_START, end)))
    return series


def pretrial_series(archive: Path) -> list[Series]:
    """Each 2023 light zone's drivers, from 5 September to 9 November."""
    with zipfile.ZipFile(archive) as opened:
        (member,) = [n for n in members(opened) if Path(n).name == PRETRIAL_CLIMATE]
        book = openpyxl.load_workbook(io.BytesIO(opened.read(member)), data_only=True)
    rows = list(book[PRETRIAL_CLIMATE_SHEET].iter_rows(values_only=True))
    header = [str(cell) for cell in rows[0]]
    at = header.index(PRETRIAL_TIME)
    temperature, co2 = header.index(PRETRIAL_TEMPERATURE), header.index(PRETRIAL_CO2)
    densities = [
        (datetime.combine(day, datetime.min.time(), DAYS), plants)
        for day, plants in PRETRIAL_DENSITY
    ]
    series: list[Series] = []
    for zone, column in PRETRIAL_ZONES.items():
        par = header.index(column)
        readings = [
            reading
            for row in rows[1:]
            if (reading := _pretrial_reading(row, at, temperature, par, co2)) is not None
        ]
        series.append(Series(zone, hourly(readings, densities, PRETRIAL_START, PRETRIAL_END)))
    return series


def hourly(
    readings: Iterable[Reading],
    densities: Sequence[tuple[datetime, float]],
    start: datetime,
    end: datetime,
) -> list[Hour]:
    """Each hour from `start` to `end` (not included), from the readings
    and the densities written, each at its moment."""
    sums: dict[datetime, list[list[float]]] = {}
    for reading in readings:
        hour = reading.at.astimezone(DAYS).replace(minute=0, second=0, microsecond=0)
        if not start <= hour < end:
            continue
        values = (reading.temperature_c, reading.par_umol_m2_s, reading.co2_ppm)
        bins = sums.setdefault(hour, [[], [], []])
        for index, value in enumerate(values):
            if value is not None:
                bins[index].append(value)
    steps = sorted((moment.astimezone(DAYS), plants) for moment, plants in densities)
    hours: list[Hour] = []
    previous: tuple[float, float, float] | None = None
    hour = start
    while hour < end:
        present = sums.get(hour, [[], [], []])
        if previous is None and not all(present):
            raise ValueError(f"a driver is missing at {hour.isoformat()}, the series' first hour")
        means = (
            _mean_or(present[0], previous, 0),
            _mean_or(present[1], previous, 1),
            _mean_or(present[2], previous, 2),
        )
        hours.append(Hour(hour, *means, _in_force(steps, hour), filled=not all(present)))
        previous = means
        hour += HOUR
    return hours


def _mean_or(
    values: Sequence[float], previous: tuple[float, float, float] | None, index: int
) -> float:
    """The mean of an hour's values of a driver, or the hour before's mean
    of it if the hour has none."""
    if values:
        return sum(values) / len(values)
    if previous is None:
        raise ValueError("a driver's first hour has no value")
    return previous[index]


def _pretrial_reading(
    row: Sequence[object], at: int, temperature: int, par: int, co2: int
) -> Reading | None:
    """A pre-trial row as a reading at its moment, or None for a row of no
    value. Its local time is given without an offset: one the clocks repeat
    is refused if it holds a value, since either moment could be meant."""
    stamp = row[at]
    if not isinstance(stamp, datetime):
        return None
    values = (_value(row[temperature]), _value(row[par]), _value(row[co2]))
    first, second = stamp.replace(tzinfo=LOCAL, fold=0), stamp.replace(tzinfo=LOCAL, fold=1)
    if first.utcoffset() != second.utcoffset():
        if any(value is not None for value in values):
            raise ValueError(f"{stamp.isoformat()} is a local time the clocks repeat")
        return None
    return Reading(first.astimezone(UTC), *values)


def _in_force(steps: Sequence[tuple[datetime, float]], hour: datetime) -> float:
    """The density written last at or before `hour`."""
    current: float | None = None
    for moment, plants in steps:
        if moment > hour:
            break
        current = plants
    if current is None:
        raise ValueError(f"no density is in force at {hour.isoformat()}")
    return current


def _value(cell: object) -> float | None:
    return float(str(cell)) if holds(cell) else None


def _number(value: float) -> str:
    return repr(round(value, DIGITS))


if __name__ == "__main__":
    raise SystemExit(main())
