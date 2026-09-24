from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.enums import EventSource, EventType
from greenhouse_protocol.event import Event


def _make_event(**overrides: object) -> Event:
    defaults: dict[str, object] = dict(
        event_id="evt_00392",
        greenhouse_id="gh_001",
        plant_id="plant_017",
        timestamp=datetime(2026, 1, 13, 10, 15, tzinfo=UTC),
        event_type=EventType.HARVEST,
        source=EventSource.HUMAN_REPORTED,
    )
    defaults.update(overrides)
    return Event(**defaults)


def test_event_constructs_with_required_fields() -> None:
    event = _make_event()

    assert event.event_type == EventType.HARVEST
    assert event.source == EventSource.HUMAN_REPORTED


def test_event_confidence_defaults_to_one() -> None:
    event = _make_event()

    assert event.confidence == 1.0


def test_event_parameters_default_to_empty_dict() -> None:
    event = _make_event()

    assert event.parameters == {}


def test_event_accepts_parameters_and_lower_confidence() -> None:
    event = _make_event(
        event_type=EventType.HARVEST,
        source=EventSource.INFERRED_FROM_OBSERVATIONS,
        confidence=0.94,
        parameters={"estimated_mass_g": 820},
    )

    assert event.confidence == 0.94
    assert event.parameters == {"estimated_mass_g": 820}


def test_event_is_immutable() -> None:
    event = _make_event()

    with pytest.raises(ValidationError):
        event.confidence = 0.5  # type: ignore[misc]


def test_event_type_has_expected_members() -> None:
    assert {member.value for member in EventType} == {
        "WATERING",
        "HARVEST",
        "LOWERING",
        "PRUNING",
        "FERTILISATION",
        "MANUAL_INSPECTION",
        "SPACING",
        "DESTRUCTIVE_SAMPLE",
    }


def test_event_source_has_expected_members() -> None:
    assert {member.value for member in EventSource} == {
        "HUMAN_REPORTED",
        "ROBOT_CONFIRMED",
        "CONTROL_SYSTEM",
        "INFERRED_FROM_OBSERVATIONS",
        "SIMULATION",
        "RULE_BASED_POLICY",
        "AGENT",
    }
