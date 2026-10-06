"""The simulator's own state, for a client checking what it is talking to."""

from importlib.metadata import version as installed_version

from pydantic import BaseModel

from greenhouse_sim.scene.snapshot import SCHEMA_VERSION


class Health(BaseModel):
    status: str


class Version(BaseModel):
    simulator: str
    version: str
    scene_schema_version: int


def health() -> Health:
    """The simulator is up and answering."""
    return Health(status="ok")


def version() -> Version:
    """The simulator's name and version, and the scene schema it writes."""
    return Version(
        simulator="greenhouse-sim",
        version=installed_version("greenhouse-sim"),
        scene_schema_version=SCHEMA_VERSION,
    )
