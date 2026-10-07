"""A CFD geometry, and how its air is driven, written as an OpenFOAM case.

A case is a set of text files (`mesh_case_files`, `solve_case_files`),
written into a directory (`write_case`) and run there by its scripts. It is
meshed by its `Allmesh` script, in up to five steps:

1. `blockMesh` fills the domain's box with the grid's cells, its six faces
   each a wall patch;
2. `topoSet` gathers each opening's faces (`system/topoSetDict`);
3. `createPatch` moves each opening's faces out of its wall into a patch of
   its own, named for the opening;
4. `topoSet` gathers the cells the obstacles remove
   (`system/topoSetDict.obstacles`), once the patches are made, since
   making them clears the sets;
5. `subsetMesh` removes those cells, and their exposed faces become the
   `obstacles` patch, which `foamDictionary` then makes a wall, in the
   walls' group (subsetMesh makes a new patch of type `empty`, and
   `createPatch` drops a patch declared beforehand while it has no faces).

Every opening's and obstacle's selection is a box snapped to the grid
(`geometry`), padded by a fraction of a cell so that faces and cells on its
edges are chosen as `geometry` chose them, and no others.

A case to solve (`solve_case_files`) adds the air's starting fields and
properties, as its setup (`setup.CfdSetup`) drives it, and an `Allrun`
script: it meshes the case, solves it with `simpleFoam`, steady and laminar,
and writes the cells' centres beside the solution, for `solve` to read.

- **Inlets:** air comes in square to the opening at the setup's speed
  (`surfaceNormalFixedValue`), at whatever pressure that takes.
- **Outlets:** every other open opening, at the outside's pressure, 0; air
  leaves through it freely and may come back in, still.
- **Walls**, the floor, the ceiling and the obstacles: the air does not slip.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from greenhouse_sim.cfd import runner
from greenhouse_sim.cfd.geometry import BoundaryCategory, Box, CfdGeometry, Face
from greenhouse_sim.cfd.setup import CfdSetup
from greenhouse_sim.fields.field import FieldGrid

# The patch an obstacle's exposed faces join.
OBSTACLES_PATCH: Final = "obstacles"
# The cells that stay, when obstacles remove some.
FLUID_SET: Final = "fluid"
# A selection box reaches this share of a cell past a snapped edge, so that
# the faces and cells meant are chosen, and only they.
PAD_SHARE_OF_CELL: Final = 0.25
# The OpenFOAM version the case is written for.
OPENFOAM_VERSION: Final = "v2412"
MESH_SCRIPT: Final = "Allmesh"
SOLVE_SCRIPT: Final = "Allrun"
# Where the air's starting fields are kept, to be copied to time 0 once the
# case is meshed: meshing would otherwise change them with the mesh.
INITIAL_FIELDS: Final = "0.orig"
# Read and run by anyone, written by its owner.
SCRIPT_MODE: Final = 0o755
# How much of a failed step's log is reported, in characters.
LOG_TAIL: Final = 2000

# Each face of the box, as blockMesh's vertices make it, its normal outward.
_FACE_VERTICES: Final = {
    Face.FLOOR: (0, 3, 2, 1),
    Face.CEILING: (4, 5, 6, 7),
    Face.FRONT: (0, 4, 7, 3),
    Face.BACK: (1, 2, 6, 5),
    Face.RIGHT: (0, 1, 5, 4),
    Face.LEFT: (3, 7, 6, 2),
}


def _header(name: str, location: str = "system", kind: str = "dictionary") -> str:
    return (
        f"// Written by greenhouse_sim.cfd for OpenFOAM {OPENFOAM_VERSION}.\n"
        "FoamFile\n{\n"
        "    version     2.0;\n"
        "    format      ascii;\n"
        f"    class       {kind};\n"
        f'    location    "{location}";\n'
        f"    object      {name};\n"
        "}\n\n"
    )


def _number(value: float) -> str:
    return f"{value:.9g}"


def _vector(x: float, y: float, z: float) -> str:
    return f"({_number(x)} {_number(y)} {_number(z)})"


def _padded(box: Box, grid: FieldGrid) -> tuple[str, str]:
    """A selection box's corners, padded by a fraction of a cell."""
    pad = {axis: PAD_SHARE_OF_CELL * getattr(grid.cell_size, axis) for axis in "xyz"}
    low = _vector(*(getattr(box.minimum, a) - pad[a] for a in "xyz"))
    high = _vector(*(getattr(box.maximum, a) + pad[a] for a in "xyz"))
    return low, high


