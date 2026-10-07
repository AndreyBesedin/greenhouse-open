"""Running OpenFOAM out of process: natively if it is installed, or in its
container if Docker is.

Nothing in the simulator needs OpenFOAM. What does use it asks whether it is
`available()` first, and a test that needs it is skipped without it.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Final

# The container image OpenFOAM is run from when it is not installed, unless
# GREENHOUSE_OPENFOAM_IMAGE names another.
DEFAULT_IMAGE: Final = "opencfd/openfoam-default:2412"
IMAGE_VARIABLE: Final = "GREENHOUSE_OPENFOAM_IMAGE"
# Where the case is mounted inside the container.
CASE_MOUNT: Final = "/case"
# How long a command may run, and how long Docker may take to say whether it
# is running, in seconds.
TIMEOUT_S: Final = 600
PROBE_TIMEOUT_S: Final = 30


class OpenFoamUnavailable(RuntimeError):
    """OpenFOAM is neither installed nor reachable in a container."""


def _native() -> bool:
    return shutil.which("blockMesh") is not None


def _docker() -> bool:
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


def available() -> bool:
    """Whether OpenFOAM can be run here."""
    return _native() or _docker()


def run(case: Path, script: str) -> subprocess.CompletedProcess[str]:
    """Run a case's shell script (such as `./Allmesh`) in the case's
    directory, with OpenFOAM's environment, natively or in its container."""
    if _native():
        command = ["sh", "-c", script]
        cwd: Path | None = case
    elif _docker():
        image = os.environ.get(IMAGE_VARIABLE, DEFAULT_IMAGE)
        command = [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{case.resolve()}:{CASE_MOUNT}",
            "--workdir",
            CASE_MOUNT,
            "--entrypoint",
            "bash",
            image,
            "-lc",
            script,
        ]
        cwd = None
    else:
        raise OpenFoamUnavailable("OpenFOAM is not installed, and Docker is not running")
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S, check=False
    )
