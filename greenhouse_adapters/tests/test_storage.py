import hashlib
import os
from collections.abc import Callable
from pathlib import Path

import httpx
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
    UpstreamHttpMirror,
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


def _replace_bytes(path: Path, content: bytes) -> None:
    """Writes `content` over `path` as a later write would, its modification
    time moved on even where the clock is coarser than two quick writes."""
    before = path.stat().st_mtime_ns
    path.write_bytes(content)
    os.utime(path, ns=(before, before + 1_000_000_000))


def test_a_verified_file_replaced_afterwards_is_verified_again(tmp_path: Path) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest()
    resolver = ArtifactResolver(layout, mirrors=[RecordingMirror("upstream", has_it=True)])
    path = resolver.resolve(manifest, "timeseries.zip")

    _replace_bytes(path, bytes(len(CONTENT)))

    with pytest.raises(ChecksumMismatch):
        resolver.resolve(manifest, "timeseries.zip")


def test_a_file_fetched_again_is_verified_again_and_a_bad_one_moved_aside(
    tmp_path: Path,
) -> None:
    layout = DataDirectory(tmp_path)
    manifest = _manifest()
    mirror = RecordingMirror("upstream", has_it=True)
    resolver = ArtifactResolver(layout, mirrors=[mirror])
    path = resolver.resolve(manifest, "timeseries.zip")
    path.unlink()  # the record of its verification stays behind
    mirror.content = bytes(len(CONTENT))

    with pytest.raises(ChecksumMismatch, match="moved aside"):
        resolver.resolve(manifest, "timeseries.zip")
    assert not path.exists()
    assert path.with_name("timeseries.zip.rejected").read_bytes() == mirror.content

    mirror.content = CONTENT
    assert resolver.resolve(manifest, "timeseries.zip").read_bytes() == CONTENT
    assert mirror.calls == 3


# The upstream mirror, against a provider played by httpx's mock transport.
PAYLOAD = bytes(range(256)) * 40
HALF = len(PAYLOAD) // 2


def _payload_manifest() -> DatasetManifest:
    return _manifest(size=len(PAYLOAD), md5=hashlib.md5(PAYLOAD).hexdigest())


def _ranged(request: httpx.Request) -> httpx.Response:
    """A provider that honours a Range request."""
    asked = request.headers.get("Range")
    if asked is None:
        return httpx.Response(200, content=PAYLOAD)
    start = int(asked.removeprefix("bytes=").removesuffix("-"))
    return httpx.Response(206, content=PAYLOAD[start:])


class Provider:
    """Answers each request with the next of `answers`, and keeps them."""

    def __init__(self, *answers: Callable[[httpx.Request], httpx.Response]) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers[min(len(self.requests), len(self.answers)) - 1]
        return answer(request)


def _upstream(provider: Provider, waits: list[float] | None = None) -> UpstreamHttpMirror:
    return UpstreamHttpMirror(
        transport=httpx.MockTransport(provider),
        sleep=(waits if waits is not None else []).append,
    )


def _with_partial(tmp_path: Path, content: bytes) -> tuple[DataDirectory, Path]:
    layout = DataDirectory(tmp_path)
    destination = layout.raw(_payload_manifest()) / "timeseries.zip"
    destination.parent.mkdir(parents=True)
    destination.with_name("timeseries.zip.part").write_bytes(content)
    return layout, destination


def test_a_download_is_fetched_verified_and_kept(tmp_path: Path) -> None:
    provider = Provider(_ranged)
    resolver = ArtifactResolver(DataDirectory(tmp_path), mirrors=[_upstream(provider)])

    path = resolver.resolve(_payload_manifest(), "timeseries.zip")

    assert path.read_bytes() == PAYLOAD
    assert not path.with_name("timeseries.zip.part").exists()