def _shrunk(box: Box, grid: FieldGrid) -> tuple[str, str]:
    """An obstacle's box, shrunk by a fraction of a cell, so that it holds the
    centres of the cells it removes and no others."""
    pad = {axis: PAD_SHARE_OF_CELL * getattr(grid.cell_size, axis) for axis in "xyz"}
    low = _vector(*(getattr(box.minimum, a) + pad[a] for a in "xyz"))
    high = _vector(*(getattr(box.maximum, a) - pad[a] for a in "xyz"))
    return low, high


def block_mesh_dict(geometry: CfdGeometry) -> str:
    grid = geometry.grid
    low, high = grid.origin, grid.maximum
    corners = [
        (low.x, low.y, low.z),
        (high.x, low.y, low.z),
        (high.x, high.y, low.z),
        (low.x, high.y, low.z),
        (low.x, low.y, high.z),
        (high.x, low.y, high.z),
        (high.x, high.y, high.z),
        (low.x, high.y, high.z),
    ]
    vertices = "\n".join(f"    {_vector(*corner)}" for corner in corners)
    patches = "\n".join(
        f"    {face.value}\n    {{\n        type wall;\n"
        f"        faces (({' '.join(str(v) for v in _FACE_VERTICES[face])}));\n    }}"
        for face in Face
    )
    return (
        _header("blockMeshDict")
        + "scale 1;\n\n"
        + f"vertices\n(\n{vertices}\n);\n\n"
        + "blocks\n(\n"
        + f"    hex (0 1 2 3 4 5 6 7) ({grid.cells.x} {grid.cells.y} {grid.cells.z})"
        + " simpleGrading (1 1 1)\n);\n\n"
        + f"boundary\n(\n{patches}\n);\n"
    )


def topo_set_dict(geometry: CfdGeometry) -> str:
    """Each opening's faces, as a face set named for the opening."""
    grid = geometry.grid
    actions: list[str] = []
    for opening in geometry.of(BoundaryCategory.OPENING):
        low, high = _padded(opening.box, grid)
        actions.append(
            f"    {{\n        name {opening.name};\n        type faceSet;\n        action new;\n"
            f"        source boxToFace;\n        box {low} {high};\n    }}"
        )
    return _header("topoSetDict") + "actions\n(\n" + "\n".join(actions) + "\n);\n"


def obstacles_topo_set_dict(geometry: CfdGeometry) -> str:
    """The cells the obstacles remove, and the fluid cells that stay."""
    grid = geometry.grid
    actions: list[str] = []
    obstacles = geometry.of(BoundaryCategory.OBSTACLE)
    for index, obstacle in enumerate(obstacles):
        low, high = _shrunk(obstacle.box, grid)
        actions.append(
            f"    {{\n        name {OBSTACLES_PATCH};\n        type cellSet;\n"
            f"        action {'new' if index == 0 else 'add'};\n"
            f"        source boxToCell;\n        box {low} {high};\n    }}"
        )
    if obstacles:
        actions.append(
            f"    {{\n        name {FLUID_SET};\n        type cellSet;\n        action new;\n"
            f"        source cellToCell;\n        sets ({OBSTACLES_PATCH});\n    }}"
        )
        actions.append(
            f"    {{\n        name {FLUID_SET};\n        type cellSet;\n"
            "        action invert;\n    }"
        )
    return _header("topoSetDict.obstacles") + "actions\n(\n" + "\n".join(actions) + "\n);\n"


def create_patch_dict(geometry: CfdGeometry) -> str:
    patches = "\n".join(
        f"    {{\n        name {opening.name};\n        patchInfo {{ type patch; }}\n"
        f"        constructFrom set;\n        set {opening.name};\n    }}"
        for opening in geometry.of(BoundaryCategory.OPENING)
    )
    return _header("createPatchDict") + "pointSync false;\n\npatches\n(\n" + patches + "\n);\n"


