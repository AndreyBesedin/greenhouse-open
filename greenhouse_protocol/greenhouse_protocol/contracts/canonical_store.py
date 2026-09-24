"""Where canonical records go once a producer has made them, and how a
consumer reads them back.

One contract per record kind, written from what producers and consumers
actually need: append records for a greenhouse, replace what a previous load
of the same greenhouse left behind, and read records back up to an instant.
A relational database is one implementation; a live source, a columnar
store or `greenhouse_protocol.contracts.memory` are others.

The contracts belong to no producer. The simulator and a recorded-data
adapter write through the same ones, which is what lets a consumer treat
simulated and recorded history alike: it reads observations, and never
learns which kind of producer wrote them.
"""

from datetime import datetime
from typing import Protocol

from greenhouse_protocol.enums import CaptureModality
from greenhouse_protocol.event import Event
from greenhouse_protocol.media import MediaCapture
from greenhouse_protocol.observation import Observation


class ObservationStore(Protocol):
    def save_many(self, items: list[Observation]) -> None: ...

    def delete_for_greenhouse(self, greenhouse_id: str) -> None: ...


class EventStore(Protocol):
    def save_many(self, items: list[Event]) -> None: ...

    def delete_for_greenhouse(self, greenhouse_id: str) -> None: ...


class ObservationQuery(Protocol):
    """Reading observations back, however they were produced.

    A consumer names this contract rather than the store that happens to
    hold the records. `up_to` is the temporal-honesty boundary every reader
    respects: a decision made at T must not see a reading from after T.
    """

    def list_for_greenhouse(
        self,
        greenhouse_id: str,
        *,
        compartment_id: str | None = None,
        plant_id: str | None = None,
        up_to: datetime | None = None,
    ) -> list[Observation]: ...


class EventQuery(Protocol):
    def list_for_greenhouse(
        self,
        greenhouse_id: str,
        *,
        compartment_id: str | None = None,
        plant_id: str | None = None,
        up_to: datetime | None = None,
    ) -> list[Event]: ...


class MediaQuery(Protocol):
    def list_for_greenhouse(
        self,
        greenhouse_id: str,
        *,
        compartment_id: str | None = None,
        sensor_id: str | None = None,
        modality: CaptureModality | None = None,
        up_to: datetime | None = None,
    ) -> list[MediaCapture]: ...
