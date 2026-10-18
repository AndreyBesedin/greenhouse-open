"""The canonical tier writes only records that pass the protocol's
conformance checks, and nothing of a build whose records fail them; its
greenhouse is dated by the source, not by when the build ran."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.greenhouse import GreenhouseDescription, GreenhouseLayout
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

from greenhouse_adapters import cli
from greenhouse_adapters.canonical import (
    CanonicalGreenhouse,
    RefusedBuild,
    recording_start,
    write_canonical_greenhouse,
)
from greenhouse_adapters.storage.resolver import ArtifactResolver
from greenhouse_adapters.wur.agc4_pretrial_2023 import build as agc4_2023

START = datetime(2024, 9, 3, tzinfo=UTC)
GREENHOUSE_ID = "gh"


def _reading(index: int, value: float = 21.0, observation_id: str | None = None) -> Observation:
    return Observation(
        observation_id=observation_id or f"t{index}",
        greenhouse_id=GREENHOUSE_ID,
        plant_id=None,
        timestamp=START + timedelta(minutes=5 * index),
        observation_type=ObservationType.AIR_TEMPERATURE_C,
        value=value,
        source=RecordSource(type=SourceType.IMPORTED_DATA),
    )


def _write(
    directory: Path, observations: list[Observation], created_at: datetime | None = None
) -> CanonicalGreenhouse:
    return write_canonical_greenhouse(
        directory,
        greenhouse=GreenhouseDescription(
            greenhouse_id=GREENHOUSE_ID,
            name="a greenhouse",
            description="",
            source_type=SourceType.IMPORTED_DATA,
            layout=GreenhouseLayout(kind="compartment", rows=0, columns=0),
            plants=[],
            created_at=created_at or recording_start(observations),
        ),
        observations=observations,
        events=[],
        dataset_id="a dataset",
        dataset_version=1,
        adapter="an adapter",
        sources=[],
        selection={},
    )


def test_the_greenhouse_is_dated_by_its_first_reading() -> None:
    assert recording_start([_reading(2), _reading(0), _reading(1)]) == START


def test_a_source_with_no_readings_is_refused_rather_than_dated_by_the_clock() -> None:
    with pytest.raises(RefusedBuild, match="no readings"):
        recording_start([])


def test_conformant_records_are_written(tmp_path: Path) -> None:
    written = _write(tmp_path / "gh", [_reading(1), _reading(0)])

    assert [o.observation_id for o in written.observations()] == ["t0", "t1"]
    assert written.greenhouse().created_at == START


@pytest.mark.parametrize(
    ("records", "violation"),
    [
        ([_reading(0), _reading(1, value=float("nan"))], "non-finite value"),
        ([_reading(0), _reading(1, value=float("inf"))], "non-finite value"),
        ([_reading(0), _reading(1, observation_id="t0")], "describes two different instants"),
    ],
    ids=["NaN", "infinity", "duplicate id"],
)
def test_records_that_fail_the_protocols_checks_are_refused_and_nothing_is_written(
    tmp_path: Path, records: list[Observation], violation: str
) -> None:
    with pytest.raises(RefusedBuild, match=violation):
        _write(tmp_path / "gh", records)

    assert not (tmp_path / "gh").exists()


def test_records_built_without_validation_are_checked_before_they_are_sorted(
    tmp_path: Path,
) -> None:
    # A naive timestamp cannot be ordered beside an aware one.
    naive = _reading(1).model_copy(update={"timestamp": datetime(2024, 9, 3, 0, 5)})

    with pytest.raises(RefusedBuild, match="no timezone"):
        _write(tmp_path / "gh", [_reading(0), naive], created_at=START)

    assert not (tmp_path / "gh").exists()


def test_the_command_line_ends_a_refused_build_in_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refused(*args: object, **kwargs: object) -> CanonicalGreenhouse:
        raise RefusedBuild("1 conformance violation(s)")

    # Each artifact resolves to a path without a fetch, and the build refuses.
    monkeypatch.setattr(ArtifactResolver, "resolve", lambda self, manifest, name: tmp_path)
    monkeypatch.setattr(agc4_2023, "build_greenhouse", refused)

    status = cli.main(
        ["prepare", "wur", "agc4-2023", "--profile", "tiny", "--data-dir", str(tmp_path)]
    )

    assert status == 1
    assert capsys.readouterr().err == "greenhouse-data: error: 1 conformance violation(s)\n"
