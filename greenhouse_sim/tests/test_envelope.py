"""The greenhouse's envelope and its own frame (decisions 0016 and 0017): known
points land where they should in the world, and the surfaces close the
greenhouse, facing into it."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SceneEntityKind, scene_snapshot
from greenhouse_sim.world.envelope import Envelope, MemberKind, Surface, SurfaceCategory
from greenhouse_sim.world.geometry import Quaternion, Transform, Vector3

# A quarter turn about the world's z: x turns onto y, and y onto -x.
QUARTER_TURN_ABOUT_Z = Quaternion(w=math.sqrt(0.5), z=math.sqrt(0.5))
# A 24 m house of one 12.8 m span, its eaves at 5.5 m and its ridge 2.4 m higher.
HOUSE = Envelope(length=24.0, width=12.8, eave_height=5.5, ridge_height=7.9)
type Point = tuple[float, float, float]


def _close(actual: Vector3, expected: Vector3) -> bool:
    return all(
        actual_value == pytest.approx(expected_value, abs=1e-12)
        for actual_value, expected_value in zip(
            (actual.x, actual.y, actual.z), (expected.x, expected.y, expected.z), strict=True
        )
    )


def _rounded(point: Vector3) -> Point:
    """A point rounded to a micrometre, so that corners can be compared."""
    return (round(point.x, 6), round(point.y, 6), round(point.z, 6))


def _outline(surface: Surface) -> list[Point]:
    """A surface's corners in order, in the greenhouse's frame."""
    shape = surface.shape
    if shape.shape == "plane":
        half_x, half_y = shape.size_x / 2, shape.size_y / 2
        corners = [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
    else:
        corners = [(point.x, point.y) for point in shape.points]
    return [_rounded(surface.transform.apply(Vector3(x=x, y=y, z=0.0))) for x, y in corners]


def _edges(surface: Surface) -> set[frozenset[Point]]:
    """A surface's edges, each as the pair of corners it joins."""
    outline = _outline(surface)
    return {frozenset((outline[i], outline[(i + 1) % len(outline)])) for i in range(len(outline))}


def _by_id(envelope: Envelope) -> dict[str, Surface]:
    return {surface.surface_id: surface for surface in envelope.surfaces()}


def test_a_rotation_turns_vectors_and_a_transform_moves_points() -> None:
    assert _close(QUARTER_TURN_ABOUT_Z.rotate(Vector3(x=1, y=0, z=0)), Vector3(x=0, y=1, z=0))
    assert _close(QUARTER_TURN_ABOUT_Z.rotate(Vector3(x=0, y=1, z=0)), Vector3(x=-1, y=0, z=0))
    assert _close(Quaternion().rotate(Vector3(x=1, y=2, z=3)), Vector3(x=1, y=2, z=3))

    moved = Transform(position=Vector3(x=10, y=0, z=0), rotation=QUARTER_TURN_ABOUT_Z)
    assert _close(moved.apply(Vector3(x=2, y=0, z=1)), Vector3(x=10, y=2, z=1))


def test_a_rotation_built_from_axes_turns_the_frame_onto_them() -> None:
    along_the_slope = Vector3(x=0.0, y=math.cos(0.4), z=math.sin(0.4))
    turn = Quaternion.from_axes(Vector3(x=-1, y=0, z=0), along_the_slope)

    assert _close(turn.rotate(Vector3(x=1, y=0, z=0)), Vector3(x=-1, y=0, z=0))
    assert _close(turn.rotate(Vector3(x=0, y=1, z=0)), along_the_slope)


def test_the_greenhouse_fills_the_positive_octant_of_its_frame() -> None:
    corner, far_corner = HOUSE.bounds()

    assert corner == Vector3(x=0, y=0, z=0)
    assert far_corner == Vector3(x=24.0, y=12.8, z=7.9)


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
    assert _close(placed.to_world(Vector3(x=24, y=12.8, z=7.9)), Vector3(x=87.2, y=74, z=7.9))


@pytest.mark.parametrize(
    "field", ["length", "width", "eave_height", "ridge_height", "spans", "bays"]
)
@pytest.mark.parametrize("size", [0.0, -1.0])
def test_an_envelope_without_room_is_refused(field: str, size: float) -> None:
    sizes: dict[str, float] = {
        "length": 24.0,
        "width": 12.8,
        "eave_height": 5.5,
        "ridge_height": 7.9,
        field: size,
    }

    with pytest.raises(ValidationError):
        Envelope(**sizes)


