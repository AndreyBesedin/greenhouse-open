"""The simulator's own state, for a client checking what it is talking to."""

import subprocess
from functools import cache
from importlib.metadata import version as installed_version
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from greenhouse_sim.scene.snapshot import SCHEMA_VERSION

# What names the commit the simulator runs from when it is not run from a
# git checkout, as the viewer names its own (`vite.config.ts`).
UNKNOWN_COMMIT: Final = "unknown"
# How long git may take to name it, in seconds.
GIT_TIMEOUT_S: Final = 5.0


class Health(BaseModel):
    status: str


class Version(BaseModel):
    simulator: str
    version: str
    # The commit the simulator runs from, abbreviated as git abbreviates it,
    # or "unknown" outside a git checkout.
    commit: str
    scene_schema_version: int


def health() -> Health:
    """The simulator is up and answering."""
    return Health(status="ok")


def version() -> Version:
    """The simulator's name, version and commit, and the scene schema it
    writes."""
    return Version(
        simulator="greenhouse-sim",
        version=installed_version("greenhouse-sim"),
        commit=source_commit(),
        scene_schema_version=SCHEMA_VERSION,
    )


@cache
def source_commit() -> str:
    """The commit the simulator's source was checked out at, as the viewer
    names the one it was built from: git's abbreviation of it, or
    `UNKNOWN_COMMIT` outside a git checkout. Asked once, as the process
    first needs it."""
    try:
        answer = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=True,
        )
    except OSError, subprocess.SubprocessError:
        return UNKNOWN_COMMIT
    return answer.stdout.strip() or UNKNOWN_COMMIT
