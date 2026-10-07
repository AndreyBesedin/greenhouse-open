"""Fixture primitives: each builds fixtures of exactly its configured
dimensions, where it says, with a kind, a material and what it obstructs."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.layout import FixtureKind, Material, Obstruction
from greenhouse_sim.world.fixtures import (
    DEFAULT_MATERIALS,
    DEFAULT_OBSTRUCTIONS,
    WALKWAY_THICKNESS_M,
    BoxPrimitive,
    CylinderPrimitive,
    Fixture,
    PipePrimitive,
    RailPrimitive,
    TrayPrimitive,
    WalkwayPrimitive,
)
from greenhouse_sim.world.geometry import Box, Cylinder, Point2, Vector3

UP = Vector3(x=0.0, y=0.0, z=1.0)


def _only(fixtures: list[Fixture]) -> Fixture:
    assert len(fixtures) == 1
    return fixtures[0]


def _close(actual: Vector3, expected: tuple[float, float, float]) -> bool:
    return all(
        math.isclose(a, e, abs_tol=1e-12)
        for a, e in zip((actual.x, actual.y, actual.z), expected, strict=True)
    )


def _axis(fixture: Fixture) -> tuple[Vector3, Vector3]:
    """Where a cylinder's axis starts and ends, in the greenhouse's frame."""
    assert isinstance(fixture.shape, Cylinder)
    return (
        fixture.transform.apply(Vector3(x=0.0, y=0.0, z=0.0)),
        fixture.transform.apply(Vector3(x=0.0, y=0.0, z=fixture.shape.height)),
    )


def test_a_box_stands_on_its_base_at_its_size() -> None:
    cabinet = _only(
        BoxPrimitive(
            fixture_id="cabinet",
            base=Vector3(x=2.0, y=3.0, z=0.0),
            size_x=0.6,
            size_y=1.2,
            size_z=1.8,
        ).fixtures()
    )

    assert cabinet.shape == Box(size_x=0.6, size_y=1.2, size_z=1.8)
    low, high = cabinet.bounds()
    assert _close(low, (1.7, 2.4, 0.0))
    assert _close(high, (2.3, 3.6, 1.8))


def test_a_box_turns_about_the_vertical_by_its_heading() -> None:
    turned = _only(
        BoxPrimitive(
            fixture_id="cabinet",
            base=Vector3(x=2.0, y=3.0, z=0.0),
            size_x=0.6,
            size_y=1.2,
            size_z=1.8,
            heading=math.pi / 2,
        ).fixtures()
    )

    low, high = turned.bounds()
    assert _close(low, (1.4, 2.7, 0.0))
    assert _close(high, (2.6, 3.3, 1.8))


def test_a_cylinder_stands_upright_on_its_base() -> None:
    tank = _only(
        CylinderPrimitive(
            fixture_id="tank", base=Vector3(x=1.0, y=1.0, z=0.0), radius=0.6, height=1.5
        ).fixtures()
    )

    start, end = _axis(tank)
    assert _close(start, (1.0, 1.0, 0.0))
    assert _close(end, (1.0, 1.0, 1.5))
    assert tank.shape == Cylinder(radius=0.6, height=1.5)


@pytest.mark.parametrize(
    "end",
    [
        Vector3(x=9.0, y=1.0, z=0.3),  # along the length
        Vector3(x=1.0, y=5.0, z=0.3),  # across it
        Vector3(x=4.0, y=5.0, z=2.3),  # rising at a slant
        Vector3(x=1.0, y=1.0, z=3.3),  # straight up
        Vector3(x=1.0, y=1.0, z=-0.2),  # straight down
    ],
)
def test_a_pipe_runs_from_its_start_to_its_end(end: Vector3) -> None:
    start = Vector3(x=1.0, y=1.0, z=0.3)
    pipe = _only(PipePrimitive(fixture_id="pipe", start=start, end=end, radius=0.0255).fixtures())

    from_, to = _axis(pipe)
    assert _close(from_, (start.x, start.y, start.z))
    assert _close(to, (end.x, end.y, end.z))
    assert isinstance(pipe.shape, Cylinder)
    assert pipe.shape.radius == 0.0255


def test_a_rails_tubes_lie_a_gauge_apart_either_side_of_its_centre_line() -> None:
    right, left = RailPrimitive(
        fixture_id="rail",
        start=Vector3(x=1.0, y=2.0, z=0.1),
        end=Vector3(x=9.0, y=2.0, z=0.1),
        gauge=0.55,
        tube_radius=0.0255,
    ).fixtures()

    assert (right.fixture_id, left.fixture_id) == ("rail_right", "rail_left")
    # Looking along +x, the right is towards -y.
    assert all(
        _close(a, b)
        for a, b in zip(_axis(right), [(1.0, 1.725, 0.1), (9.0, 1.725, 0.1)], strict=True)
    )
    assert all(
        _close(a, b)
        for a, b in zip(_axis(left), [(1.0, 2.275, 0.1), (9.0, 2.275, 0.1)], strict=True)
    )


def test_a_rail_whose_tubes_would_touch_is_refused() -> None:
    with pytest.raises(ValidationError, match="tubes overlap"):
        RailPrimitive(
            fixture_id="rail",
            start=Vector3(x=1.0, y=2.0, z=0.1),
            end=Vector3(x=9.0, y=2.0, z=0.1),
            gauge=0.05,
            tube_radius=0.0255,
        )


def test_a_tray_lies_along_its_line_and_stays_level_across() -> None:
    # A gutter falling 4 cm over 8 m, to drain.
    start, end = Vector3(x=1.0, y=2.0, z=0.54), Vector3(x=9.0, y=2.0, z=0.5)
    gutter = _only(
        TrayPrimitive(fixture_id="gutter", start=start, end=end, width=0.3, depth=0.12).fixtures()
    )

    assert isinstance(gutter.shape, Box)
    assert math.isclose(gutter.shape.size_x, math.hypot(8.0, 0.04))
    assert (gutter.shape.size_y, gutter.shape.size_z) == (0.3, 0.12)
    half = gutter.shape.size_x / 2
    bottom_start = gutter.transform.apply(Vector3(x=-half, y=0.0, z=0.0))
    bottom_end = gutter.transform.apply(Vector3(x=half, y=0.0, z=0.0))
    assert _close(bottom_start, (1.0, 2.0, 0.54))
    assert _close(bottom_end, (9.0, 2.0, 0.5))
    across = gutter.transform.rotation.rotate(Vector3(x=0.0, y=1.0, z=0.0))
    assert math.isclose(across.z, 0.0, abs_tol=1e-12)


def test_a_walkway_lies_on_the_floor_at_its_width() -> None:
    walkway = _only(
        WalkwayPrimitive(
            fixture_id="aisle", start=Point2(x=0.0, y=4.8), end=Point2(x=12.0, y=4.8), width=1.2
        ).fixtures()
    )

    low, high = walkway.bounds()
    assert _close(low, (0.0, 4.2, 0.0))
    assert _close(high, (12.0, 5.4, WALKWAY_THICKNESS_M))


@pytest.mark.parametrize(
    ("primitive", "size"),
    [
        (PipePrimitive, {"radius": 0.1}),
        (TrayPrimitive, {"width": 0.1, "depth": 0.1}),
    ],
)
def test_a_line_without_length_is_refused(
    primitive: type[PipePrimitive | TrayPrimitive], size: dict[str, float]
) -> None:
    point = Vector3(x=1.0, y=1.0, z=1.0)
    with pytest.raises(ValidationError, match="same point"):
        primitive.model_validate({"fixture_id": "x", "start": point, "end": point, **size})


def test_a_description_with_a_field_it_does_not_have_is_refused() -> None:
    """A typo in a layout file is an error, not a silently ignored line."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PipePrimitive.model_validate(
            {
                "fixture_id": "x",
                "start": Vector3(x=0.0, y=0.0, z=0.3),
                "end": Vector3(x=1.0, y=0.0, z=0.3),
                "radius": 0.03,
                "radious": 0.03,
            }
        )


