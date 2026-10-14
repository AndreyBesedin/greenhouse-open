"""Finding a dataset artifact: local copy, then configured mirrors, then the
upstream provider. Every path verifies the manifest's checksum, and a caller
can cap how much it is willing to download so a `tiny` snapshot can never
silently turn into a 30 GB image pull.

A verified file is not hashed again while it stays the file that was
verified: a record beside it names the checksum with the file's size,
inode and modification time, and a file that differs in any of them is
hashed again. A fetch drops the record first, and a fetched file that
fails its checksum is moved aside, so the next run fetches it again.
"""

import hashlib
from collections.abc import Sequence
from http import HTTPStatus
from pathlib import Path
from typing import Protocol

import httpx

from greenhouse_adapters.manifests import ArtifactManifest, DatasetManifest
from greenhouse_adapters.storage.layout import DataDirectory

_CHUNK_BYTES = 1024 * 1024
_VERIFIED_SUFFIX = ".md5-verified"
_REJECTED_SUFFIX = ".rejected"


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
            partial.open(
                "ab" if already and response.status_code == HTTPStatus.PARTIAL_CONTENT else "wb"
            ) as sink,
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
        # A record left by a file deleted since describes nothing fetched now.
        _verified(destination).unlink(missing_ok=True)
        for mirror in self._mirrors:
            if mirror.fetch(artifact, destination):
                try:
                    self._verify(artifact, destination)
                except ChecksumMismatch as error:
                    rejected = destination.with_name(destination.name + _REJECTED_SUFFIX)
                    destination.replace(rejected)
                    raise ChecksumMismatch(
                        f"{error}: {mirror.name} sent it; it is moved aside to {rejected}, "
                        "and the next run fetches it again"
                    ) from error
                return destination

        raise ArtifactUnavailable(
            f"no source could provide {artifact.name} (tried: "
            f"{', '.join(m.name for m in self._mirrors) or 'nothing - no mirrors configured'}); "
            f"place a copy at {destination}"
        )

    def _verify(self, artifact: ArtifactManifest, path: Path) -> None:
        marker = _verified(path)
        stamp = _stamp(artifact.md5, path)
        if marker.exists() and marker.read_text(encoding="utf-8").strip() == stamp:
            return
        actual = _md5(path)
        if actual != artifact.md5:
            raise ChecksumMismatch(
                f"{path} has md5 {actual}, manifest says {artifact.md5}; delete it and re-fetch"
            )
        marker.write_text(stamp + "\n", encoding="utf-8")


def _verified(path: Path) -> Path:
    """Where the record of `path`'s verification is kept."""
    return path.with_name(path.name + _VERIFIED_SUFFIX)


def _stamp(md5: str, path: Path) -> str:
    """The checksum a verification found, with what says the file is still
    the one it was found in: its size, inode and modification time."""
    status = path.stat()
    return f"{md5} {status.st_size} {status.st_ino} {status.st_mtime_ns}"


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        while chunk := source.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
