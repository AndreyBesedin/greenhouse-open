"""OpenFOAM's container is run as it was before the shared module ran it
(`greenhouse_sim.containers`): its case mounted where its scripts run,
through bash with OpenFOAM's environment, as the case's owner on Linux.
The CFD workflow runs OpenFOAM natively, so it never builds this command."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from greenhouse_sim.cfd import runner


def test_a_case_runs_in_openfoams_container_when_openfoam_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(runner.IMAGE_VARIABLE, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(runner, "_native", lambda: False)
    monkeypatch.setattr(runner, "docker_running", lambda: True)
    ran: list[list[str]] = []

    def run(command: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        assert options["cwd"] is None
        ran.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    runner.run(tmp_path, "./Allmesh")
    assert ran == [
        [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--env",
            "HOME=/tmp",
            "--volume",
            f"{tmp_path.resolve()}:/case",
            "--workdir",
            "/case",
            "--entrypoint",
            "bash",
            runner.DEFAULT_IMAGE,
            "-lc",
            runner.CONTAINER_ENVIRONMENT + "./Allmesh",
        ]
    ]