def test_a_ridge_below_the_eaves_is_refused_and_one_level_with_them_is_flat() -> None:
    with pytest.raises(ValidationError, match="the ridge"):
        Envelope(length=24.0, width=12.8, eave_height=5.5, ridge_height=5.0)

    flat = Envelope(length=24.0, width=12.8, eave_height=5.5, ridge_height=5.5)
    assert flat.roof_pitch == 0.0


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


def test_the_envelope_has_a_floor_four_walls_and_two_roof_slopes() -> None:
    surfaces = HOUSE.surfaces()

    assert [(s.surface_id, s.category) for s in surfaces] == [
        ("floor", SurfaceCategory.FLOOR),
        ("side_wall_right", SurfaceCategory.WALL),
        ("side_wall_left", SurfaceCategory.WALL),
        ("end_wall_front", SurfaceCategory.WALL),
        ("end_wall_back", SurfaceCategory.WALL),
        ("roof_1_right", SurfaceCategory.ROOF),
        ("roof_1_left", SurfaceCategory.ROOF),
    ]


def test_each_surface_has_the_corners_the_configuration_gives_it() -> None:
    length, width = HOUSE.length, HOUSE.width
    eave, ridge, middle = HOUSE.eave_height, HOUSE.ridge_height, HOUSE.width / 2
    surfaces = _by_id(HOUSE)

    def corners(surface_id: str) -> set[Point]:
        return set(_outline(surfaces[surface_id]))

    assert corners("floor") == {(0, 0, 0), (length, 0, 0), (length, width, 0), (0, width, 0)}
    assert corners("side_wall_right") == {
        (0, 0, 0),
        (length, 0, 0),
        (length, 0, eave),
        (0, 0, eave),
    }
    assert corners("side_wall_left") == {
        (0, width, 0),
        (length, width, 0),
        (length, width, eave),
        (0, width, eave),
    }
    for x in (0, length):
        surface_id = "end_wall_front" if x == 0 else "end_wall_back"
        assert corners(surface_id) == {
            (x, 0, 0),
            (x, width, 0),
            (x, width, eave),
            (x, middle, ridge),
            (x, 0, eave),
        }
    assert corners("roof_1_right") == {
        (0, 0, eave),
        (length, 0, eave),
        (length, middle, ridge),
        (0, middle, ridge),
    }
    assert corners("roof_1_left") == {
        (0, width, eave),
        (length, width, eave),
        (length, middle, ridge),
        (0, middle, ridge),
    }


def test_the_cross_section_matches_the_configuration() -> None:
    """The gable is the greenhouse's cross-section: walls to the eaves on both
    sides, and the ridge above the middle of the width."""
    gable = _outline(_by_id(HOUSE)["end_wall_front"])
    heights_across = sorted({(y, z) for _, y, z in gable})

    assert heights_across == [(0, 0), (0, 5.5), (6.4, 7.9), (12.8, 0), (12.8, 5.5)]
    assert HOUSE.roof_pitch == pytest.approx(math.atan2(2.4, 6.4))


def test_every_surface_faces_into_the_greenhouse() -> None:
    """No inverted surfaces: each one's front points at the middle of the house."""
    middle = (HOUSE.length / 2, HOUSE.width / 2, HOUSE.eave_height / 2)

    for surface in HOUSE.surfaces():
        facing = surface.transform.rotation.rotate(Vector3(x=0, y=0, z=1))
        outline = _outline(surface)
        centre = [sum(corner[axis] for corner in outline) / len(outline) for axis in range(3)]
        reach = sum(
            f * (m - c)
            for f, m, c in zip((facing.x, facing.y, facing.z), middle, centre, strict=True)
        )
        assert reach > 0, surface.surface_id


@pytest.mark.parametrize(("ridge_height", "spans"), [(7.9, 1), (5.5, 1), (7.9, 2), (6.2, 5)])
def test_the_surfaces_close_the_greenhouse(ridge_height: float, spans: int) -> None:
    """No gaps: every edge of every surface is shared with exactly one other,
    for a pitched roof and a flat one, of one span and of several."""
    house = HOUSE.model_copy(update={"ridge_height": ridge_height, "spans": spans})
    shared: dict[frozenset[Point], int] = {}
    for surface in house.surfaces():
        for edge in _edges(surface):
            shared[edge] = shared.get(edge, 0) + 1

    assert set(shared.values()) == {2}


@pytest.mark.parametrize(
    ("length", "width", "eave_height", "ridge_height"),
    [(4.0, 3.2, 3.0, 3.65), (60.0, 32.0, 6.5, 12.0)],
)
def test_the_surfaces_follow_the_envelopes_dimensions(
    length: float, width: float, eave_height: float, ridge_height: float
) -> None:
    envelope = Envelope(
        length=length, width=width, eave_height=eave_height, ridge_height=ridge_height
    )
    surfaces = _by_id(envelope)

    assert max(z for _, _, z in _outline(surfaces["end_wall_back"])) == ridge_height
    assert max(z for _, _, z in _outline(surfaces["side_wall_right"])) == eave_height
    assert max(x for x, _, _ in _outline(surfaces["roof_1_left"])) == length
    assert max(y for _, y, _ in _outline(surfaces["floor"])) == width