def test_each_kind_brings_its_own_material_and_obstructions() -> None:
    pipe = _only(
        PipePrimitive(
            fixture_id="pipe",
            start=Vector3(x=0.0, y=0.0, z=0.3),
            end=Vector3(x=1.0, y=0.0, z=0.3),
            radius=0.0255,
        ).fixtures()
    )
    walkway = _only(
        WalkwayPrimitive(
            fixture_id="aisle", start=Point2(x=0.0, y=1.0), end=Point2(x=5.0, y=1.0), width=1.0
        ).fixtures()
    )

    assert pipe.material == DEFAULT_MATERIALS[FixtureKind.PIPE] == Material.STEEL
    assert pipe.obstructs == {Obstruction.MOVEMENT, Obstruction.LIGHT}
    assert walkway.material == Material.CONCRETE
    assert walkway.obstructs == frozenset()
    assert set(DEFAULT_MATERIALS) == set(DEFAULT_OBSTRUCTIONS) == set(FixtureKind)


def test_a_description_chooses_its_own_kind_material_and_obstructions() -> None:
    # A raised platform to walk on: a box, but a walkway of aluminium.
    platform = _only(
        BoxPrimitive(
            fixture_id="platform",
            kind=FixtureKind.WALKWAY,
            base=Vector3(x=1.0, y=1.0, z=0.0),
            size_x=2.0,
            size_y=1.0,
            size_z=0.3,
            material=Material.ALUMINIUM,
            obstructs=[Obstruction.LIGHT],
        ).fixtures()
    )

    assert platform.kind == FixtureKind.WALKWAY
    assert platform.material == Material.ALUMINIUM
    assert platform.obstructs == {Obstruction.LIGHT}