def control_dict(iterations: int = 1) -> str:
    """Steady iterations, the last written; and every field in plain text."""
    return (
        _header("controlDict")
        + "application     simpleFoam;\n"
        + "startFrom       startTime;\nstartTime       0;\n"
        + f"stopAt          endTime;\nendTime         {iterations};\ndeltaT          1;\n"
        + f"writeControl    timeStep;\nwriteInterval   {iterations};\n"
        + "writeFormat     ascii;\nwritePrecision  8;\n"
    )


def fv_schemes() -> str:
    """Steady, incompressible schemes: second order, bounded upwinding for
    the momentum's convection."""
    return (
        _header("fvSchemes")
        + "ddtSchemes\n{\n    default         steadyState;\n}\n\n"
        + "gradSchemes\n{\n    default         Gauss linear;\n}\n\n"
        + "divSchemes\n{\n    default         none;\n"
        + "    div(phi,U)      bounded Gauss linearUpwind grad(U);\n"
        + "    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n\n"
        + "laplacianSchemes\n{\n    default         Gauss linear corrected;\n}\n\n"
        + "interpolationSchemes\n{\n    default         linear;\n}\n\n"
        + "snGradSchemes\n{\n    default         corrected;\n}\n"
    )


def fv_solution() -> str:
    """The SIMPLE algorithm's solvers, its convergence and its relaxation."""
    return (
        _header("fvSolution")
        + "solvers\n{\n"
        + "    p\n    {\n        solver          GAMG;\n        smoother        GaussSeidel;\n"
        + "        tolerance       1e-06;\n        relTol          0.1;\n    }\n"
        + '    "(U|Phi)"\n    {\n        solver          smoothSolver;\n'
        + "        smoother        symGaussSeidel;\n        tolerance       1e-07;\n"
        + "        relTol          0.1;\n    }\n}\n\n"
        + "SIMPLE\n{\n    nNonOrthogonalCorrectors 0;\n    consistent      yes;\n"
        + "    residualControl\n    {\n        p               1e-04;\n"
        + "        U               1e-05;\n    }\n}\n\n"
        + "relaxationFactors\n{\n    equations\n    {\n        U               0.9;\n"
        + '        ".*"            0.9;\n    }\n}\n'
    )


# subsetMesh makes the obstacles' patch an empty one; it is a wall, in the
# walls' group.
_OBSTACLES_AS_WALL: Final = (
    f"foamDictionary constant/polyMesh/boundary -entry entry0/{OBSTACLES_PATCH}/type -set wall",
    f"foamDictionary constant/polyMesh/boundary -entry entry0/{OBSTACLES_PATCH}/inGroups"
    " -set '1(wall)'",
)


def allmesh_script(geometry: CfdGeometry) -> str:
    """The script that meshes the case, each step logging to its own file."""
    steps = ["blockMesh", "topoSet"]
    if geometry.of(BoundaryCategory.OPENING):
        steps.append("createPatch -overwrite")
    if geometry.of(BoundaryCategory.OBSTACLE):
        steps.append("topoSet -dict system/topoSetDict.obstacles")
        steps.append(f"subsetMesh {FLUID_SET} -patch {OBSTACLES_PATCH} -overwrite")
        steps.extend(_OBSTACLES_AS_WALL)
    logs = {step: f"log.{step.split()[0]}" for step in steps}
    logs["topoSet -dict system/topoSetDict.obstacles"] = "log.topoSet.obstacles"
    logs[_OBSTACLES_AS_WALL[0]] = "log.foamDictionary.type"
    logs[_OBSTACLES_AS_WALL[1]] = "log.foamDictionary.inGroups"
    body = "\n".join(f"{step} > {logs[step]} 2>&1" for step in steps)
    return (
        "#!/bin/sh\n"
        f"# Meshes the case, as greenhouse_sim.cfd wrote it, with OpenFOAM {OPENFOAM_VERSION}.\n"
        'cd "${0%/*}" || exit 1\nset -e\n' + body + "\n"
    )


