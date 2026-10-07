"""The geometry a CFD solver is given, and the OpenFOAM case that meshes it.

The domain is a scenario's field box, bounded by its floor, four walls and
ceiling; open doors and vents are openings in them, and fixtures in the
air's way are obstacles. Each is snapped to the mesh, so the case's
selections are checked here against the grid's own face and cell centres,
and, with `pytest -m cfd`, against what OpenFOAM meshes.

`greenhouse_sim/cfd/geometry.schema.json` is the schema the viewer generates
its CFD geometry types from. It is written here, from `greenhouse_sim/`:

    python tests/test_cfd_geometry.py --update
"""

import itertools
import json
import re
import sys
from http import HTTPStatus
from pathlib import Path

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.cfd.__main__ import main
from greenhouse_sim.cfd.geometry import (
    FACES,
    Boundary,
    BoundaryCategory,
    CfdGeometry,
    Face,
    cfd_geometry,
    cfd_geometry_json_schema,
)
from greenhouse_sim.cfd.openfoam import (
    OBSTACLES_PATCH,
    allmesh_script,
    block_mesh_dict,
    mesh,
    obstacles_topo_set_dict,
    topo_set_dict,
)
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.services import cfd, fields
from greenhouse_sim.services.scenarios import SceneChanges, scenario
from greenhouse_sim.world.geometry import Vector3

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "greenhouse_sim" / "cfd" / "geometry.schema.json"
GH_001 = cfd.geometry("gh_001")
# gh_001 with its door open, and one vent shut.
OPENED = SceneChanges(openings={"door_1": 1.0, "roof_vent_2": 0.0})
SCENARIOS = ("gh_001", "gh_demo", "gh_002")
WHOLE_FACES = (Face.FLOOR, Face.CEILING, Face.FRONT, Face.BACK, Face.RIGHT, Face.LEFT)
_BOX = r"box\s+\(([^)]*)\)\s+\(([^)]*)\)"


def _centres(grid: FieldGrid, axis: str) -> list[float]:
    size = getattr(grid.cell_size, axis)
    start = getattr(grid.origin, axis)
    return [start + (i + 0.5) * size for i in range(getattr(grid.cells, axis))]


def _inside(point: dict[str, float], low: Vector3, high: Vector3) -> bool:
    return all(getattr(low, a) <= point[a] <= getattr(high, a) for a in "xyz")


def _face_centres(grid: FieldGrid, face: Face) -> list[dict[str, float]]:
    """The centres of the mesh's faces on one of the domain's faces."""
    axis, far, (first, second) = FACES[face]
    level = getattr(grid.maximum if far else grid.origin, axis)
    return [
        {axis: level, first: a, second: b}
        for a, b in itertools.product(_centres(grid, first), _centres(grid, second))
    ]


def _cell_centres(grid: FieldGrid) -> list[dict[str, float]]:
    xs, ys, zs = (_centres(grid, axis) for axis in "xyz")
    return [{"x": x, "y": y, "z": z} for x, y, z in itertools.product(xs, ys, zs)]


def _selection(dictionary: str, name: str) -> tuple[Vector3, Vector3]:
    """The box an action named `name` selects with, in a topoSetDict."""
    action = re.search(rf"name {name};.*?{_BOX}", dictionary, re.DOTALL)
    assert action is not None, name
    low, high = ([float(v) for v in corner.split()] for corner in action.groups())
    return Vector3(x=low[0], y=low[1], z=low[2]), Vector3(x=high[0], y=high[1], z=high[2])


def _footprint(obstacle: Boundary, grid: FieldGrid, face: Face) -> int:
    """How many of a face's mesh faces an obstacle standing on it removes."""
    axis, far, (first, second) = FACES[face]
    level = getattr(grid.maximum if far else grid.origin, axis)
    side = getattr(obstacle.box.maximum if far else obstacle.box.minimum, axis)
    if abs(side - level) > 1e-9:
        return 0
    return sum(
        _inside(point, obstacle.box.minimum, obstacle.box.maximum)
        for point in _face_centres(grid, face)
    )


