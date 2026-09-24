from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource


def _make_observation(**overrides: object) -> Observation:
    defaults: dict[str, object] = dict(
        observation_id="obs_00001",
        greenhouse_id="gh_001",
        plant_id="plant_017",
        timestamp=datetime(2026, 1, 9, 12, 0, tzinfo=UTC),
        observation_type=ObservationType.SOIL_MOISTURE_PCT,
        value=38.0,
        source=RecordSource(type=SourceType.SIMULATION, source_id="sim_gh_001"),
    )
    defaults.update(overrides)
    return Observation(**defaults)


def test_observation_constructs_with_plant_level_fields() -> None:
    observation = _make_observation()

    assert observation.plant_id == "plant_017"
    assert observation.observation_type == ObservationType.SOIL_MOISTURE_PCT
    assert observation.value == 38.0


def test_observation_plant_id_is_optional_for_greenhouse_level_readings() -> None:
    observation = _make_observation(
        plant_id=None, observation_type=ObservationType.AIR_TEMPERATURE_C, value=31.2
    )

    assert observation.plant_id is None


def test_observation_is_immutable() -> None:
    observation = _make_observation()

    with pytest.raises(ValidationError):
        observation.value = 50.0  # type: ignore[misc]


def test_observation_type_keeps_the_plant_level_members() -> None:
    assert {member.value for member in ObservationType} >= {
        "soil_moisture_pct",
        "air_temperature_c",
        "visible_fruit_count",
        "ripe_fruit_count",
        "estimated_ripe_mass_g",
        "visible_height_cm",
    }