def mesh_case_files(geometry: CfdGeometry) -> dict[str, str]:
    """The files of a case that meshes the geometry, by their paths in it."""
    return {
        "system/blockMeshDict": block_mesh_dict(geometry),
        "system/topoSetDict": topo_set_dict(geometry),
        "system/createPatchDict": create_patch_dict(geometry),
        "system/topoSetDict.obstacles": obstacles_topo_set_dict(geometry),
        "system/controlDict": control_dict(),
        "system/fvSchemes": fv_schemes(),
        "system/fvSolution": fv_solution(),
        MESH_SCRIPT: allmesh_script(geometry),
        "geometry.json": geometry.model_dump_json(indent=2) + "\n",
    }


class SetupRefused(ValueError):
    """A setup that cannot drive a geometry's air."""


@dataclass(frozen=True)
class FlowRoles:
    """Which of a geometry's openings the air comes in through, and which it
    leaves through, by their patches' names."""

    inlets: list[str]
    outlets: list[str]


def flow_roles(geometry: CfdGeometry, setup: CfdSetup) -> FlowRoles:
    """Each opening's part in the flow: the setup's inlets, or the first
    opening, and every other as an outlet. Air must have a way in and a way
    out, so a geometry with fewer than two openings is refused."""
    openings = [b.name for b in geometry.of(BoundaryCategory.OPENING)]
    if len(openings) < 2:
        open_ones = ", ".join(openings) or "none"
        raise SetupRefused(
            f"{geometry.scenario_id} needs two open doors or vents for air to come in and go "
            f"out; it has {open_ones}"
        )
    inlets = setup.inlets if setup.inlets is not None else openings[:1]
    unknown = sorted(set(inlets) - set(openings))
    if unknown or not inlets:
        raise SetupRefused(
            f"{geometry.scenario_id}'s inlets must be some of its open doors and vents "
            f"({', '.join(openings)}), not {', '.join(unknown) or 'none'}"
        )
    outlets = [name for name in openings if name not in inlets]
    if not outlets:
        raise SetupRefused(f"{geometry.scenario_id} has no open door or vent left for air to leave")
    return FlowRoles(inlets=list(inlets), outlets=outlets)


def _field_file(name: str, kind: str, dimensions: str, internal: str, patches: str) -> str:
    return (
        _header(name, "0", kind)
        + f"dimensions      {dimensions};\n\n"
        + f"internalField   uniform {internal};\n\n"
        + "boundaryField\n{\n"
        + patches
        + "}\n"
    )


# Every patch the others do not name: a pattern, which a patch's own name
# takes precedence over.
_EVERY_PATCH: Final = '".*"'


def _entry(name: str, body: str) -> str:
    return f"    {name}\n    {{\n{body}    }}\n"


def velocity_field(roles: FlowRoles, setup: CfdSetup) -> str:
    """The air's starting velocity: still, with its boundaries' conditions.
    Every patch is a wall unless it is an inlet or an outlet."""
    patches = _entry(_EVERY_PATCH, "        type            noSlip;\n")
    for inlet in roles.inlets:
        patches += _entry(
            inlet,
            "        type            surfaceNormalFixedValue;\n"
            # Negative: into the domain.
            f"        refValue        uniform {_number(-setup.inlet_speed_m_s)};\n"
            "        value           uniform (0 0 0);\n",
        )
    for outlet in roles.outlets:
        patches += _entry(
            outlet,
            "        type            pressureInletOutletVelocity;\n"
            "        value           uniform (0 0 0);\n",
        )
    return _field_file("U", "volVectorField", "[0 1 -1 0 0 0 0]", "(0 0 0)", patches)


def pressure_field(roles: FlowRoles) -> str:
    """The air's starting kinematic pressure: the outside's, 0, held at the
    outlets."""
    patches = _entry(_EVERY_PATCH, "        type            zeroGradient;\n")
    for outlet in roles.outlets:
        patches += _entry(
            outlet, "        type            fixedValue;\n        value           uniform 0;\n"
        )
    return _field_file("p", "volScalarField", "[0 2 -2 0 0 0 0]", "0", patches)


def transport_properties(setup: CfdSetup) -> str:
    return (
        _header("transportProperties", "constant")
        + "transportModel  Newtonian;\n\n"
        + f"nu              {_number(setup.effective_viscosity_m2_s)};\n"
    )


