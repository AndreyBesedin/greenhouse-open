"""A scenario's air as a CFD solver is given it, and as it solves it.

The domain is the box a scenario's fields cover, on the same grid
(`fields.air_grid`), so a solver's result maps onto a field cell for cell.
It is worked out from the scenario as a client changes it, as its scene is
(`scenarios.SceneChanges`): with another of its layouts, another size of
greenhouse, or its doors and vents opened, so that what a viewer draws of
it matches the scene beside it.

Solving needs OpenFOAM (`greenhouse_sim.cfd.runner`). A solve of a scenario
as it is configured, with any of its layouts, is kept
(`greenhouse_sim.cfd.results`), and offered as one of its fields with that
layout for as long as it is still that scenario's solution; a solve of a
scenario with its greenhouse or its openings changed is only returned.
"""

from dataclasses import dataclass
from pathlib import Path

from greenhouse_sim.cfd.geometry import CfdGeometry, cfd_geometry
from greenhouse_sim.cfd.openfoam import SetupRefused, write_mesh_case
from greenhouse_sim.cfd.results import CfdResult, keep
from greenhouse_sim.cfd.solve import solve as solve_case
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.grid import air_grid
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


@dataclass(frozen=True)
class Solved:
    """A solve's result, and where it was kept, if it was."""

    result: CfdResult
    kept: Path | None


def solve(scenario_id: str, directory: Path, changes: SceneChanges | None = None) -> Solved:
    """Solve a scenario's air with OpenFOAM in `directory`, as its
    configuration's setup drives it, and keep the result if only its layout
    was changed, if anything. A scenario its setup cannot drive is
    refused."""
    changes = changes or SceneChanges()
    as_configured = not changes.envelope and not changes.openings
    config = changed(scenario(scenario_id), changes)
    try:
        result = solve_case(geometry(scenario_id, changes), config.cfd, directory, changes.layout)
    except SetupRefused as refusal:
        raise InvalidRequest(str(refusal)) from None
    return Solved(result=result, kept=keep(result) if as_configured else None)