def test_an_interrupted_download_resumes_from_its_partial_file(tmp_path: Path) -> None:
    layout, _ = _with_partial(tmp_path, PAYLOAD[:HALF])
    provider = Provider(_ranged)

    path = ArtifactResolver(layout, mirrors=[_upstream(provider)]).resolve(
        _payload_manifest(), "timeseries.zip"
    )

    assert path.read_bytes() == PAYLOAD
    assert provider.requests[0].headers["Range"] == f"bytes={HALF}-"


def test_a_provider_that_ignores_the_range_starts_the_file_again(tmp_path: Path) -> None:
    layout, _ = _with_partial(tmp_path, PAYLOAD[:HALF])
    provider = Provider(lambda request: httpx.Response(200, content=PAYLOAD))

    path = ArtifactResolver(layout, mirrors=[_upstream(provider)]).resolve(
        _payload_manifest(), "timeseries.zip"
    )

    assert path.read_bytes() == PAYLOAD


def test_a_busy_provider_keeps_the_bytes_already_fetched(tmp_path: Path) -> None:
    layout, destination = _with_partial(tmp_path, PAYLOAD[:HALF])
    provider = Provider(lambda request: httpx.Response(503))
    waits: list[float] = []

    with pytest.raises(ArtifactUnavailable, match="503") as raised:
        ArtifactResolver(layout, mirrors=[_upstream(provider, waits)]).resolve(
            _payload_manifest(), "timeseries.zip"
        )

    assert destination.with_name("timeseries.zip.part").read_bytes() == PAYLOAD[:HALF]
    assert not destination.exists()
    assert "resumes" in str(raised.value)
    assert len(provider.requests) == 4
    assert waits == [2.0, 4.0, 8.0]


def test_a_short_answer_is_resumed_not_kept(tmp_path: Path) -> None:
    provider = Provider(lambda request: httpx.Response(200, content=PAYLOAD[:HALF]), _ranged)
    waits: list[float] = []

    path = ArtifactResolver(DataDirectory(tmp_path), mirrors=[_upstream(provider, waits)]).resolve(
        _payload_manifest(), "timeseries.zip"
    )

    assert path.read_bytes() == PAYLOAD
    assert provider.requests[1].headers["Range"] == f"bytes={HALF}-"
    assert waits == [2.0]


def test_a_download_that_stays_short_is_not_moved_into_place(tmp_path: Path) -> None:
    provider = Provider(lambda request: httpx.Response(200, content=PAYLOAD[:HALF]))
    layout = DataDirectory(tmp_path)

    with pytest.raises(ArtifactUnavailable, match="stopped at"):
        ArtifactResolver(layout, mirrors=[_upstream(provider)]).resolve(
            _payload_manifest(), "timeseries.zip"
        )

    assert not (layout.raw(_payload_manifest()) / "timeseries.zip").exists()


def test_a_longer_answer_is_refused_and_dropped(tmp_path: Path) -> None:
    provider = Provider(lambda request: httpx.Response(200, content=PAYLOAD + b"!"))
    layout = DataDirectory(tmp_path)

    with pytest.raises(ChecksumMismatch, match="nothing was kept"):
        ArtifactResolver(layout, mirrors=[_upstream(provider)]).resolve(
            _payload_manifest(), "timeseries.zip"
        )

    assert list((layout.raw(_payload_manifest())).iterdir()) == []


def test_a_dropped_connection_is_tried_again(tmp_path: Path) -> None:
    def dropped(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection reset", request=request)

    provider = Provider(dropped, _ranged)

    path = ArtifactResolver(DataDirectory(tmp_path), mirrors=[_upstream(provider)]).resolve(
        _payload_manifest(), "timeseries.zip"
    )

    assert path.read_bytes() == PAYLOAD
    assert len(provider.requests) == 2


def test_a_missing_artifact_is_not_asked_for_again(tmp_path: Path) -> None:
    provider = Provider(lambda request: httpx.Response(404))

    with pytest.raises(ArtifactUnavailable, match="404"):
        ArtifactResolver(DataDirectory(tmp_path), mirrors=[_upstream(provider)]).resolve(
            _payload_manifest(), "timeseries.zip"
        )

    assert len(provider.requests) == 1
