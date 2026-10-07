"""A scenario's air as a CFD solver is given it: the computational domain and
its boundaries, and the OpenFOAM case that meshes them.

The domain is the box a scenario's fields cover, on the same grid
(`fields.air_grid`), so a solver's result maps onto a field cell for cell.
It is worked out from the scenario as a client changes it, as its scene is
(`scenarios.SceneChanges`): with another of its layouts, another size of
greenhouse, or its doors and vents opened, so that what a viewer draws of
it matches the scene beside it.
"""

from pathlib import Path

from greenhouse_sim.cfd.geometry import CfdGeometry, cfd_geometry
from greenhouse_sim.cfd.openfoam import write_mesh_case
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.services.scenarios import SceneChanges, changed, scenario


def geometry(scenario_id: str, changes: SceneChanges | None = None) -> CfdGeometry:
    """The CFD geometry of a scenario, changed as a client asks."""
    config = changed(scenario(scenario_id), changes or SceneChanges())
    return cfd_geometry(scenario_id, config, air_grid(config))


def write_case(
    scenario_id: str, directory: Path, changes: SceneChanges | None = None
) -> list[Path]:
    """Write the OpenFOAM case that meshes a scenario's CFD geometry into
    `directory`, and return the files written. Its `Allmesh` script meshes
    it, wherever OpenFOAM is."""
    return write_mesh_case(geometry(scenario_id, changes), directory)
