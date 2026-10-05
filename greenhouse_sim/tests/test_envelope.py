"""The greenhouse's envelope and its own frame (decision 0016): known points
of the greenhouse land where they should in the world."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SceneEntityKind, scene_snapshot
from greenhouse_sim.world.envelope import Envelope, Surface, SurfaceCategory
from greenhouse_sim.world.geometry import Quaternion, Transform, Vector3

# A quarter turn about the world's z: x turns onto y, and y onto -x.
QUARTER_TURN_ABOUT_Z = Quaternion(w=math.sqrt(0.5), z=math.sqrt(0.5))
HOUSE = Envelope(length=24.0, width=12.8, height=5.5)


def _close(actual: Vector3, expected: Vector3) -> bool:
    return all(
        actual_value == pytest.approx(expected_value, abs=1e-12)
        for actual_value, expected_value in zip(
            (actual.x, actual.y, actual.z), (expected.x, expected.y, expected.z), strict=True
        )
    )


def test_a_rotation_turns_vectors_and_a_transform_moves_points() -> None:
    assert _close(QUARTER_TURN_ABOUT_Z.rotate(Vector3(x=1, y=0, z=0)), Vector3(x=0, y=1, z=0))
    assert _close(QUARTER_TURN_ABOUT_Z.rotate(Vector3(x=0, y=1, z=0)), Vector3(x=-1, y=0, z=0))
    assert _close(Quaternion().rotate(Vector3(x=1, y=2, z=3)), Vector3(x=1, y=2, z=3))

    moved = Transform(position=Vector3(x=10, y=0, z=0), rotation=QUARTER_TURN_ABOUT_Z)
    assert _close(moved.apply(Vector3(x=2, y=0, z=1)), Vector3(x=10, y=2, z=1))


def test_the_greenhouse_fills_the_positive_octant_of_its_frame() -> None:
    corner, far_corner = HOUSE.bounds()

    assert corner == Vector3(x=0, y=0, z=0)
    assert far_corner == Vector3(x=24.0, y=12.8, z=5.5)


def test_by_default_the_greenhouse_frame_is_the_world_frame() -> None:
    point = Vector3(x=3.0, y=4.0, z=1.5)

    assert _close(HOUSE.to_world(point), point)


def test_known_points_of_a_placed_greenhouse_land_where_they_should() -> None:
    placed = HOUSE.model_copy(
        update={
            "origin": Transform(
                position=Vector3(x=100.0, y=50.0, z=0.0), rotation=QUARTER_TURN_ABOUT_Z
            )
        }
    )

    # Its floor corner is its origin; its length now runs along the world's y,
    # and its width along the world's -x.
    assert _close(placed.to_world(Vector3(x=0, y=0, z=0)), Vector3(x=100, y=50, z=0))
    assert _close(placed.to_world(Vector3(x=24, y=0, z=0)), Vector3(x=100, y=74, z=0))
    assert _close(placed.to_world(Vector3(x=0, y=12.8, z=0)), Vector3(x=87.2, y=50, z=0))
    assert _close(placed.to_world(Vector3(x=24, y=12.8, z=5.5)), Vector3(x=87.2, y=74, z=5.5))


@pytest.mark.parametrize("field", ["length", "width", "height"])
@pytest.mark.parametrize("size", [0.0, -1.0])
def test_an_envelope_without_room_is_refused(field: str, size: float) -> None:
    sizes = {"length": 24.0, "width": 12.8, "height": 5.5, field: size}

    with pytest.raises(ValidationError):
        Envelope(**sizes)


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_every_scenario_keeps_its_plants_inside_its_greenhouse(scenario_id: str) -> None:
    config = SCENARIO_REGISTRY[scenario_id]
    plant_ids = [f"{scenario_id}_plant_{i:03d}" for i in range(1, config.rows * config.columns + 1)]
    world = SimulationEngine(config).initialize(plant_ids, greenhouse_id=scenario_id)
    scene = scene_snapshot(world, config)
    _, far_corner = config.envelope.bounds()

    for entity in scene.entities:
        if entity.kind != SceneEntityKind.PLANT:
            continue
        position = entity.transform.position
        assert 0.0 < position.x < far_corner.x, entity.entity_id
        assert 0.0 < position.y < far_corner.y, entity.entity_id


def _corners(surface: Surface) -> set[tuple[float, float, float]]:
    """A surface's four corners in the greenhouse's frame, rounded to a micrometre."""
    half_x, half_y = surface.shape.size_x / 2, surface.shape.size_y / 2
    corners = set()
    for x, y in [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]:
        point = surface.transform.apply(Vector3(x=x, y=y, z=0.0))
        corners.add((round(point.x, 6), round(point.y, 6), round(point.z, 6)))
    return corners


def _edges(surface: Surface) -> set[frozenset[tuple[float, float, float]]]:
    """A rectangle's four edges, each as the pair of corners it joins."""
    half_x, half_y = surface.shape.size_x / 2, surface.shape.size_y / 2
    loop = [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
    points = []
    for x, y in loop:
        point = surface.transform.apply(Vector3(x=x, y=y, z=0.0))
        points.append((round(point.x, 6), round(point.y, 6), round(point.z, 6)))
    return {frozenset((points[i], points[(i + 1) % len(points)])) for i in range(len(points))}


def test_the_envelope_has_one_floor_and_four_walls_with_their_own_names() -> None:
    surfaces = HOUSE.surfaces()

    assert [(s.surface_id, s.category) for s in surfaces] == [
        ("floor", SurfaceCategory.FLOOR),
        ("side_wall_right", SurfaceCategory.WALL),
        ("side_wall_left", SurfaceCategory.WALL),
        ("end_wall_front", SurfaceCategory.WALL),
        ("end_wall_back", SurfaceCategory.WALL),
    ]


def test_the_floor_covers_the_footprint_and_the_walls_stand_on_its_edges() -> None:
    floor, right, left, front, back = HOUSE.surfaces()
    length, width, height = HOUSE.length, HOUSE.width, HOUSE.height

    assert _corners(floor) == {(0, 0, 0), (length, 0, 0), (length, width, 0), (0, width, 0)}
    assert _corners(right) == {(0, 0, 0), (length, 0, 0), (length, 0, height), (0, 0, height)}
    assert _corners(left) == {
        (0, width, 0),
        (length, width, 0),
        (length, width, height),
        (0, width, height),
    }
    assert _corners(front) == {(0, 0, 0), (0, width, 0), (0, width, height), (0, 0, height)}
    assert _corners(back) == {
        (length, 0, 0),
        (length, width, 0),
        (length, width, height),
        (length, 0, height),
    }


def test_every_surface_faces_into_the_greenhouse() -> None:
    """No inverted surfaces: each one's front points at the middle of the house."""
    middle = Vector3(x=HOUSE.length / 2, y=HOUSE.width / 2, z=HOUSE.height / 2)

    for surface in HOUSE.surfaces():
        facing = surface.transform.rotation.rotate(Vector3(x=0, y=0, z=1))
        centre = surface.transform.position
        towards_middle = (middle.x - centre.x, middle.y - centre.y, middle.z - centre.z)
        reach = sum(
            f * t for f, t in zip((facing.x, facing.y, facing.z), towards_middle, strict=True)
        )
        assert reach > 0, surface.surface_id


def test_the_surfaces_close_the_greenhouse_up_to_its_open_top() -> None:
    """No gaps: every edge of the floor and every corner post is shared by
    exactly two surfaces. The top edges have one each, until the roof (P01.3)."""
    shared: dict[frozenset[tuple[float, float, float]], int] = {}
    for surface in HOUSE.surfaces():
        for edge in _edges(surface):
            shared[edge] = shared.get(edge, 0) + 1

    on_top = {
        edge: count for edge, count in shared.items() if all(p[2] == HOUSE.height for p in edge)
    }
    below = {edge: count for edge, count in shared.items() if edge not in on_top}
    assert len(below) == 8 and set(below.values()) == {2}
    assert len(on_top) == 4 and set(on_top.values()) == {1}


@pytest.mark.parametrize(("length", "width", "height"), [(4.0, 3.2, 4.0), (60.0, 32.0, 6.5)])
def test_the_surfaces_follow_the_envelopes_dimensions(
    length: float, width: float, height: float
) -> None:
    floor, right, *_, back = Envelope(length=length, width=width, height=height).surfaces()

    assert (floor.shape.size_x, floor.shape.size_y) == (length, width)
    assert (right.shape.size_x, right.shape.size_y) == (length, height)
    assert back.transform.position == Vector3(x=length, y=width / 2, z=height / 2)


def test_a_placed_greenhouse_places_its_surfaces() -> None:
    placed = HOUSE.model_copy(
        update={
            "origin": Transform(
                position=Vector3(x=100.0, y=50.0, z=0.0), rotation=QUARTER_TURN_ABOUT_Z
            )
        }
    )
    floor = placed.surfaces_in_world()[0]

    # The floor's middle, half the length along the world's y and half the
    # width along its -x.
    assert _close(floor.transform.position, Vector3(x=100 - 6.4, y=50 + 12, z=0))
    assert floor.transform.rotation == QUARTER_TURN_ABOUT_Z