def test_a_gutter_runs_along_each_eave() -> None:
    right, left = HOUSE.gutters()

    assert (right.gutter_id, right.start, right.end) == (
        "gutter_0",
        Vector3(x=0, y=0, z=5.5),
        Vector3(x=24.0, y=0, z=5.5),
    )
    assert (left.gutter_id, left.start, left.end) == (
        "gutter_1",
        Vector3(x=0, y=12.8, z=5.5),
        Vector3(x=24.0, y=12.8, z=5.5),
    )


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
    assert _close(floor.transform.rotation.rotate(Vector3(x=1, y=0, z=0)), Vector3(x=0, y=1, z=0))


# Five 9.6 m spans and twelve 4.5 m bays: a greenhouse of commercial proportions.
VENLO = Envelope(length=54.0, width=48.0, eave_height=6.0, ridge_height=7.0, spans=5, bays=12)


def test_each_span_has_its_own_roof_and_ridge() -> None:
    surfaces = _by_id(VENLO)
    roofs = [surface for surface in VENLO.surfaces() if surface.category == SurfaceCategory.ROOF]

    assert len(roofs) == 2 * VENLO.spans
    for number in range(1, VENLO.spans + 1):
        ridge_y = 9.6 * (number - 1) + 4.8
        outline = set(_outline(surfaces[f"roof_{number}_right"]))
        assert (0, round(ridge_y, 6), 7.0) in outline
        assert (0, round(9.6 * (number - 1), 6), 6.0) in outline


def test_the_gable_has_a_peak_per_span_and_a_valley_between() -> None:
    gable = _outline(_by_id(VENLO)["end_wall_front"])
    tops = sorted((y, z) for _, y, z in gable if z > 0)

    assert [z for _, z in tops] == [6.0, 7.0] * VENLO.spans + [6.0]
    assert VENLO.roof_pitch == pytest.approx(math.atan2(1.0, 4.8))


def test_a_gutter_runs_along_each_eave_and_each_valley() -> None:
    gutters = VENLO.gutters()

    assert [gutter.start.y for gutter in gutters] == pytest.approx([0, 9.6, 19.2, 28.8, 38.4, 48])
    assert all(gutter.start.z == gutter.end.z == 6.0 for gutter in gutters)
    assert all((gutter.start.x, gutter.end.x) == (0, 54.0) for gutter in gutters)


@pytest.mark.parametrize("bays", [1, 3, 12, 37])
def test_each_bay_count_gives_one_frame_more_than_its_bays(bays: int) -> None:
    house = VENLO.model_copy(update={"bays": bays})
    members = house.members()
    frames = sorted({member.frame for member in members})

    assert frames == list(range(bays + 1))
    posts = [member for member in members if member.kind == MemberKind.POST]
    rafters = [member for member in members if member.kind == MemberKind.RAFTER]
    assert len(posts) == (bays + 1) * (house.spans + 1)
    assert len(rafters) == (bays + 1) * 2 * house.spans


@pytest.mark.parametrize("bays", [3, 7, 37, 1000])
def test_frames_do_not_drift_along_the_house(bays: int) -> None:
    """Each frame stands at exactly its own multiple of the bay spacing, never
    at a sum of spacings, which gathers rounding error along the house: the
    last stands exactly at the back wall, however many bays."""
    house = VENLO.model_copy(update={"bays": bays})
    xs = sorted({member.start.x for member in house.members()})

    assert xs == [house.length * k / bays for k in range(bays + 1)]
    assert xs[-1] == house.length


def test_posts_stand_on_the_gutter_lines_and_rafters_climb_to_the_ridges() -> None:
    gutter_lines = {round(gutter.start.y, 6) for gutter in VENLO.gutters()}
    ridges = {round(9.6 * index + 4.8, 6) for index in range(VENLO.spans)}

    for member in VENLO.members():
        if member.kind == MemberKind.POST:
            assert (member.start.z, member.end.z) == (0.0, 6.0)
            assert round(member.start.y, 6) in gutter_lines
        else:
            assert (member.start.z, member.end.z) == (6.0, 7.0)
            assert round(member.start.y, 6) in gutter_lines
            assert round(member.end.y, 6) in ridges
            assert member.start.x == member.end.x