def test_the_domain_is_the_fields_box_bounded_by_its_floor_walls_and_ceiling() -> None:
    grid = fields.grid("gh_001")
    nx, ny, nz = grid.shape
    sides = [b for b in GH_001.boundaries if b.category != BoundaryCategory.OPENING and b.face]

    assert GH_001.grid == grid
    assert [(b.name, b.category, b.face) for b in sides] == [
        ("floor", BoundaryCategory.FLOOR, Face.FLOOR),
        ("ceiling", BoundaryCategory.CEILING, Face.CEILING),
        ("wall_front", BoundaryCategory.WALL, Face.FRONT),
        ("wall_back", BoundaryCategory.WALL, Face.BACK),
        ("wall_right", BoundaryCategory.WALL, Face.RIGHT),
        ("wall_left", BoundaryCategory.WALL, Face.LEFT),
    ]
    assert [b.mesh_faces for b in sides] == [nx * ny, nx * ny, ny * nz, ny * nz, nx * nz, nx * nz]
    # The ceiling at the eaves, 3.5 m up.
    assert sides[1].box.minimum.z == sides[1].box.maximum.z == pytest.approx(3.5)


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_every_boundary_is_one_the_greenhouse_has_by_its_category(scenario_id: str) -> None:
    config = scenario(scenario_id)
    geometry = cfd.geometry(scenario_id)
    open_ones = [o.opening_id for o in config.envelope.openings if o.opening > 0]
    in_the_way = [f.fixture_id for f in config.layout.obstructing(Obstruction.AIRFLOW)]
    obstacles = [b.name.removeprefix("obstacle_") for b in geometry.of(BoundaryCategory.OBSTACLE)]

    assert len(geometry.of(BoundaryCategory.FLOOR)) == 1
    assert len(geometry.of(BoundaryCategory.CEILING)) == 1
    assert len(geometry.of(BoundaryCategory.WALL)) == 4
    assert [b.name for b in geometry.of(BoundaryCategory.OPENING)] + geometry.unplaced == open_ones
    assert sorted(obstacles + geometry.too_small) == sorted(in_the_way)
    assert len({b.name for b in geometry.boundaries}) == len(geometry.boundaries)


def test_only_open_doors_and_vents_are_openings_each_on_the_face_it_opens_in() -> None:
    opened = cfd.geometry("gh_001", OPENED)

    assert [(b.name, b.opening_kind, b.face) for b in GH_001.of(BoundaryCategory.OPENING)] == [
        ("roof_vent_1", OpeningKind.ROOF_VENT, Face.CEILING),
        ("roof_vent_2", OpeningKind.ROOF_VENT, Face.CEILING),
    ]
    assert [(b.name, b.opening_kind, b.face) for b in opened.of(BoundaryCategory.OPENING)] == [
        ("roof_vent_1", OpeningKind.ROOF_VENT, Face.CEILING),
        ("door_1", OpeningKind.DOOR, Face.FRONT),
    ]
    # The door, about 1 m by 2 m, is 2 faces wide and 4 high.
    door = opened.of(BoundaryCategory.OPENING)[1]
    assert door.mesh_faces == 8
    assert door.box.minimum.z == 0.0


def test_an_opening_covers_whole_faces_of_the_mesh_the_selection_finds_exactly() -> None:
    geometry = cfd.geometry("gh_001", OPENED)
    selections = topo_set_dict(geometry)

    for opening in geometry.of(BoundaryCategory.OPENING):
        assert opening.face is not None
        on_face = _face_centres(geometry.grid, opening.face)
        covered = [p for p in on_face if _inside(p, opening.box.minimum, opening.box.maximum)]
        selected = [p for p in on_face if _inside(p, *_selection(selections, opening.name))]
        assert len(covered) == opening.mesh_faces
        assert selected == covered


def test_an_obstacle_removes_the_cells_its_fixture_holds_and_the_selection_finds_them() -> None:
    fixture = next(
        f for f in scenario("gh_001").layout.fixtures() if f.fixture_id == "irrigation_unit"
    )
    low, high = fixture.bounds()
    centres = _cell_centres(GH_001.grid)
    held = [p for p in centres if _inside(p, low, high)]
    (obstacle,) = GH_001.of(BoundaryCategory.OBSTACLE)
    selected = [
        p
        for p in centres
        if _inside(p, *_selection(obstacles_topo_set_dict(GH_001), OBSTACLES_PATCH))
    ]

    assert obstacle.name == "obstacle_irrigation_unit"
    assert obstacle.mesh_faces == len(held) == 6
    assert [p for p in centres if _inside(p, obstacle.box.minimum, obstacle.box.maximum)] == held
    assert selected == held
    # The crop's slabs and supports are narrower than a cell.
    assert "row_1_slab_1" in GH_001.too_small


def test_at_a_coarser_resolution_openings_crowd_and_obstacles_vanish() -> None:
    config = scenario("gh_001")
    envelope = config.envelope
    top = Vector3(x=envelope.length, y=envelope.width, z=envelope.eave_height)
    # One cell across the house: both vents would open in the ceiling's one
    # face across it, so the first takes it.
    coarse = FieldGrid.over(Vector3(x=0, y=0, z=0), top, max(top.x, top.y, top.z))
    geometry = cfd_geometry("gh_001", config, coarse)

    assert coarse.shape == (1, 1, 1)
    assert [b.mesh_faces for b in geometry.of(BoundaryCategory.OPENING)] == [1]
    assert geometry.unplaced == ["roof_vent_2"]
    assert geometry.of(BoundaryCategory.OBSTACLE) == []
    assert "irrigation_unit" in geometry.too_small


