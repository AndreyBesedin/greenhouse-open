import json
from pathlib import Path

import pytest

from greenhouse_adapters.manifests import ArtifactKind, list_manifest_ids, load_manifest
from greenhouse_adapters.storage.upstream_4tu import build_manifest
from greenhouse_adapters.wur.datasets import AGC4_CHALLENGE_2024, AGC4_PRETRIAL_2023, WUR_DATASETS

FIXTURES = Path(__file__).parent / "fixtures"


def test_every_known_wur_dataset_has_a_committed_manifest() -> None:
    assert set(list_manifest_ids()) >= {d.id for d in WUR_DATASETS.values()}


@pytest.mark.parametrize("dataset", [AGC4_PRETRIAL_2023, AGC4_CHALLENGE_2024])
def test_committed_manifests_are_complete_and_classified(dataset) -> None:  # type: ignore[no-untyped-def]
    manifest = load_manifest(dataset.id)

    assert manifest.source.dataset_uuid == dataset.dataset_uuid
    assert manifest.licence == "CC BY 4.0"
    assert manifest.artifacts, "a manifest with no artifacts is useless"
    for artifact in manifest.artifacts:
        assert artifact.size_bytes > 0
        assert len(artifact.md5) == 32
        assert artifact.download_url.startswith("https://data.4tu.nl/file/")
        assert artifact.kind == dataset.classify(artifact.name)
    # Phase 0's finding: the tabular data is tiny, the images are not.
    for tabular in manifest.artifacts_of_kind(ArtifactKind.TIMESERIES):
        assert tabular.size_bytes < 10 * 1024 * 1024
    for images in manifest.artifacts_of_kind(
        ArtifactKind.LABELLED_IMAGES, ArtifactKind.LONGITUDINAL_RGBD
    ):
        assert images.size_bytes > 1024**3


def test_storage_prefix_separates_provider_dataset_and_version() -> None:
    manifest = load_manifest(AGC4_CHALLENGE_2024.id)

    assert manifest.storage_prefix == Path("wur/agc4-challenge-2024/v1")


def test_build_manifest_takes_every_field_from_upstream_metadata() -> None:
    metadata = json.loads((FIXTURES / "4tu_agc4_challenge_2024.json").read_text())

    manifest = build_manifest(
        dataset_id=AGC4_CHALLENGE_2024.id,
        dataset_uuid=AGC4_CHALLENGE_2024.dataset_uuid,
        classify=AGC4_CHALLENGE_2024.classify,
        metadata=metadata,
    )

    assert manifest == load_manifest(AGC4_CHALLENGE_2024.id)
    assert [a.name for a in manifest.artifacts] == sorted(a.name for a in manifest.artifacts)
    timeseries = manifest.artifact("autonomous_greenhouse_challenge4_timeseries.zip")
    assert timeseries.kind == ArtifactKind.TIMESERIES
    assert timeseries.size_bytes == 6014133


def test_unknown_artifact_names_are_refused_rather_than_guessed() -> None:
    with pytest.raises(ValueError):
        AGC4_CHALLENGE_2024.classify("mystery_archive.zip")


def test_unknown_artifact_lookup_raises() -> None:
    with pytest.raises(KeyError):
        load_manifest(AGC4_CHALLENGE_2024.id).artifact("nope.zip")
