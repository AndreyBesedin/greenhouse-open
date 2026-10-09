"""Recorded weather, read from a file (P07.7).

**The format** is a CSV: a `timestamp` column, an ISO 8601 instant with its
time zone, and a column for each quantity recorded, named after the
protocol's outside observation types (`outside_air_temperature_c`,
`outside_wind_speed_m_s`, …), in the units the names state, so that the
same name means the same thing in a record, a file and a run. The air's
temperature and relative humidity are needed; the rest may be left out,
the weather then taking its default: 420 ppm of CO₂, no wind, the standard
atmosphere's pressure at the site, no radiation and a clear sky. A file
without a wind vane's column has wind without a direction, which drives no
flow through the house, and a station reads none.

**Checked:** a column that is no outside quantity, a timestamp without a
time zone or not after the one before it, a value that is not a number or
lies outside its quantity's physical range, are refused, naming the row.

**Missing values:** an empty cell is a missing value. A gap of up to an
hour between a quantity's known values is interpolated across; within a
longer one the quantity is not known, and a run that reaches into it is
refused rather than invented.

**Replayed:** a recorded day is played from its first day's midnight at
the site at the run's start, so that any scenario can be run under it.

**Provenance:** a run under recorded weather is told apart by its file's
content (`identity`), so that it changes with the file.
"""

import csv
import hashlib
import io
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.weather.sources import WeatherSource
from greenhouse_sim.weather.state import OUTSIDE_CO2_PPM, WeatherState
from greenhouse_sim.world.site import Site, bearing

# Where the recorded weather files a scenario can be run under are kept.
RECORDED_DIRECTORY: Final = Path(__file__).parent / "recorded"
TIMESTAMP: Final = "timestamp"
PREFIX: Final = "outside_"
# The quantities a file must give.
REQUIRED: Final = ("air_temperature_c", "relative_humidity_pct")
# What a file may leave out, and what the weather then is.
DEFAULTS: Final[dict[str, float | None]] = {
    "co2_ppm": OUTSIDE_CO2_PPM,
    "wind_speed_m_s": 0.0,
    "wind_direction_deg": None,
    "global_radiation_w_m2": 0.0,
    "cloud_cover_pct": 0.0,
}
# The range each quantity's values may lie in.
RANGES: Final = {
    "air_temperature_c": (-60.0, 60.0),
    "relative_humidity_pct": (0.0, 100.0),
    "co2_ppm": (100.0, 5_000.0),
    "wind_speed_m_s": (0.0, 75.0),
    "wind_direction_deg": (0.0, 360.0),
    "barometric_pressure_hpa": (850.0, 1_100.0),
    "global_radiation_w_m2": (0.0, 1_500.0),
    "cloud_cover_pct": (0.0, 100.0),
}
# The longest gap between known values interpolated across.
LONGEST_GAP: Final = timedelta(hours=1)
HALF_TURN_DEG: Final = 180.0
# A file's first data row is its second line.
FIRST_ROW: Final = 2


class WeatherFileError(ValueError):
    """A weather file that cannot be read, and the row that says why."""


@dataclass(frozen=True)
class _Known:
    """A quantity's known values, at their moments, in order."""

    moments: list[datetime]
    values: list[float]


def _quantity(column: str, row: int) -> str:
    name = column.removeprefix(PREFIX)
    if not column.startswith(PREFIX) or name not in RANGES:
        raise WeatherFileError(f"row {row}: no outside quantity is called {column!r}")
    return name


