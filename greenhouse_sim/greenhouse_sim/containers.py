"""Running an outside tool in its container, from an image pinned by its
digest, so that what the tool is cannot move under a result: OpenFOAM for
the airflow (`cfd.runner`), and OpenModelica for the research's Modelica
comparison (`research/modelica`).

Docker runs the containers. This needs Python's standard library alone, so
a check that only asks where an image is published can import it without
the workspace installed.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

# How long Docker may take to say whether it is running, and a registry to
# answer, in seconds.
PROBE_TIMEOUT_S: Final = 30
REGISTRY_TIMEOUT_S: Final = 60

# Docker Hub, and the manifest types a pinned digest may name: an image
# index, OCI's or Docker's, or a single image.
DOCKER_HUB_TOKEN: Final = "https://auth.docker.io/token"
DOCKER_HUB: Final = "https://registry-1.docker.io/v2"
MANIFEST_TYPES: Final = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)

# Where a container's peak memory is read: its control group's, under
# cgroup v2, the page cache included.
MEMORY_PEAK: Final = "/sys/fs/cgroup/memory.peak"


class ImageNotPublished(RuntimeError):
    """The registry no longer serves an image as it is pinned."""


@dataclass(frozen=True)
class Mount:
    """A host folder, and where the container sees it."""

    source: Path
    target: str
    read_only: bool = False


@dataclass(frozen=True)
class Measured:
    """What a run in a container took: its exit status, its time, and the
    container's peak memory, where its control group gives it."""

    status: int
    seconds: float
    peak_bytes: int | None


def docker_running() -> bool:
    """Whether Docker is installed and its daemon answers."""
    if shutil.which("docker") is None:
        return False
    try:
        info = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return False
    return info.returncode == 0


def docker_run(
    image: str,
    argv: Sequence[str],
    *,
    mounts: Sequence[Mount] = (),
    workdir: str | None = None,
    environment: Mapping[str, str] | None = None,
    entrypoint: str | None = None,
) -> list[str]:
    """The `docker run` that runs `argv` in `image`, and removes the
    container after.

    On Linux, files keep their owners between the host and the container,
    so the container runs as the user who runs it, to write beside them.
    That user has no home in the image: a tool that needs one is given
    `HOME` in `environment`. Docker Desktop's mounts, on macOS and Windows,
    carry no owners, and Windows has no user ids, so there the container
    runs as the image's own user."""
    command = ["docker", "run", "--rm", *_host_user()]
    for name, value in (environment or {}).items():
        command += ["--env", f"{name}={value}"]
    for mount in mounts:
        mode = ":ro" if mount.read_only else ""
        command += ["--volume", f"{mount.source.resolve()}:{mount.target}{mode}"]
    if workdir is not None:
        command += ["--workdir", workdir]
    if entrypoint is not None:
        command += ["--entrypoint", entrypoint]
    return [*command, image, *argv]


def run_measured(
    image: str,
    argv: Sequence[str],
    *,
    workdir: Mount,
    name: str,
    mounts: Sequence[Mount] = (),
    environment: Mapping[str, str] | None = None,
) -> Measured:
    """Runs `argv` in `image`, in `workdir`, its output in `<name>.log`
    there, and answers what it took. A log an earlier run left is removed
    first, so that a container that does not start leaves none. The image
    needs a shell, which reads the peak before the container goes."""
    log = workdir.source / f"{name}.log"
    peak = workdir.source / f"{name}.peak"
    log.unlink(missing_ok=True)
    peak.unlink(missing_ok=True)
    wrapped = (
        f'"$@" > {log.name} 2>&1; status=$?; '
        f"cat {MEMORY_PEAK} > {peak.name} 2>/dev/null; exit $status"
    )
    command = docker_run(
        image,
        ["-c", wrapped, "sh", *argv],
        mounts=[*mounts, workdir],
        workdir=workdir.target,
        environment=environment,
        entrypoint="sh",
    )
    started = time.monotonic()
    ran = subprocess.run(command, check=False)
    seconds = time.monotonic() - started
    text = peak.read_text(encoding="utf-8").strip() if peak.is_file() else ""
    peak.unlink(missing_ok=True)
    return Measured(ran.returncode, seconds, int(text) if text.isdigit() else None)


def verify_published(image: str) -> None:
    """Refuses `image`, a Docker Hub image pinned by its digest, unless
    Docker Hub still serves that digest. Asking for a manifest is not a
    pull: no image is downloaded."""
    repository, digest = _on_docker_hub(image)
    token = _json(
        f"{DOCKER_HUB_TOKEN}?service=registry.docker.io&scope=repository:{repository}:pull"
    )["token"]
    request = urllib.request.Request(
        f"{DOCKER_HUB}/{repository}/manifests/{digest}",
        method="HEAD",
        headers={"Authorization": f"Bearer {token}", "Accept": ", ".join(MANIFEST_TYPES)},
    )
    try:
        with urllib.request.urlopen(request, timeout=REGISTRY_TIMEOUT_S) as response:
            served = response.headers.get("Docker-Content-Digest")
    except urllib.error.HTTPError as error:
        raise ImageNotPublished(f"Docker Hub no longer serves {image} ({error.code})") from error
    if served != digest:
        raise ImageNotPublished(f"Docker Hub serves {served} for {image}")


def _host_user() -> list[str]:
    if sys.platform != "linux":
        return []
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def _on_docker_hub(image: str) -> tuple[str, str]:
    """`image`'s repository on Docker Hub, an official image's under
    `library/`, and its digest."""
    named, _, digest = image.partition("@")
    if not digest:
        raise ValueError(f"{image} is not pinned by its digest")
    host, slash, _ = named.partition("/")
    if slash and ("." in host or ":" in host or host == "localhost"):
        raise ValueError(f"{image} is not on Docker Hub")
    repository = named.rpartition(":")[0] if ":" in named.rpartition("/")[2] else named
    return (repository if "/" in repository else f"library/{repository}"), digest


def _json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=REGISTRY_TIMEOUT_S) as response:
        return json.loads(response.read())
