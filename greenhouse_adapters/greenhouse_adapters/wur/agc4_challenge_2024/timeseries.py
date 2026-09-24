"""5-minute CSVs -> canonical Observations (long form: one record per
timestamp per mapped channel with a value).

A compartment's file describes that compartment. The weather and forecast
files describe the site, so their observations name no compartment and are
reconstructed into the greenhouse-level environment."""

import csv
from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime

from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_adapters.wur.agc4_challenge_2024 import SOURCE_ID
from greenhouse_adapters.wur.agc4_challenge_2024.channels import (
    CHANNELS,
    FORECAST_CHANNELS,
    FORECAST_MEMBER,
    HARVEST_DAY_COLUMN,
    RECODED,
    TIME_COLUMN,
    WEATHER_CHANNELS,
    WEATHER_MEMBER,
    ZERO_PLACEHOLDER_CHANNELS,
    ZERO_PLACEHOLDER_MAX,
)
from greenhouse_adapters.wur.agc4_challenge_2024.compartments import GREENHOUSE_ID, Compartment
from greenhouse_adapters.wur.common.time import WUR_LOCAL_TIMEZONE, parse_offset_timestamp

SOURCE = RecordSource(type=SourceType.IMPORTED_DATA, source_id=SOURCE_ID)
_SITE_SCOPE = "site"


def parse_timeseries(lines: Iterable[str], compartment: Compartment) -> Iterator[Observation]:
    """A compartment's file, in file order (chronological in the source).
    Empty cells are gaps, not zeros: they yield nothing."""
    return _parse(
        lines,
        member=compartment.timeseries_member,
        channels=CHANNELS,
        compartment_id=compartment.compartment_id,
        scope=f"c{compartment.code}",
    )


def parse_weather(lines: Iterable[str]) -> Iterator[Observation]:
    """The site's measured outside weather."""
    return _parse(
        lines,
        member=WEATHER_MEMBER,
        channels=WEATHER_CHANNELS,
        compartment_id=None,
        scope=_SITE_SCOPE,
    )


def parse_forecast(lines: Iterable[str]) -> Iterator[Observation]:
    """The site's weather forecast - only the channels that can be read as
    "known at the row's time" (see channels.py)."""
    return _parse(
        lines,
        member=FORECAST_MEMBER,
        channels=FORECAST_CHANNELS,
        compartment_id=None,
        scope=_SITE_SCOPE,
    )


def final_harvest_timestamp(lines: Iterable[str], compartment: Compartment) -> datetime | None:
    """When the compartment's final harvest happened: the row carrying the
    recorded harvest day. The dataset writes the day of year once, on the
    harvest day's last row, so that row's timestamp is the harvest instant.
    The day number is checked against the row's local date rather than
    trusted blindly. None when the file records no harvest day."""
    reader = csv.DictReader(lines)
    if reader.fieldnames is None or HARVEST_DAY_COLUMN not in reader.fieldnames:
        return None
    for row in reader:
        raw = row.get(HARVEST_DAY_COLUMN) or ""
        if not raw.strip():
            continue
        timestamp = parse_offset_timestamp(row[TIME_COLUMN])
        local_day = timestamp.astimezone(WUR_LOCAL_TIMEZONE).timetuple().tm_yday
        if int(float(raw)) != local_day:
            raise ValueError(
                f"{compartment.timeseries_member}: harvest day {raw} does not match the "
                f"row's local day of year {local_day} ({row[TIME_COLUMN]})"
            )
        return timestamp
    return None


def observation_id(compartment: Compartment, timestamp: datetime, kind: str) -> str:
    return _observation_id(f"c{compartment.code}", timestamp, kind)


def _parse(
    lines: Iterable[str],
    *,
    member: str,
    channels: Mapping[str, ObservationType],
    compartment_id: str | None,
    scope: str,
) -> Iterator[Observation]:
    reader = csv.DictReader(lines)
    if reader.fieldnames is None or TIME_COLUMN not in reader.fieldnames:
        raise ValueError(f"{member} has no {TIME_COLUMN!r} column")
    mapped = [(column, channels[column]) for column in reader.fieldnames if column in channels]
    if not mapped:
        raise ValueError(f"{member} has none of the expected channels")

    for row in reader:
        timestamp = parse_offset_timestamp(row[TIME_COLUMN])
        for column, observation_type in mapped:
            raw = row.get(column, "")
            if raw is None or raw.strip() == "":
                continue
            value = float(raw)
            codes = RECODED.get(column)
            if codes is not None:
                if value not in codes:
                    raise ValueError(
                        f"{member}: {column} has unexpected code {raw!r} at {row[TIME_COLUMN]}"
                    )
                value = codes[value]
            if column in ZERO_PLACEHOLDER_CHANNELS and 0 < value <= ZERO_PLACEHOLDER_MAX:
                value = 0.0
            yield Observation(
                observation_id=_observation_id(scope, timestamp, observation_type.value),
                greenhouse_id=GREENHOUSE_ID,
                compartment_id=compartment_id,
                plant_id=None,
                timestamp=timestamp,
                observation_type=observation_type,
                value=value,
                source=SOURCE,
            )


def _observation_id(scope: str, timestamp: datetime, kind: str) -> str:
    return f"wur24_{scope}_{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{kind}"
