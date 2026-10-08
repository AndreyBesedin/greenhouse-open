"""The geometry a CFD solver is given: the air's box, and what bounds it.

The computational domain is the box a scenario's environment fields cover,
the air under the greenhouse's gutters, on the same regular grid. So a
solver's cells are the field's cells, and its result maps onto a field
directly.

- **Boundaries:** the box's six faces: the floor, the four walls, and the
  ceiling at the eaves, which stands for the roof above them.
- **Openings:** a door or vent that is open, however far, lets the air
  through. Its frame's rectangle is projected onto the face it opens in; a
  roof vent onto the ceiling. It is snapped to the mesh's faces whose
  centres lie inside it, or, if none do, the one face nearest its centre. A
  face belongs to one opening at most, the first that claims it; one left
  with no face is said to be.
- **Obstacles:** a fixture that obstructs airflow removes the mesh's cells
  whose centres lie inside it. One too small to hold any cell's centre is
  left out at this resolution, and said to be.

Everything is described as it will be meshed, snapped to the grid, so what a
viewer draws of it is exactly what the solver sees. A viewer reads it as
`CfdGeometry`, described by `geometry.schema.json` next to this module.
"""

import math
from enum import StrEnum
from typing import Final, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.domain.envelope import OpeningKind, SurfaceCategory
from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import Opening, Surface
from greenhouse_sim.world.geometry import Vector3

CFD_GEOMETRY_SCHEMA_VERSION: Final = 1
# How far from one of the box's faces a point may lie and still be on it, in
# metres.
ON_FACE_M: Final = 1e-6


class BoundaryCategory(StrEnum):
    """What a boundary of the CFD domain is."""

    FLOOR = "floor"
    WALL = "wall"
    # The plane at the eaves, standing for the roof above it.
    CEILING = "ceiling"
    OPENING = "opening"
    OBSTACLE = "obstacle"


class Face(StrEnum):
    """One of the domain's six faces, by where it lies."""

    FLOOR = "floor"
    CEILING = "ceiling"
    FRONT = "wall_front"
    BACK = "wall_back"
    RIGHT = "wall_right"
    LEFT = "wall_left"


# Each face: the axis it is square to, whether it lies at the box's far end
# along it, and the two axes across it.
FACES: Final[dict[Face, tuple[str, bool, tuple[str, str]]]] = {
    Face.FLOOR: ("z", False, ("x", "y")),
    Face.CEILING: ("z", True, ("x", "y")),
    Face.FRONT: ("x", False, ("y", "z")),
    Face.BACK: ("x", True, ("y", "z")),
    Face.RIGHT: ("y", False, ("x", "z")),
    Face.LEFT: ("y", True, ("x", "z")),
}


class Box(BaseModel):
    """An axis-aligned box, by its lowest and highest corners."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum: Vector3
    maximum: Vector3


class Boundary(BaseModel):
    """One boundary of the domain as it is meshed: what it is, and the faces
    of the mesh it is made of."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Its name in the case, unique.
    name: str
    category: BoundaryCategory
    # The domain face it lies on, for a face or an opening.
    face: Face | None = None
    # For an opening: its identifier and kind in the greenhouse.
    opening_id: str | None = None
    opening_kind: OpeningKind | None = None
    # The rectangle it covers, snapped to the mesh, as a flat box; for an
    # obstacle, the cells it removes.
    box: Box
    # How many of the mesh's faces it is made of; for an obstacle, how many
    # cells it removes.
    mesh_faces: int


class CfdGeometry(BaseModel):
    """What a solver is given for a scenario: the domain, on its grid, and
    every boundary, as they will be meshed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = CFD_GEOMETRY_SCHEMA_VERSION
    scenario_id: str
    grid: FieldGrid
    boundaries: list[Boundary]
    # Fixtures that obstruct airflow but hold no cell's centre at this
    # resolution, by identifier.
    too_small: list[str]
    # Open doors and vents left with no face of the mesh: each it would have
    # had is another's, or it opens in none of the domain's faces.
    unplaced: list[str]

    def of(self, category: BoundaryCategory) -> list[Boundary]:
        """Its boundaries of one category, in order."""
        return [b for b in self.boundaries if b.category == category]

    def solid(self) -> np.ndarray:
        """The cells of its grid that obstacles remove, as they are meshed, in
        the grid's order (z, y, x)."""
        xs, ys, zs = self.grid.centres()
        solid = np.zeros((zs.size, ys.size, xs.size), dtype=bool)
        for obstacle in self.of(BoundaryCategory.OBSTACLE):
            low, high = obstacle.box.minimum, obstacle.box.maximum
            solid |= (
                ((zs >= low.z) & (zs <= high.z))[:, None, None]
                & ((ys >= low.y) & (ys <= high.y))[None, :, None]
                & ((xs >= low.x) & (xs <= high.x))[None, None, :]
            )
        return solid


def _axis(point: Vector3, axis: str) -> float:
    return float(getattr(point, axis))


def _point(**coordinates: float) -> Vector3:
    return Vector3(x=coordinates["x"], y=coordinates["y"], z=coordinates["z"])


def _centres(grid: FieldGrid, axis: str) -> list[float]:
    count = getattr(grid.cells, axis)
    size = _axis(grid.cell_size, axis)
    origin = _axis(grid.origin, axis)
    return [origin + (index + 1 / 2) * size for index in range(count)]


def _edges(grid: FieldGrid, axis: str, first: int, last: int) -> tuple[float, float]:
    """Where cells `first` to `last` (inclusive) begin and end along an axis."""
    size = _axis(grid.cell_size, axis)
    origin = _axis(grid.origin, axis)
    return origin + first * size, origin + (last + 1) * size


