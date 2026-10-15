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
import time
from collections.abc import Callable, Sequence
from http import HTTPStatus
from pathlib import Path
from typing import Protocol

import httpx

from greenhouse_adapters.manifests import ArtifactManifest, DatasetManifest
from greenhouse_adapters.storage.layout import DataDirectory

_CHUNK_BYTES = 1024 * 1024
_VERIFIED_SUFFIX = ".md5-verified"
_PARTIAL_SUFFIX = ".part"
_REJECTED_SUFFIX = ".rejected"
# Answers worth asking again for: the provider is busy or failing for now.
_RETRIED = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)
_ATTEMPTS = 4
_FIRST_WAIT_S = 2.0


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


class _Interrupted(Exception):
    """A download that stopped short for a reason that may pass."""


class UpstreamHttpMirror:
    """Fetches from the manifest's own download URL (the provider, e.g.
    4TU). Resumes an interrupted download with an HTTP Range request, and
    asks again, a few times and less often each time, when the provider is
    busy, fails, or the connection drops; what was fetched is kept for the
    next run to resume from."""

    name = "upstream"

    def __init__(
        self,
        *,
        timeout_seconds: float = 60.0,
        attempts: int = _ATTEMPTS,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._attempts = attempts
        self._transport = transport
        self._sleep = sleep

    def fetch(self, artifact: ArtifactManifest, destination: Path) -> bool:
        partial = destination.with_name(destination.name + _PARTIAL_SUFFIX)
        for attempt in range(1, self._attempts + 1):
            try:
                self._download(artifact, partial)
            except _Interrupted as error:
                if attempt == self._attempts:
                    kept = partial.stat().st_size if partial.exists() else 0
                    raise ArtifactUnavailable(
                        f"{artifact.name}: {error} ({attempt} attempts); the {kept:,} bytes "
                        f"fetched are kept in {partial}, and the next run resumes from them"
                    ) from error
                self._sleep(_FIRST_WAIT_S * 2 ** (attempt - 1))
                continue
            partial.replace(destination)
            return True
        return False

    def _download(self, artifact: ArtifactManifest, partial: Path) -> None:
        """Brings `partial` to the artifact's size, from where it stands, or
        raises `_Interrupted` with what it has kept."""
        already = partial.stat().st_size if partial.exists() else 0
        if already >= artifact.size_bytes:
            already = 0
            partial.unlink()
        headers = {"Range": f"bytes={already}-"} if already else {}
        try:
            with (
                httpx.Client(
                    transport=self._transport,
                    timeout=self._timeout_seconds,
                    follow_redirects=True,
                ) as client,
                client.stream("GET", artifact.download_url, headers=headers) as response,
            ):
                if response.status_code in _RETRIED:
                    raise _Interrupted(f"the provider answered {response.status_code}")
                if response.is_error:
                    raise ArtifactUnavailable(
                        f"{artifact.name}: the provider answered {response.status_code} "
                        f"for {artifact.download_url}"
                    )
                # A provider that ignores the range sends the whole file again.
                resuming = already and response.status_code == HTTPStatus.PARTIAL_CONTENT
                with partial.open("ab" if resuming else "wb") as sink:
                    for chunk in response.iter_bytes(_CHUNK_BYTES):
                        sink.write(chunk)
        except httpx.TransportError as error:
            raise _Interrupted(f"the connection failed: {error}") from error
        size = partial.stat().st_size
        if size < artifact.size_bytes:
            raise _Interrupted(f"the download stopped at {size:,} of {artifact.size_bytes:,} bytes")
        if size > artifact.size_bytes:
            partial.unlink()
            raise ChecksumMismatch(
                f"{artifact.download_url} sent {size:,} bytes, the manifest says "
                f"{artifact.size_bytes:,}; nothing was kept"
            )


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
