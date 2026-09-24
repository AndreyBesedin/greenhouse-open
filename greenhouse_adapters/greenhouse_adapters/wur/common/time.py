"""WUR timestamps arrive in Dutch local time - the 2024 CSVs with an explicit
offset (+02:00 / +01:00 across the DST change), the 2023 workbooks as Excel
serial dates or MATLAB datenums with none. Everything becomes a timezone-aware UTC datetime
here, so downstream ordering and "<= T" comparisons are exact."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WUR_LOCAL_TIMEZONE = ZoneInfo("Europe/Amsterdam")

_EXCEL_EPOCH = datetime(1899, 12, 30)
# MATLAB datenum 1 is 1 January of year 0; Python ordinal 1 is 1 January of
# year 1, 366 days later.
_MATLAB_ORDINAL_OFFSET = 366


def parse_offset_timestamp(value: str) -> datetime:
    """'2024-09-03 00:05:00+02:00' -> aware UTC datetime."""
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None:
        raise ValueError(f"WUR timestamp {value!r} has no UTC offset")
    return parsed.astimezone(UTC)


def local_noon(day: date) -> datetime:
    """A manual measurement whose source gives only a date: pinned to local
    noon so it sorts inside that day's readings rather than at midnight."""
    return datetime.combine(day, time(12, 0), tzinfo=WUR_LOCAL_TIMEZONE).astimezone(UTC)


def excel_serial_to_utc(serial: float) -> datetime:
    """Excel serial day number in Dutch local time -> aware UTC datetime,
    rounded to the nearest second (serials carry float noise)."""
    naive = _EXCEL_EPOCH + timedelta(days=serial)
    naive = (naive + timedelta(microseconds=500_000)).replace(microsecond=0)
    return naive.replace(tzinfo=WUR_LOCAL_TIMEZONE).astimezone(UTC)


def matlab_datenum_to_utc(datenum: float) -> datetime:
    """MATLAB datenum in Dutch local wall-clock time -> aware UTC datetime,
    rounded to the nearest second (datenums carry float noise).

    A local time that occurs twice (the hour the clocks go back) or never
    (the hour they go forward) has no single UTC instant. It is refused
    rather than guessed: the 2023 export leaves that hour's rows empty, so a
    reading there means the source changed."""
    whole = int(datenum)
    naive = datetime.fromordinal(whole - _MATLAB_ORDINAL_OFFSET) + timedelta(days=datenum - whole)
    naive = (naive + timedelta(microseconds=500_000)).replace(microsecond=0)
    first = naive.replace(tzinfo=WUR_LOCAL_TIMEZONE, fold=0)
    as_utc = first.astimezone(UTC)
    # A time in the spring gap does not survive the round trip; both folds of
    # a gap time also have different offsets, so this check has to come first.
    if as_utc.astimezone(WUR_LOCAL_TIMEZONE).replace(tzinfo=None) != naive:
        raise ValueError(f"local time {naive.isoformat()} does not exist in {WUR_LOCAL_TIMEZONE}")
    second = naive.replace(tzinfo=WUR_LOCAL_TIMEZONE, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError(f"local time {naive.isoformat()} occurs twice in {WUR_LOCAL_TIMEZONE}")
    return as_utc
