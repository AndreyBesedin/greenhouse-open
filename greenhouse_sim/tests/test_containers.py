"""A container is run from its pinned image as the host allows
(`greenhouse_sim.containers`), without Docker: the command, a measured
run's status, time and peak memory, and an image refused unless Docker Hub
still serves its digest."""

import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

from greenhouse_sim.containers import (
    ImageNotPublished,
    Mount,
    docker_run,
    run_measured,
    verify_published,
)

DIGEST = "sha256:" + "a" * 64
IMAGE = f"publisher/tool:1.0@{DIGEST}"


def test_on_linux_a_container_runs_as_the_user_who_runs_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Files keep their owners between the host and the container there.
    monkeypatch.setattr(sys, "platform", "linux")
    command = docker_run(
        IMAGE,
        ["tool", "--version"],
        mounts=[Mount(tmp_path / "data", "/data", read_only=True), Mount(tmp_path, "/work")],
        workdir="/work",
        environment={"HOME": "/tmp"},
        entrypoint="bash",
    )
    assert command == [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--env",
        "HOME=/tmp",
        "--volume",
        f"{(tmp_path / 'data').resolve()}:/data:ro",
        "--volume",
        f"{tmp_path.resolve()}:/work",
        "--workdir",
        "/work",
        "--entrypoint",
        "bash",
        IMAGE,
        "tool",
        "--version",
    ]


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_under_docker_desktop_a_container_runs_as_the_images_user(
    platform: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Its mounts carry no owners, and Windows has no user ids to give.
    monkeypatch.setattr(sys, "platform", platform)
    if platform == "win32":
        monkeypatch.delattr(os, "getuid")
        monkeypatch.delattr(os, "getgid")
    assert docker_run(IMAGE, ["tool"]) == ["docker", "run", "--rm", IMAGE, "tool"]


def test_a_measured_run_answers_its_status_time_and_peak_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = Mount(tmp_path, "/work")
    commands: list[list[str]] = []

    def container(peak: str | None, status: int) -> object:
        def run(command: list[str], check: bool) -> subprocess.CompletedProcess[bytes]:
            commands.append(command)
            if peak is not None:
                (tmp_path / "step.log").write_text("ran\n")
                (tmp_path / "step.peak").write_text(peak)
            return subprocess.CompletedProcess(command, status)

        return run

    monkeypatch.setattr(subprocess, "run", container("2147483648\n", 0))
    measured = run_measured(IMAGE, ["tool", "input"], workdir=work, name="step")
    assert (measured.status, measured.peak_bytes) == (0, 2**31)
    assert measured.seconds >= 0
    # The shell is the entrypoint, so that an image's own cannot take the
    # command; it runs the tool in the working folder, its output to the log.
    command = commands[-1]
    assert command[command.index("--entrypoint") + 1] == "sh"
    assert command[command.index("--workdir") + 1] == "/work"
    image_at = command.index(IMAGE)
    assert command[image_at + 1] == "-c"
    assert '"$@" > step.log 2>&1' in command[image_at + 2]
    assert command[image_at + 3 :] == ["sh", "tool", "input"]
    assert (tmp_path / "step.log").is_file()
    assert not (tmp_path / "step.peak").exists()

    # A container that does not start leaves no log, not the last run's,
    # and no peak memory: a control group without one gives none either.
    monkeypatch.setattr(subprocess, "run", container(None, 125))
    measured = run_measured(IMAGE, ["tool"], workdir=work, name="step")
    assert (measured.status, measured.peak_bytes) == (125, None)
    assert not (tmp_path / "step.log").exists()


class _Served(io.BytesIO):
    def __init__(self, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        super().__init__(body)
        self.headers = headers or {}


def test_an_image_is_refused_unless_docker_hub_still_serves_its_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []
    # What Docker Hub answers for a manifest: a status, and the digest.
    status, served = [200], [DIGEST]

    def urlopen(request: str | urllib.request.Request, timeout: float) -> _Served:
        url = request if isinstance(request, str) else request.full_url
        asked.append(url)
        if url.startswith("https://auth.docker.io/"):
            return _Served(json.dumps({"token": "anonymous"}).encode())
        assert isinstance(request, urllib.request.Request)
        assert request.get_method() == "HEAD"
        if status[0] != 200:
            raise urllib.error.HTTPError(url, status[0], "Gone", Message(), None)
        return _Served(headers={"Docker-Content-Digest": served[0]})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    verify_published(IMAGE)
    assert asked[-1] == f"https://registry-1.docker.io/v2/publisher/tool/manifests/{DIGEST}"

    # An official image is under `library/`.
    verify_published(f"ubuntu:24.04@{DIGEST}")
    assert asked[-1] == f"https://registry-1.docker.io/v2/library/ubuntu/manifests/{DIGEST}"

    status[0] = 404
    with pytest.raises(ImageNotPublished, match=r"no longer serves .* \(404\)"):
        verify_published(IMAGE)

    status[0], served[0] = 200, "sha256:" + "b" * 64
    with pytest.raises(ImageNotPublished, match=r"serves sha256:b+ for"):
        verify_published(IMAGE)

    with pytest.raises(ValueError, match="not pinned by its digest"):
        verify_published("publisher/tool:1.0")
    with pytest.raises(ValueError, match="not on Docker Hub"):
        verify_published(f"ghcr.io/publisher/tool:1.0@{DIGEST}")