def read_records(text: str) -> dict[str, _Known]:
    """Each quantity a weather file records, its known values at their
    moments; a file that cannot be read is refused, naming the row."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or TIMESTAMP not in rows[0]:
        raise WeatherFileError(f"row 1: a weather file starts with a {TIMESTAMP!r} column")
    header = rows[0]
    names = [None if column == TIMESTAMP else _quantity(column, 1) for column in header]
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        raise WeatherFileError(f"row 1: a weather file gives {PREFIX}{missing[0]}")
    known = {name: _Known([], []) for name in names if name is not None}
    before: datetime | None = None
    for number, row in enumerate(rows[1:], start=FIRST_ROW):
        cells = dict(zip(header, row, strict=False))
        try:
            moment = datetime.fromisoformat(cells.get(TIMESTAMP, ""))
        except ValueError:
            raise WeatherFileError(
                f"row {number}: {cells.get(TIMESTAMP, '')!r} is no ISO 8601 timestamp"
            ) from None
        if moment.utcoffset() is None:
            raise WeatherFileError(f"row {number}: its timestamp has no time zone")
        if before is not None and moment <= before:
            raise WeatherFileError(f"row {number}: its timestamp is not after the row's before")
        before = moment
        for column, name in zip(header, names, strict=True):
            text_value = cells.get(column, "").strip()
            if name is None or not text_value:
                continue
            try:
                value = float(text_value)
            except ValueError:
                raise WeatherFileError(
                    f"row {number}: {column} is not a number: {text_value!r}"
                ) from None
            low, high = RANGES[name]
            if not (low <= value <= high and math.isfinite(value)):
                raise WeatherFileError(
                    f"row {number}: {column} is {value:g}, outside {low:g} to {high:g}"
                )
            known[name].moments.append(moment)
            known[name].values.append(value)
    return known


def _between(known: _Known, moment: datetime, name: str) -> tuple[float, float, float] | None:
    """A known value's neighbours either side of `moment` and its share of
    the way between, or None if the quantity is not known then."""
    moments = known.moments
    after = bisect_right(moments, moment)
    if after > 0 and moments[after - 1] == moment:
        value = known.values[after - 1]
        return value, value, 0.0
    if after == 0 or after == len(moments):
        return None
    start, end = moments[after - 1], moments[after]
    if end - start > LONGEST_GAP:
        raise ValueError(
            f"the recorded weather does not know {PREFIX}{name} from "
            f"{start.isoformat()} to {end.isoformat()}"
        )
    return known.values[after - 1], known.values[after], (moment - start) / (end - start)


@dataclass(frozen=True)
class _Recorded:
    known: dict[str, _Known]
    site: Site
    # How far the file's moments lie ahead of the run's.
    offset: timedelta

    def at(self, moment: datetime) -> WeatherState:
        if moment.utcoffset() is None:
            raise ValueError(f"a moment has a time zone: {moment.isoformat()}")
        recorded = moment + self.offset
        values: dict[str, float | None] = {}
        for name in RANGES:
            known = self.known.get(name)
            if known is None or not known.moments:
                values[name] = (
                    self.site.standard_pressure_hpa()
                    if name == "barometric_pressure_hpa"
                    else DEFAULTS[name]
                )
                continue
            between = _between(known, recorded, name)
            if between is None:
                raise ValueError(
                    f"the recorded weather is known from {known.moments[0].isoformat()} to "
                    f"{known.moments[-1].isoformat()}, not at {recorded.isoformat()}"
                )
            earlier, later, share = between
            if name == "wind_direction_deg":
                # The shorter way round.
                turn = bearing(later - earlier + HALF_TURN_DEG) - HALF_TURN_DEG
                values[name] = bearing(earlier + share * turn)
            else:
                values[name] = (1.0 - share) * earlier + share * later
        return WeatherState.model_validate(values)


class RecordedWeather(BaseModel):
    """Weather recorded in a file of the recorded weather's directory, by its
    name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["recorded"] = "recorded"
    file: str

    def path(self) -> Path:
        return RECORDED_DIRECTORY / self.file

    def identity(self) -> str:
        """Its file's content, as a digest: a run under it is told apart by
        it."""
        return hashlib.sha256(self.path().read_bytes()).hexdigest()

    def source(self, site: Site, seed: int = 0, start: datetime | None = None) -> WeatherSource:
        """Its weather at `site`, its first day's midnight replayed at
        `start`; nothing in it is drawn from `seed`."""
        known = read_records(self.path().read_text())
        first = min(series.moments[0] for series in known.values() if series.moments)
        local = first.astimezone(site.zone())
        midnight = site.midnight(local.date())
        offset = timedelta(0) if start is None else midnight - start
        return _Recorded(known, site, offset)


def recorded_weathers() -> dict[str, RecordedWeather]:
    """The recorded weather files a scenario can be run under, by name."""
    return {
        path.stem: RecordedWeather(file=path.name)
        for path in sorted(RECORDED_DIRECTORY.glob("*.csv"))
    }
