"""Finding a dataset artifact: local copy, then configured mirrors, then the
upstream provider. Every path verifies the manifest's checksum, and a caller
can cap how much it is willing to download so a `tiny` snapshot can never
silently turn into a 30 GB image pull.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import httpx

from greenhouse_adapters.manifests import ArtifactManifest, DatasetManifest
from greenhouse_adapters.storage.layout import DataDirectory

_CHUNK_BYTES = 1024 * 1024
_VERIFIED_SUFFIX = ".md5-verified"


class ArtifactUnavailable(Exception):
    """No source could provide the artifact; the message says what to do."""


class ChecksumMismatch(Exception):
    pass


class ArtifactMirror(Protocol):
    """Somewhere an artifact can be fetched from, in precedence order. An S3
    mirror is a second implementation of this, not a change to the
    resolver."""

    name: str

    def fetch(self, artifact: ArtifactManifest, destination: Path) -> bool:
        """Writes the artifact to destination (resuming a partial file if
        one exists) and returns True, or returns False if this mirror does
        not have it."""
        ...


class UpstreamHttpMirror:
    """Fetches from the manifest's own download URL (the provider, e.g.
    4TU). Resumes an interrupted download with an HTTP Range request."""

    name = "upstream"

    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch(self, artifact: ArtifactManifest, destination: Path) -> bool:
        partial = destination.with_suffix(destination.suffix + ".part")
        already = partial.stat().st_size if partial.exists() else 0
        if already >= artifact.size_bytes:
            already = 0
            partial.unlink()
        headers = {"Range": f"bytes={already}-"} if already else {}
        with (
            httpx.stream(
                "GET",
                artifact.download_url,
                headers=headers,
                timeout=self._timeout_seconds,
                follow_redirects=True,
            ) as response,
            partial.open("ab" if already and response.status_code == 206 else "wb") as sink,
        ):
            response.raise_for_status()
            for chunk in response.iter_bytes(_CHUNK_BYTES):
                sink.write(chunk)
        partial.replace(destination)
        return True


class ArtifactResolver:
    def __init__(
        self,
        data_dir: DataDirectory,
        *,
        mirrors: Sequence[ArtifactMirror] = (),
        max_download_bytes: int | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._mirrors = list(mirrors)
        self._max_download_bytes = max_download_bytes

    def local_path(self, manifest: DatasetManifest, artifact: ArtifactManifest) -> Path:
        return self._data_dir.raw(manifest) / artifact.name

    def is_local(self, manifest: DatasetManifest, artifact: ArtifactManifest) -> bool:
        return self.local_path(manifest, artifact).exists()

    def resolve(self, manifest: DatasetManifest, artifact_name: str) -> Path:
        """The verified local path of the artifact, fetching it if needed."""
        artifact = manifest.artifact(artifact_name)
        destination = self.local_path(manifest, artifact)
        if destination.exists():
            self._verify(artifact, destination)
            return destination

        if self._max_download_bytes is not None and artifact.size_bytes > self._max_download_bytes:
            raise ArtifactUnavailable(
                f"{artifact.name} is {artifact.size_bytes:,} bytes, above this command's "
                f"download cap of {self._max_download_bytes:,} bytes; place it at "
                f"{destination} yourself or run a profile that allows large downloads"
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        for mirror in self._mirrors:
            if mirror.fetch(artifact, destination):
                self._verify(artifact, destination)
                return destination

        raise ArtifactUnavailable(
            f"no source could provide {artifact.name} (tried: "
            f"{', '.join(m.name for m in self._mirrors) or 'nothing - no mirrors configured'}); "
            f"place a copy at {destination}"
        )

    def _verify(self, artifact: ArtifactManifest, path: Path) -> None:
        marker = path.with_name(path.name + _VERIFIED_SUFFIX)
        if marker.exists() and marker.read_text().strip() == artifact.md5:
            return
        actual = _md5(path)
        if actual != artifact.md5:
            raise ChecksumMismatch(
                f"{path} has md5 {actual}, manifest says {artifact.md5}; delete it and re-fetch"
            )
        marker.write_text(artifact.md5 + "\n")


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        while chunk := source.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