def _within(grid: FieldGrid, axis: str, low: float, high: float) -> list[int]:
    """The cells along an axis whose centres lie between `low` and `high`."""
    return [i for i, centre in enumerate(_centres(grid, axis)) if low <= centre <= high]


def _face_box(grid: FieldGrid, face: Face, across: dict[str, tuple[int, int]]) -> Box:
    """The flat box on a face covering the mesh faces in index ranges
    `across`, by axis."""
    axis, far, _ = FACES[face]
    top = grid.maximum
    level = _axis(top, axis) if far else _axis(grid.origin, axis)
    low: dict[str, float] = {axis: level}
    high: dict[str, float] = {axis: level}
    for name, (first, last) in across.items():
        low[name], high[name] = _edges(grid, name, first, last)
    return Box(minimum=_point(**low), maximum=_point(**high))


def _whole_face(grid: FieldGrid, face: Face) -> tuple[Box, int]:
    _, _, (first_axis, second_axis) = FACES[face]
    counts = {name: getattr(grid.cells, name) for name in (first_axis, second_axis)}
    box = _face_box(grid, face, {name: (0, count - 1) for name, count in counts.items()})
    return box, math.prod(counts.values())


def _face_of(surface: Surface, corners: list[Vector3], grid: FieldGrid) -> Face | None:
    """The domain face an opening in this surface opens in: the face its
    corners lie on, or for a roof, the ceiling."""
    if surface.category == SurfaceCategory.ROOF:
        return Face.CEILING
    top = grid.maximum
    for face, (axis, far, _) in FACES.items():
        level = _axis(top, axis) if far else _axis(grid.origin, axis)
        if all(abs(_axis(corner, axis) - level) < ON_FACE_M for corner in corners):
            return face
    return None


def _opening_faces(grid: FieldGrid, face: Face, corners: list[Vector3]) -> dict[str, list[int]]:
    """The mesh faces an opening covers on its face, as the cells' indices
    along the two axes across it: those whose centres lie inside it, or the
    one nearest its centre."""
    _, _, axes = FACES[face]
    chosen: dict[str, list[int]] = {}
    for axis in axes:
        values = [_axis(corner, axis) for corner in corners]
        low, high = min(values), max(values)
        inside = _within(grid, axis, low, high)
        if not inside:
            middle = (low + high) / 2
            centres = _centres(grid, axis)
            inside = [min(range(len(centres)), key=lambda i: abs(centres[i] - middle))]
        chosen[axis] = inside
    return chosen


def _opening_corners(surface: Surface, opening: Opening) -> list[Vector3]:
    return [surface.transform.apply(Vector3(x=c.x, y=c.y, z=0.0)) for c in opening.corners()]


def cfd_geometry(scenario_id: str, config: ScenarioConfig, grid: FieldGrid) -> CfdGeometry:
    """The geometry a solver is given for a scenario, on `grid`."""
    boundaries: list[Boundary] = []
    categories = {Face.FLOOR: BoundaryCategory.FLOOR, Face.CEILING: BoundaryCategory.CEILING}
    for side in Face:
        box, faces = _whole_face(grid, side)
        category = categories.get(side, BoundaryCategory.WALL)
        boundaries.append(
            Boundary(name=side.value, category=category, face=side, box=box, mesh_faces=faces)
        )

    hosts = {surface.surface_id: surface for surface in config.envelope.surfaces()}
    claimed: set[tuple[Face, int, int]] = set()
    unplaced: list[str] = []
    for opening in config.envelope.openings:
        if opening.opening == 0:
            continue
        host = hosts[opening.surface_id]
        corners = _opening_corners(host, opening)
        face = _face_of(host, corners, grid)
        if face is None:
            unplaced.append(opening.opening_id)
            continue
        chosen = _opening_faces(grid, face, corners)
        first_axis, second_axis = FACES[face][2]
        mine = {
            (face, i, j)
            for i in chosen[first_axis]
            for j in chosen[second_axis]
            if (face, i, j) not in claimed
        }
        if not mine:
            unplaced.append(opening.opening_id)
            continue
        claimed |= mine
        across = {
            first_axis: (min(i for _, i, _ in mine), max(i for _, i, _ in mine)),
            second_axis: (min(j for _, _, j in mine), max(j for _, _, j in mine)),
        }
        boundaries.append(
            Boundary(
                name=opening.opening_id,
                category=BoundaryCategory.OPENING,
                face=face,
                opening_id=opening.opening_id,
                opening_kind=opening.kind,
                box=_face_box(grid, face, across),
                mesh_faces=len(mine),
            )
        )

    too_small = []
    for fixture in config.layout.obstructing(Obstruction.AIRFLOW):
        low, high = fixture.bounds()
        cells = {axis: _within(grid, axis, _axis(low, axis), _axis(high, axis)) for axis in "xyz"}
        if not all(cells.values()):
            too_small.append(fixture.fixture_id)
            continue
        removed: dict[str, float] = {}
        kept: dict[str, float] = {}
        for axis, indices in cells.items():
            removed[axis], kept[axis] = _edges(grid, axis, min(indices), max(indices))
        boundaries.append(
            Boundary(
                name=f"obstacle_{fixture.fixture_id}",
                category=BoundaryCategory.OBSTACLE,
                box=Box(minimum=_point(**removed), maximum=_point(**kept)),
                mesh_faces=math.prod(len(indices) for indices in cells.values()),
            )
        )
    return CfdGeometry(
        scenario_id=scenario_id,
        grid=grid,
        boundaries=boundaries,
        too_small=too_small,
        unplaced=unplaced,
    )


def cfd_geometry_json_schema() -> dict[str, object]:
    """The JSON Schema a viewer validates a CFD geometry against, written as
    `geometry.schema.json` next to this module."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **CfdGeometry.model_json_schema(mode="serialization"),
    }