def turbulence_properties() -> str:
    """Laminar: turbulence is in the effective viscosity (`setup`)."""
    return _header("turbulenceProperties", "constant") + "simulationType  laminar;\n"


def allrun_script() -> str:
    """The script that meshes the case, solves it, and writes its cells'
    centres beside the solution."""
    return (
        "#!/bin/sh\n"
        f"# Solves the case, as greenhouse_sim.cfd wrote it, with OpenFOAM {OPENFOAM_VERSION}.\n"
        'cd "${0%/*}" || exit 1\nset -e\n'
        f"./{MESH_SCRIPT}\n"
        f"rm -rf 0\ncp -r {INITIAL_FIELDS} 0\n"
        "simpleFoam > log.simpleFoam 2>&1\n"
        "postProcess -func writeCellCentres -latestTime > log.writeCellCentres 2>&1\n"
    )


def solve_case_files(geometry: CfdGeometry, setup: CfdSetup) -> dict[str, str]:
    """The files of a case that meshes the geometry and solves its air as
    the setup drives it, by their paths in it."""
    roles = flow_roles(geometry, setup)
    return mesh_case_files(geometry) | {
        "system/controlDict": control_dict(setup.iterations),
        f"{INITIAL_FIELDS}/U": velocity_field(roles, setup),
        f"{INITIAL_FIELDS}/p": pressure_field(roles),
        "constant/transportProperties": transport_properties(setup),
        "constant/turbulenceProperties": turbulence_properties(),
        SOLVE_SCRIPT: allrun_script(),
    }


def write_case(files: Mapping[str, str], directory: Path) -> list[Path]:
    """Write a case's files into `directory`, its scripts runnable, and
    return their paths."""
    written = []
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if name in (MESH_SCRIPT, SOLVE_SCRIPT):
            path.chmod(SCRIPT_MODE)
        written.append(path)
    return written


def write_mesh_case(geometry: CfdGeometry, directory: Path) -> list[Path]:
    """Write a case that meshes the geometry into `directory`, and return
    the files written."""
    return write_case(mesh_case_files(geometry), directory)


class MeshFailed(RuntimeError):
    """OpenFOAM could not mesh the case."""


@dataclass(frozen=True)
class MeshedPatch:
    """One patch of a meshed case, as OpenFOAM wrote it."""

    name: str
    # OpenFOAM's type for it: wall, patch, empty...
    kind: str
    faces: int


@dataclass(frozen=True)
class Mesh:
    """What OpenFOAM meshed: its cells, and its patches in order."""

    cells: int
    patches: list[MeshedPatch]


_PATCH = re.compile(r"\n\s*(\w+)\s*\{[^}]*?\btype\s+(\w+);[^}]*?\bnFaces\s+(\d+);")
_CELLS = re.compile(r"\bnCells:\s*(\d+)")


def meshed(directory: Path) -> Mesh:
    """The mesh a case holds, read from its `constant/polyMesh`."""
    poly_mesh = directory / "constant" / "polyMesh"
    boundary = (poly_mesh / "boundary").read_text()
    cells = _CELLS.search((poly_mesh / "owner").read_text())
    if cells is None:
        raise MeshFailed(f"{poly_mesh / 'owner'} does not say how many cells there are")
    patches = [
        MeshedPatch(name=name, kind=kind, faces=int(faces))
        for name, kind, faces in _PATCH.findall(boundary)
    ]
    return Mesh(cells=int(cells.group(1)), patches=patches)


def mesh(directory: Path) -> Mesh:
    """Mesh a written case with OpenFOAM, wherever it runs (`runner`), and
    return what it meshed."""
    result = runner.run(directory, f"./{MESH_SCRIPT}")
    if result.returncode != 0:
        logs = sorted(directory.glob("log.*"), key=lambda log: log.stat().st_mtime)
        last = logs[-1].read_text()[-LOG_TAIL:] if logs else result.stderr[-LOG_TAIL:]
        raise MeshFailed(f"{MESH_SCRIPT} failed:\n{last}")
    return meshed(directory)
