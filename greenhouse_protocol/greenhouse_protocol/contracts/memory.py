"""A reference implementation of the record contracts, held in memory.

Small enough to read in one sitting, and exact about the semantics a real
store must share:

- filters are exact matches, and a filter left as None does not filter;
- `up_to` is inclusive: a record stamped exactly at T is visible at T;
- records come back in chronological order, ties in the order they were
  saved (media captures: ties by capture id);
- saving a record whose identity is already stored is refused, because two
  records with one identity is a producer bug, not an update.

Useful for examples, for tests of a producer or consumer, and as the
specification a database-backed store is checked against.
"""

from collections.abc import Iterable, Iterator
from datetime import datetime

from greenhouse_protocol.enums import CaptureModality
from greenhouse_protocol.event import Event
from greenhouse_protocol.media import MediaCapture
from greenhouse_protocol.observation import Observation


class DuplicateRecord(ValueError):
    """A record with this identity is already stored."""


class InMemoryObservations:
    """Satisfies both `ObservationStore` and `ObservationQuery`."""

    def __init__(self) -> None:
        self._records: dict[str, Observation] = {}

    def save_many(self, items: list[Observation]) -> None:
        _refuse_duplicates(self._records, ((o.observation_id, o) for o in items))
        self._records.update((o.observation_id, o) for o in items)

    def delete_for_greenhouse(self, greenhouse_id: str) -> None:
        self._records = {
            key: o for key, o in self._records.items() if o.greenhouse_id != greenhouse_id
        }

    def list_for_greenhouse(
        self,
        greenhouse_id: str,
        *,
        compartment_id: str | None = None,
        plant_id: str | None = None,
        up_to: datetime | None = None,
    ) -> list[Observation]:
        matching = (
            o
            for o in self._records.values()
            if o.greenhouse_id == greenhouse_id
            and (compartment_id is None or o.compartment_id == compartment_id)
            and (plant_id is None or o.plant_id == plant_id)
            and (up_to is None or o.timestamp <= up_to)
        )
        return sorted(matching, key=lambda o: o.timestamp)


class InMemoryEvents:
    """Satisfies both `EventStore` and `EventQuery`."""

    def __init__(self) -> None:
        self._records: dict[str, Event] = {}

    def save_many(self, items: list[Event]) -> None:
        _refuse_duplicates(self._records, ((e.event_id, e) for e in items))
        self._records.update((e.event_id, e) for e in items)

    def delete_for_greenhouse(self, greenhouse_id: str) -> None:
        self._records = {
            key: e for key, e in self._records.items() if e.greenhouse_id != greenhouse_id
        }

    def list_for_greenhouse(
        self,
        greenhouse_id: str,
        *,
        compartment_id: str | None = None,
        plant_id: str | None = None,
        up_to: datetime | None = None,
    ) -> list[Event]:
        matching = (
            e
            for e in self._records.values()
            if e.greenhouse_id == greenhouse_id
            and (compartment_id is None or e.compartment_id == compartment_id)
            and (plant_id is None or e.plant_id == plant_id)
            and (up_to is None or e.timestamp <= up_to)
        )
        return sorted(matching, key=lambda e: e.timestamp)


class InMemoryMedia:
    """Satisfies `MediaQuery`, with a `save_many` to put captures in."""

    def __init__(self) -> None:
        self._records: dict[str, MediaCapture] = {}

    def save_many(self, items: list[MediaCapture]) -> None:
        _refuse_duplicates(self._records, ((c.capture_id, c) for c in items))
        self._records.update((c.capture_id, c) for c in items)

    def delete_for_greenhouse(self, greenhouse_id: str) -> None:
        self._records = {
            key: c for key, c in self._records.items() if c.greenhouse_id != greenhouse_id
        }

    def list_for_greenhouse(
        self,
        greenhouse_id: str,
        *,
        compartment_id: str | None = None,
        sensor_id: str | None = None,
        modality: CaptureModality | None = None,
        up_to: datetime | None = None,
    ) -> list[MediaCapture]:
        matching = (
            c
            for c in self._records.values()
            if c.greenhouse_id == greenhouse_id
            and (compartment_id is None or c.compartment_id == compartment_id)
            and (sensor_id is None or c.sensor_id == sensor_id)
            and (modality is None or c.modality == modality)
            and (up_to is None or c.timestamp <= up_to)
        )
        return sorted(matching, key=lambda c: (c.timestamp, c.capture_id))


def _refuse_duplicates[T](stored: dict[str, T], incoming: Iterable[tuple[str, T]]) -> None:
    seen: set[str] = set()
    for key in _keys(incoming):
        if key in stored or key in seen:
            raise DuplicateRecord(key)
        seen.add(key)


def _keys[T](pairs: Iterable[tuple[str, T]]) -> Iterator[str]:
    return (key for key, _ in pairs)
