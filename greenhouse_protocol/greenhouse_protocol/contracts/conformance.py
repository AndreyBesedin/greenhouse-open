"""Checks any producer's records must pass, whatever produced them.

These are contract checks written as plain functions rather than as test
cases, so a producer can call them on its own output - in its own test
suite, in a notebook, or in a pipeline before records are stored.

Each rule states something the canonical contract means, not something the
Pydantic models already enforce. A model guarantees that a timestamp is a
datetime; it cannot guarantee that the datetime is unambiguous, that a
reading is a number rather than a placeholder, or that two records
describing different moments have different identities. Those are the
properties a consumer actually relies on, and the properties a new adapter
is most likely to get wrong.

Every function returns a list of human-readable violations, empty when the
records conform, so a caller can report all of them at once rather than
stopping at the first.
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Protocol

from greenhouse_protocol.event import Event
from greenhouse_protocol.media import MediaCapture
from greenhouse_protocol.observation import Observation


class CanonicalRecord(Protocol):
    """What every canonical record has: a greenhouse and an instant.

    Observations, events and captures share this much, which is what the
    shared checks below are written against.
    """

    @property
    def greenhouse_id(self) -> str: ...

    @property
    def timestamp(self) -> datetime: ...


def check_observations(observations: Iterable[Observation]) -> list[str]:
    records = list(observations)
    violations: list[str] = []
    violations += _check_timestamps_are_unambiguous(records, "observation")
    violations += _check_identities_are_unique(
        [(o.observation_id, o.timestamp) for o in records], "observation"
    )
    violations += _check_scoping(records, "observation")

    for observation in records:
        if not math.isfinite(observation.value):
            violations.append(
                f"observation {observation.observation_id!r} has a non-finite value "
                f"({observation.value!r}): a gap is an absent record, not a NaN"
            )
        if not observation.source.type.strip():
            violations.append(f"observation {observation.observation_id!r} has no source type")
    return violations


def check_events(events: Iterable[Event]) -> list[str]:
    records = list(events)
    violations: list[str] = []
    violations += _check_timestamps_are_unambiguous(records, "event")
    violations += _check_identities_are_unique(
        [(e.event_id, e.timestamp) for e in records], "event"
    )
    violations += _check_scoping(records, "event")

    for event in records:
        if not 0.0 <= event.confidence <= 1.0:
            violations.append(
                f"event {event.event_id!r} has confidence {event.confidence!r}, "
                "which is outside 0..1"
            )
    return violations


def check_media(captures: Iterable[MediaCapture]) -> list[str]:
    records = list(captures)
    violations: list[str] = []
    violations += _check_timestamps_are_unambiguous(records, "capture")
    violations += _check_identities_are_unique(
        [(c.capture_id, c.timestamp) for c in records], "capture"
    )

    for capture in records:
        if not capture.artifact_uri.strip():
            violations.append(f"capture {capture.capture_id!r} has an empty artifact reference")
        if not capture.sensor_id.strip():
            violations.append(f"capture {capture.capture_id!r} names no sensor")
    return violations


def _check_timestamps_are_unambiguous(records: Sequence[CanonicalRecord], kind: str) -> list[str]:
    """Canonical chronology is an instant, not a wall-clock reading.

    A naive datetime is ambiguous twice a year in any greenhouse that
    observes daylight saving, which the WUR recordings do.
    """
    violations = []
    for record in records:
        timestamp = record.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            violations.append(f"a {kind} has a timestamp with no timezone: {timestamp!r}")
    return violations


def _check_identities_are_unique(
    identities: Sequence[tuple[str, datetime]], kind: str
) -> list[str]:
    """Two records describing different moments must not share an identity.

    Keying records by a step counter, for example, collides across runs
    that describe different instants.
    """
    violations = []
    seen: dict[str, datetime] = {}
    for record_id, timestamp in identities:
        if not record_id.strip():
            violations.append(f"a {kind} has an empty identifier")
            continue
        previous = seen.get(record_id)
        if previous is not None and previous != timestamp:
            violations.append(
                f"{kind} id {record_id!r} describes two different instants "
                f"({previous!r} and {timestamp!r})"
            )
        seen[record_id] = timestamp

    duplicates = [rid for rid, count in Counter(rid for rid, _ in identities).items() if count > 1]
    if duplicates:
        violations.append(
            f"{len(duplicates)} {kind} id(s) appear more than once, e.g. {sorted(duplicates)[:3]}"
        )
    return violations


def _check_scoping(records: Sequence[CanonicalRecord], kind: str) -> list[str]:
    """A record says what it describes: a greenhouse, one of its
    compartments, or one plant. It must at least name its greenhouse."""
    violations = []
    for record in records:
        if not record.greenhouse_id.strip():
            violations.append(f"a {kind} names no greenhouse")
    return violations
