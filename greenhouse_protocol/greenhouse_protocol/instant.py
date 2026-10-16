"""A record's instant: a datetime that says which instant it is.

Chronology is the timestamp alone, so every record's timestamps are
timezone-aware. A naive datetime names a wall-clock reading, which daylight
saving makes ambiguous twice a year, and cannot be ordered beside an aware
one: a store holding both fails to sort them.
"""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"a timestamp must be timezone-aware, not {value!r}")
    return value


type Instant = Annotated[datetime, AfterValidator(_aware)]
