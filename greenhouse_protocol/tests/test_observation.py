import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.enums import ObservationQuality, ObservationType, SourceType
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


def test_an_observation_may_name_its_sensor_its_delivery_and_its_quality() -> None:
    taken = datetime(2026, 1, 9, 12, 0, tzinfo=UTC)
    observation = _make_observation(
        plant_id=None,
        observation_type=ObservationType.AIR_SPEED_M_S,
        value=0.4,
        sensor_id="anemometer_1",
        delivered_at=taken.replace(second=30),
        quality={ObservationQuality.CLIPPED},
    )

    assert observation.sensor_id == "anemometer_1"
    assert observation.delivered_at == taken.replace(second=30)
    assert observation.quality == frozenset({ObservationQuality.CLIPPED})


def test_an_observation_that_names_none_of_them_is_written_as_before() -> None:
    written = json.loads(_make_observation().model_dump_json())

    assert set(written) == {
        "observation_id",
        "greenhouse_id",
        "compartment_id",
        "plant_id",
        "timestamp",
        "observation_type",
        "value",
        "source",
    }
    assert _make_observation(quality=set()).model_dump() == _make_observation().model_dump()


def test_an_observation_with_them_survives_being_written_and_read() -> None:
    observation = _make_observation(
        sensor_id="t_1",
        delivered_at=datetime(2026, 1, 9, 12, 1, tzinfo=UTC),
        quality={ObservationQuality.CLIPPED},
    )

    assert Observation.model_validate_json(observation.model_dump_json()) == observation


def test_a_delivery_before_the_reading_or_without_a_timezone_does_not_conform() -> None:
    taken = datetime(2026, 1, 9, 12, 0, tzinfo=UTC)
    early = _make_observation(delivered_at=datetime(2026, 1, 9, 11, 59, tzinfo=UTC))
    naive = _make_observation(observation_id="obs_2", delivered_at=datetime(2026, 1, 9, 12, 1))
    unnamed = _make_observation(observation_id="obs_3", sensor_id=" ")
    on_time = _make_observation(observation_id="obs_4", delivered_at=taken, sensor_id="t_1")

    violations = check_observations([early, naive, unnamed, on_time])

    assert len(violations) == 3
    assert "before it was taken" in violations[0]
    assert "no timezone" in violations[1]
    assert "empty sensor" in violations[2]
