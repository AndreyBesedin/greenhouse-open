import hashlib
from pathlib import Path

import pytest

from greenhouse_adapters.manifests import (
    ArtifactKind,
    ArtifactManifest,
    DatasetManifest,
    DatasetSource,
)
from greenhouse_adapters.storage.layout import DATA_DIR_ENV_VAR, DataDirectory
from greenhouse_adapters.storage.resolver import (
    ArtifactResolver,
    ArtifactUnavailable,
    ChecksumMismatch,
)

CONTENT = b"time,compartment/air_temperature\n2024-09-03 00:00:00+02:00,20.1\n"


def _manifest(size: int = len(CONTENT), md5: str | None = None) -> DatasetManifest:
    return DatasetManifest(
        id="wur_test-dataset",
        version=1,
        title="Test",
        source=DatasetSource(provider="4tu", dataset_uuid="uuid", doi="10.4121/x"),
        licence="CC BY 4.0",
        artifacts=[
            ArtifactManifest(
                name="timeseries.zip",
                kind=ArtifactKind.TIMESERIES,
                size_bytes=size,
                md5=md5 or hashlib.md5(CONTENT).hexdigest(),
                download_url="https://example.invalid/timeseries.zip",
            )
        ],
    )


class RecordingMirror:
    def __init__(self, name: str, *, has_it: bool, content: bytes = CONTENT) -> None:
        self.name = name
        self.has_it = has_it
        self.content = content
        self.calls = 0

    def fetch(self, artifact: ArtifactManifest, destination: Path) -> bool:
        self.calls += 1
        if not self.has_it:
            return False
        destination.write_bytes(self.content)
        return True


def test_data_directory_reads_root_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path / "data"))

    layout = DataDirectory()

    assert layout.root == (tmp_path / "data").resolve()
    assert layout.raw(_manifest()) == layout.root / "raw" / "wur" / "test-dataset" / "v1"
    assert (
        layout.canonical(_manifest()) == layout.root / "canonical" / "wur" / "test-dataset" / "v1"
    )


def test_local_copy_wins_without_consulting_any_mirror(tmp_path: Path) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest()
    local = layout.raw(manifest) / "timeseries.zip"
    local.parent.mkdir(parents=True)
    local.write_bytes(CONTENT)
    mirror = RecordingMirror("mirror", has_it=True)
    resolver = ArtifactResolver(layout, mirrors=[mirror])

    assert resolver.resolve(manifest, "timeseries.zip") == local
    assert mirror.calls == 0


def test_mirrors_are_tried_in_order_and_the_first_hit_is_verified_and_kept(
    tmp_path: Path,
) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest()
    first = RecordingMirror("s3", has_it=False)
    second = RecordingMirror("upstream", has_it=True)
    resolver = ArtifactResolver(layout, mirrors=[first, second])

    path = resolver.resolve(manifest, "timeseries.zip")

    assert path.read_bytes() == CONTENT
    assert (first.calls, second.calls) == (1, 1)
    # A second resolve is served locally, without re-hashing or re-fetching.
    assert resolver.resolve(manifest, "timeseries.zip") == path
    assert second.calls == 1


def test_checksum_mismatch_is_an_error_not_a_silent_success(tmp_path: Path) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest()
    resolver = ArtifactResolver(
        layout, mirrors=[RecordingMirror("upstream", has_it=True, content=b"corrupted")]
    )

    with pytest.raises(ChecksumMismatch):
        resolver.resolve(manifest, "timeseries.zip")


def test_a_pre_existing_local_file_is_verified_once(tmp_path: Path) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest(md5="0" * 32)
    local = layout.raw(manifest) / "timeseries.zip"
    local.parent.mkdir(parents=True)
    local.write_bytes(CONTENT)

    with pytest.raises(ChecksumMismatch):
        ArtifactResolver(layout).resolve(manifest, "timeseries.zip")


def test_download_cap_refuses_large_artifacts_with_remediation(tmp_path: Path) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest(size=31_000_000_000)
    mirror = RecordingMirror("upstream", has_it=True)
    resolver = ArtifactResolver(layout, mirrors=[mirror], max_download_bytes=1_000_000_000)

    with pytest.raises(ArtifactUnavailable, match="download cap"):
        resolver.resolve(manifest, "timeseries.zip")
    assert mirror.calls == 0


def test_no_source_at_all_is_a_clear_error(tmp_path: Path) -> None:
    resolver = ArtifactResolver(DataDirectory(tmp_path))

    with pytest.raises(ArtifactUnavailable, match="place a copy at"):
        resolver.resolve(_manifest(), "timeseries.zip")
