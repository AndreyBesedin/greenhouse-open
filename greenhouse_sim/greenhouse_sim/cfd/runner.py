"""Running OpenFOAM out of process: natively if it is installed, or in its
container if Docker is (`greenhouse_sim.containers`).

Nothing in the simulator needs OpenFOAM. What does use it asks whether it is
`available()` first, and a test that needs it is skipped without it.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Final

from greenhouse_sim.containers import Mount, docker_run, docker_running

# The container image OpenFOAM is run from when it is not installed, unless
# GREENHOUSE_OPENFOAM_IMAGE names another: by digest, as well as by tag, so
# that a tag moved upstream cannot change what the kept results are
# compared with.
DEFAULT_IMAGE: Final = (
    "opencfd/openfoam-default:2412"
    "@sha256:1ba02114b1c025c370f2e269a07677c16c9bea8d990fcd75ac8378aff9d41b50"
)
IMAGE_VARIABLE: Final = "GREENHOUSE_OPENFOAM_IMAGE"
# Where the case is mounted inside the container.
CASE_MOUNT: Final = "/case"
# OpenFOAM's environment in its container, set up for whichever user runs
# it, before the case's script.
CONTAINER_ENVIRONMENT: Final = (
    "f=/usr/lib/openfoam/openfoam2412/etc/bashrc; if [ -f $f ]; then . $f; fi; "
)
# Where OpenFOAM writes as the host's user, who has no home in the image.
CONTAINER_HOME: Final = "/tmp"
# How long a command may run, in seconds.
TIMEOUT_S: Final = 600


class OpenFoamUnavailable(RuntimeError):
    """OpenFOAM is neither installed nor reachable in a container."""


def _native() -> bool:
    return shutil.which("blockMesh") is not None


def available() -> bool:
    """Whether OpenFOAM can be run here."""
    return _native() or docker_running()


def run(case: Path, script: str) -> subprocess.CompletedProcess[str]:
    """Run a case's shell script (such as `./Allmesh`) in the case's
    directory, with OpenFOAM's environment, natively or in its container."""
    if _native():
        command = ["sh", "-c", script]
        cwd: Path | None = case
    elif docker_running():
        command = docker_run(
            os.environ.get(IMAGE_VARIABLE, DEFAULT_IMAGE),
            ["-lc", CONTAINER_ENVIRONMENT + script],
            mounts=[Mount(case, CASE_MOUNT)],
            workdir=CASE_MOUNT,
            environment={"HOME": CONTAINER_HOME},
            entrypoint="bash",
        )
        cwd = None
    else:
        raise OpenFoamUnavailable("OpenFOAM is not installed, and Docker is not running")
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S, check=False
    )
