from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_protocol.contracts.canonical_store import (
    EventQuery,
    EventStore,
    MediaQuery,
    ObservationQuery,
    ObservationStore,
)
from greenhouse_protocol.contracts.memory import (
    DuplicateRecord,
    InMemoryEvents,
    InMemoryMedia,
    InMemoryObservations,
)
from greenhouse_protocol.enums import (
    CaptureModality,
    EventSource,
    EventType,
    ObservationType,
    SourceType,
)
from greenhouse_protocol.event import Event
from greenhouse_protocol.media import MediaCapture
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

T0 = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
SOURCE = RecordSource(type=SourceType.SIMULATION, source_id="test")


def _observation(
    observation_id: str,
    at: datetime,
    *,
    greenhouse_id: str = "gh",
    compartment_id: str | None = None,
    plant_id: str | None = None,
) -> Observation:
    return Observation(
        observation_id=observation_id,
        greenhouse_id=greenhouse_id,
        compartment_id=compartment_id,
        plant_id=plant_id,
        timestamp=at,
        observation_type=ObservationType.AIR_TEMPERATURE_C,
        value=21.0,
        source=SOURCE,
    )


def test_the_memory_stores_satisfy_the_contracts() -> None:
    """The annotations are the assertion: mypy rejects this file otherwise."""
    observations = InMemoryObservations()
    events = InMemoryEvents()
    written: tuple[ObservationStore, EventStore] = (observations, events)
    read: tuple[ObservationQuery, EventQuery, MediaQuery] = (
        observations,
        events,
        InMemoryMedia(),
    )
    assert written and read


def test_records_come_back_in_chronological_order() -> None:
    store = InMemoryObservations()
    store.save_many([_observation("b", T0 + timedelta(hours=1)), _observation("a", T0)])

    assert [o.observation_id for o in store.list_for_greenhouse("gh")] == ["a", "b"]


def test_up_to_is_inclusive_and_hides_the_future() -> None:
    store = InMemoryObservations()
    store.save_many(
        [
            _observation("at", T0),
            _observation("after", T0 + timedelta(seconds=1)),
        ]
    )

    assert [o.observation_id for o in store.list_for_greenhouse("gh", up_to=T0)] == ["at"]


def test_filters_are_exact_and_none_means_no_filter() -> None:
    store = InMemoryObservations()
    store.save_many(
        [
            _observation("house", T0),
            _observation("c1", T0, compartment_id="c1"),
            _observation("p1", T0, compartment_id="c1", plant_id="p1"),
            _observation("elsewhere", T0, greenhouse_id="other"),
        ]
    )

    assert {o.observation_id for o in store.list_for_greenhouse("gh")} == {"house", "c1", "p1"}
    assert {o.observation_id for o in store.list_for_greenhouse("gh", compartment_id="c1")} == {
        "c1",
        "p1",
    }
    assert [o.observation_id for o in store.list_for_greenhouse("gh", plant_id="p1")] == ["p1"]


def test_a_second_record_with_the_same_identity_is_refused() -> None:
    store = InMemoryObservations()
    store.save_many([_observation("a", T0)])

    with pytest.raises(DuplicateRecord):
        store.save_many([_observation("a", T0 + timedelta(hours=1))])
    with pytest.raises(DuplicateRecord):
        store.save_many([_observation("b", T0), _observation("b", T0)])
    assert [o.observation_id for o in store.list_for_greenhouse("gh")] == ["a"]


def test_deleting_a_greenhouse_leaves_the_others() -> None:
    store = InMemoryObservations()
    store.save_many([_observation("a", T0), _observation("z", T0, greenhouse_id="other")])

    store.delete_for_greenhouse("gh")

    assert store.list_for_greenhouse("gh") == []
    assert [o.observation_id for o in store.list_for_greenhouse("other")] == ["z"]


def test_events_follow_the_same_rules() -> None:
    store = InMemoryEvents()
    event = Event(
        event_id="e1",
        greenhouse_id="gh",
        plant_id=None,
        timestamp=T0,
        event_type=EventType.HARVEST,
        source=EventSource.HUMAN_REPORTED,
    )
    store.save_many([event])

    assert store.list_for_greenhouse("gh", up_to=T0) == [event]
    assert store.list_for_greenhouse("gh", up_to=T0 - timedelta(seconds=1)) == []
    with pytest.raises(DuplicateRecord):
        store.save_many([event])


def test_media_ties_are_ordered_by_capture_id_and_filter_by_modality() -> None:
    store = InMemoryMedia()

    def capture(capture_id: str, modality: CaptureModality) -> MediaCapture:
        return MediaCapture(
            capture_id=capture_id,
            greenhouse_id="gh",
            sensor_id="cam",
            timestamp=T0,
            modality=modality,
            artifact_uri=f"dataset/archive.zip!{capture_id}.png",
            source=SOURCE,
        )

    store.save_many([capture("b", CaptureModality.RGB), capture("a", CaptureModality.DEPTH)])

    assert [c.capture_id for c in store.list_for_greenhouse("gh")] == ["a", "b"]
    assert [
        c.capture_id for c in store.list_for_greenhouse("gh", modality=CaptureModality.RGB)
    ] == ["b"]
