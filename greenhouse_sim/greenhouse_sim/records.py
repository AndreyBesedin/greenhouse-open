"""Identifiers for the records the simulator publishes.

Every producer keys its records by the instant they describe, as the WUR
adapter does (`wur24_c3.06_20241014T120000Z_air_temperature_c`).
Timestamps are the canonical chronology; simulation steps and days are
simulator metadata. A day counter inside a record's identity would be that
metadata leaking out: the simulator's clock, readable by anything that reads
the record, and a collision between two runs of the same scenario that
describe different instants.

The format matches the recorded adapters deliberately, so a consumer
cannot tell a simulated record from a real one by the shape of its
identifier - which is the whole point of a shared observation contract.
"""

from datetime import datetime

PREFIX = "sim"


def _stamp(timestamp: datetime) -> str:
    return timestamp.strftime("%Y%m%dT%H%M%SZ")


def observation_id(scope: str, timestamp: datetime, kind: str) -> str:
    """`scope` is the plant the reading describes, or the greenhouse when
    the reading is of the greenhouse as a whole."""
    return f"{PREFIX}_{scope}_{_stamp(timestamp)}_{kind}"


def event_id(scope: str, timestamp: datetime, kind: str) -> str:
    return f"{PREFIX}_{scope}_{_stamp(timestamp)}_{kind}"