def test_the_case_meshes_the_grid_and_takes_only_the_steps_it_needs() -> None:
    nx, ny, nz = GH_001.grid.shape
    blocks = block_mesh_dict(GH_001)
    gh_002 = cfd.geometry("gh_002")

    assert f"hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz})" in blocks
    assert re.findall(r"\n    (\w+)\n    \{\n        type wall;", blocks) == [
        face.value for face in WHOLE_FACES
    ]
    assert "(8 9.6 3.5)" in blocks
    assert [line.split()[0] for line in allmesh_script(GH_001).splitlines()[4:]] == [
        "blockMesh",
        "topoSet",
        "createPatch",
        "topoSet",
        "subsetMesh",
        "foamDictionary",
        "foamDictionary",
    ]
    assert [line.split()[0] for line in allmesh_script(gh_002).splitlines()[4:]] == [
        "blockMesh",
        "topoSet",
    ]


def test_a_scenarios_cfd_geometry_is_served_changed_as_its_scene_is() -> None:
    answer = respond("GET", "/api/scenarios/gh_001/cfd/geometry")
    opened = respond("GET", "/api/scenarios/gh_001/cfd/geometry?open=door_1:1,roof_vent_2:0")

    assert answer.status == HTTPStatus.OK
    assert CfdGeometry.model_validate(answer.body) == GH_001
    assert CfdGeometry.model_validate(opened.body) == cfd.geometry("gh_001", OPENED)
    assert respond("GET", "/api/scenarios/gh_999/cfd/geometry").status == HTTPStatus.NOT_FOUND
    assert (
        respond("GET", "/api/scenarios/gh_001/cfd/geometry?open=hatch:1").status
        == HTTPStatus.BAD_REQUEST
    )


def test_the_published_schema_matches_the_cfd_geometry() -> None:
    assert json.loads(SCHEMA_FILE.read_text()) == json.loads(json.dumps(cfd_geometry_json_schema()))


def test_the_command_line_writes_a_case_described_as_the_api_describes_it(tmp_path: Path) -> None:
    case = tmp_path / "gh_001"

    assert main(["gh_001", str(case), "--open", "door_1:1,roof_vent_2:0"]) == 0
    assert (case / "Allmesh").stat().st_mode & 0o111
    written = CfdGeometry.model_validate_json((case / "geometry.json").read_text())
    assert written == cfd.geometry("gh_001", OPENED)
    with pytest.raises(SystemExit):
        main(["gh_001", str(tmp_path / "other"), "--open", "hatch:1"])
    assert not (tmp_path / "other").exists()


@pytest.mark.cfd
def test_openfoam_meshes_exactly_the_boundaries_the_geometry_describes(tmp_path: Path) -> None:
    geometry = cfd.geometry("gh_001", OPENED)
    cfd.write_case("gh_001", tmp_path, OPENED)
    grid = geometry.grid
    obstacles = geometry.of(BoundaryCategory.OBSTACLE)

    meshed = mesh(tmp_path)

    expected = {}
    for side in WHOLE_FACES:
        (whole,) = [b for b in geometry.boundaries if b.name == side.value]
        openings = [b for b in geometry.of(BoundaryCategory.OPENING) if b.face == side]
        removed = sum(_footprint(o, grid, side) for o in obstacles)
        expected[side.value] = (
            "wall",
            whole.mesh_faces - sum(o.mesh_faces for o in openings) - removed,
        )
    for opening in geometry.of(BoundaryCategory.OPENING):
        expected[opening.name] = ("patch", opening.mesh_faces)
    expected[OBSTACLES_PATCH] = ("wall", meshed.patches[-1].faces)
    assert {p.name: (p.kind, p.faces) for p in meshed.patches} == expected
    assert meshed.cells == grid.cells.x * grid.cells.y * grid.cells.z - sum(
        o.mesh_faces for o in obstacles
    )
    # The irrigation unit's 6 cells, 1 by 2 by 3 on the floor, expose 2 by 3
    # faces on either side, 1 by 3 at either end, and 1 by 2 on top.
    assert meshed.patches[-1].faces == 2 * 6 + 2 * 3 + 2


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_cfd_geometry.py --update")
    SCHEMA_FILE.write_text(
        json.dumps(cfd_geometry_json_schema(), indent=2, ensure_ascii=False) + "\n"
    )
    print("wrote", SCHEMA_FILE)
