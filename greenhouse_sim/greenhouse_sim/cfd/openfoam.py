"""A CFD geometry written as an OpenFOAM case's mesh.

The case is meshed by its `Allmesh` script, in up to five steps:

1. `blockMesh` fills the domain's box with the grid's cells, its six faces
   each a wall patch;
2. `topoSet` gathers each opening's faces (`system/topoSetDict`);
3. `createPatch` moves each opening's faces out of its wall into a patch of
   its own, named for the opening;
4. `topoSet` gathers the cells the obstacles remove
   (`system/topoSetDict.obstacles`), once the patches are made, since
   making them clears the sets;
5. `subsetMesh` removes those cells, and their exposed faces become the
   `obstacles` patch, which `foamDictionary` then makes a wall (subsetMesh
   makes a new patch of type `empty`, and `createPatch` drops a patch
   declared beforehand while it has no faces).

Every opening's and obstacle's selection is a box snapped to the grid
(`geometry`), padded by a fraction of a cell so that faces and cells on its
edges are chosen as `geometry` chose them, and no others.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from greenhouse_sim.cfd import runner
from greenhouse_sim.cfd.geometry import BoundaryCategory, Box, CfdGeometry, Face
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


def _header(name: str, location: str = "system") -> str:
    return (
        f"// Written by greenhouse_sim.cfd for OpenFOAM {OPENFOAM_VERSION}.\n"
        "FoamFile\n{\n"
        "    version     2.0;\n"
        "    format      ascii;\n"
        "    class       dictionary;\n"
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


def control_dict() -> str:
    return (
        _header("controlDict")
        + "application     simpleFoam;\n"
        + "startFrom       startTime;\nstartTime       0;\n"
        + "stopAt          endTime;\nendTime         1;\ndeltaT          1;\n"
        + "writeControl    timeStep;\nwriteInterval   1;\n"
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


# subsetMesh makes the obstacles' patch empty-typed; it is a wall.
_OBSTACLES_AS_WALL: Final = (
    f"foamDictionary constant/polyMesh/boundary -entry entry0/{OBSTACLES_PATCH}/type -set wall"
)


def allmesh_script(geometry: CfdGeometry) -> str:
    """The script that meshes the case, each step logging to its own file."""
    steps = ["blockMesh", "topoSet"]
    if geometry.of(BoundaryCategory.OPENING):
        steps.append("createPatch -overwrite")
    if geometry.of(BoundaryCategory.OBSTACLE):
        steps.append("topoSet -dict system/topoSetDict.obstacles")
        steps.append(f"subsetMesh {FLUID_SET} -patch {OBSTACLES_PATCH} -overwrite")
        steps.append(_OBSTACLES_AS_WALL)
    logs = {step: f"log.{step.split()[0]}" for step in steps}
    logs["topoSet -dict system/topoSetDict.obstacles"] = "log.topoSet.obstacles"
    body = "\n".join(f"{step} > {logs[step]} 2>&1" for step in steps)
    return (
        "#!/bin/sh\n"
        f"# Meshes the case, as greenhouse_sim.cfd wrote it, with OpenFOAM {OPENFOAM_VERSION}.\n"
        'cd "${0%/*}" || exit 1\nset -e\n' + body + "\n"
    )


def write_mesh_case(geometry: CfdGeometry, directory: Path) -> list[Path]:
    """Write the case's mesh definition into `directory`, and return the
    files written."""
    files = {
        directory / "system" / "blockMeshDict": block_mesh_dict(geometry),
        directory / "system" / "topoSetDict": topo_set_dict(geometry),
        directory / "system" / "createPatchDict": create_patch_dict(geometry),
        directory / "system" / "topoSetDict.obstacles": obstacles_topo_set_dict(geometry),
        directory / "system" / "controlDict": control_dict(),
        directory / "system" / "fvSchemes": fv_schemes(),
        directory / "system" / "fvSolution": fv_solution(),
        directory / MESH_SCRIPT: allmesh_script(geometry),
        directory / "geometry.json": geometry.model_dump_json(indent=2) + "\n",
    }
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (directory / MESH_SCRIPT).chmod(SCRIPT_MODE)
    return list(files)


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
