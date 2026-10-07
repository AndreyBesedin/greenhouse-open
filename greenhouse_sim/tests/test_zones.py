"""Walkways, service zones and keep-out volumes: no planting position inside
them, supports stopping short of them, and walkways clear of anything that
obstructs movement."""

import itertools
import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.layout import FixtureKind, Obstruction, ZoneKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import KEEP_OUT_COLOR, SceneEntityKind, greenhouse_scene
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.fixtures import BoxPrimitive, PipePrimitive, WalkwayPrimitive
from greenhouse_sim.world.geometry import Box, Point2, Vector3
from greenhouse_sim.world.layout import Layout, outside_the_greenhouse
from greenhouse_sim.world.rows import SLAB_INSET_M, TOMATO_GUTTER, CropRows
from greenhouse_sim.world.zones import Strip, Zone

HOUSE = Envelope(length=16.0, width=9.6, eave_height=4.0, ridge_height=4.65, spans=3)
# Five rows of 26 along the length, from x = 1.75 to 14.25 m.
ROWS = CropRows(
    origin=Point2(x=1.75, y=2.0),
    rows=5,
    positions_per_row=26,
    plant_pitch=0.5,
    row_spacing=1.6,
    support=TOMATO_GUTTER,
)


def _aisle(x: float, width: float = 1.2, fixture_id: str = "central_aisle") -> WalkwayPrimitive:
    """An aisle across the house at `x`."""
    return WalkwayPrimitive(
        fixture_id=fixture_id, start=Point2(x=x, y=0.2), end=Point2(x=x, y=9.4), width=width
    )


def _keep_out(x_from: float, x_to: float, y_from: float, y_to: float) -> Zone:
    middle = (y_from + y_to) / 2
    return Zone(
        zone_id="keep_out",
        kind=ZoneKind.KEEP_OUT,
        area=Strip(
            start=Point2(x=x_from, y=middle), end=Point2(x=x_to, y=middle), width=y_to - y_from
        ),
        height=2.0,
    )


def test_a_strip_holds_what_lies_inside_it_but_not_on_its_edge() -> None:
    aisle = Strip(start=Point2(x=8.0, y=0.0), end=Point2(x=8.0, y=9.6), width=1.2)

    assert aisle.contains(Point2(x=8.5, y=4.0))
    assert not aisle.contains(Point2(x=8.6, y=4.0))
    assert not aisle.contains(Point2(x=9.0, y=4.0))
    assert not aisle.contains(Point2(x=8.0, y=9.7))
    corners = {(round(c.x, 9), round(c.y, 9)) for c in aisle.corners()}
    assert corners == {(8.6, 0.0), (8.6, 9.6), (7.4, 9.6), (7.4, 0.0)}


@pytest.mark.parametrize(
    ("start", "direction", "half_width", "expected"),
    [
        # Square across the aisle: a band reaches in only where the line does.
        (Point2(x=0.0, y=4.0), Point2(x=1.0, y=0.0), 0.15, (7.4, 8.6)),
        # Along it, the band's width counts.
        (Point2(x=7.0, y=-5.0), Point2(x=0.0, y=1.0), 0.5, (5.0, 14.6)),
        # Past its end, only the band's edge reaches its corner.
        (Point2(x=0.0, y=9.7), Point2(x=1.0, y=0.0), 0.15, (7.4, 8.6)),
        (Point2(x=0.0, y=9.8), Point2(x=1.0, y=0.0), 0.15, None),
        # Parallel and beside it: never.
        (Point2(x=9.0, y=0.0), Point2(x=0.0, y=1.0), 0.15, None),
    ],
)
def test_a_band_along_a_line_reaches_into_a_strip_where_expected(
    start: Point2, direction: Point2, half_width: float, expected: tuple[float, float] | None
) -> None:
    aisle = Strip(start=Point2(x=8.0, y=0.0), end=Point2(x=8.0, y=9.6), width=1.2)
    crossing = aisle.crossing(start, direction, half_width)

    if expected is None:
        assert crossing is None
    else:
        assert crossing == pytest.approx(expected)


def test_no_planting_position_lies_in_a_walkway_and_the_others_keep_their_names() -> None:
    layout = Layout(crop_rows=ROWS, placed=[_aisle(8.0)])
    first_row = [p for p in layout.planting_positions() if p.row == 1]

    # 7.75 and 8.25 m lie in the aisle, from 7.4 to 8.6 m.
    assert [p.index for p in first_row] == [*range(1, 13), *range(15, 27)]
    assert {p.position_id for p in first_row} >= {"row_1_position_12", "row_1_position_15"}


def test_no_planting_position_lies_in_a_service_zone_or_keep_out_volume() -> None:
    service = Zone(
        zone_id="service",
        kind=ZoneKind.SERVICE,
        area=Strip(start=Point2(x=1.0, y=1.0), end=Point2(x=4.0, y=1.0), width=2.4),
        height=2.0,
    )
    layout = Layout(crop_rows=ROWS, zones=[service, _keep_out(12.0, 15.0, 7.0, 9.0)])
    positions = {(p.row, p.index) for p in layout.planting_positions()}

    # The service zone covers row 1 (y = 2.0) up to x = 4.0, and its gutter
    # must reach 0.1 m beyond its first plant; the keep-out volume covers row
    # 5 (y = 8.4) from x = 12.0, and row 4 (y = 6.8) not at all.
    assert (1, 5) not in positions and (1, 6) in positions
    assert (5, 22) not in positions and (5, 21) in positions
    assert (4, 26) in positions


def test_a_row_crossed_by_an_aisle_gets_a_support_on_each_side_stopping_at_it() -> None:
    fixtures = {f.fixture_id: f for f in Layout(crop_rows=ROWS, placed=[_aisle(8.0)]).fixtures()}
    before, after = fixtures["row_1_support_1"], fixtures["row_1_support_2"]

    assert "row_1_support_3" not in fixtures
    # Each overhangs its run by 0.25 m, unless the aisle comes first.
    assert (before.bounds()[0].x, before.bounds()[1].x) == pytest.approx((1.5, 7.4))
    assert (after.bounds()[0].x, after.bounds()[1].x) == pytest.approx((8.6, 14.5))
    slab = fixtures["row_1_slab_1"]
    # The last plant before the aisle, at 7.25 m, still stands on its slab.
    assert slab.bounds()[1].x == pytest.approx(7.4 - SLAB_INSET_M)
    assert slab.bounds()[1].x > 7.25


def test_a_support_stops_short_of_a_keep_out_volume() -> None:
    layout = Layout(crop_rows=ROWS, zones=[_keep_out(12.0, 15.0, 7.0, 9.0)])
    fixtures = {f.fixture_id: f for f in layout.fixtures()}

    assert fixtures["row_5_support_1"].bounds()[1].x == pytest.approx(12.0)
    assert fixtures["row_3_support_1"].bounds()[1].x == pytest.approx(14.5)


def test_a_fixture_that_obstructs_movement_on_a_walkway_is_refused() -> None:
    cabinet = BoxPrimitive(
        fixture_id="cabinet", base=Vector3(x=8.0, y=5.0, z=0.0), size_x=0.6, size_y=0.6, size_z=1.8
    )
    with pytest.raises(ValidationError, match="cabinet stands on the walkway central_aisle"):
        Layout(placed=[_aisle(8.0), cabinet])
    # Overhead, a pipe still obstructs movement under it: refused too.
    pipe = PipePrimitive(
        fixture_id="pipe",
        start=Vector3(x=7.0, y=3.0, z=0.3),
        end=Vector3(x=9.0, y=3.0, z=0.3),
        radius=0.03,
    )
    with pytest.raises(ValidationError, match="pipe stands on the walkway"):
        Layout(placed=[_aisle(8.0), pipe])
    # One that obstructs only light may cross it.
    shade = pipe.model_copy(update={"obstructs": [Obstruction.LIGHT]})
    assert Layout(placed=[_aisle(8.0), shade]).fixtures()


def test_identifiers_are_shared_by_no_fixture_and_zone() -> None:
    with pytest.raises(ValidationError, match="share an identifier: keep_out"):
        Layout(placed=[_aisle(8.0, fixture_id="keep_out")], zones=[_keep_out(12.0, 15.0, 7.0, 9.0)])


def test_a_zone_must_fit_inside_the_greenhouse() -> None:
    too_high = _keep_out(12.0, 15.0, 7.0, 9.0).model_copy(update={"height": 5.0})

    assert outside_the_greenhouse(Layout(zones=[too_high]), HOUSE) == ["keep_out"]


@pytest.mark.parametrize(
    ("aisle_x", "aisle_width", "keep_out"),
    list(
        itertools.product(
            [3.0, 5.45, 8.0, 10.6, 13.9],
            [0.8, 1.2, 2.5],
            [None, (11.0, 15.9, 5.5, 9.4), (1.2, 4.3, 0.2, 3.7), (6.0, 6.9, 0.2, 9.4)],
        )
    ),
)
def test_planting_and_supports_keep_clear_of_aisles_and_zones(
    aisle_x: float, aisle_width: float, keep_out: tuple[float, float, float, float] | None
) -> None:
    """Over a grid of aisles and keep-out volumes: no position inside any of
    them, every support, leg and slab clear of them, and every position on
    its row's slab."""
    zones = [] if keep_out is None else [_keep_out(*keep_out)]
    layout = Layout(crop_rows=ROWS, placed=[_aisle(aisle_x, aisle_width)], zones=zones)
    areas = layout.kept_clear()
    positions = layout.planting_positions()
    supports = [f for f in layout.fixtures() if f.fixture_id.startswith("row_")]

    for position in positions:
        assert not any(area.contains(position.point) for area in areas), position.position_id
    for fixture in supports:
        assert not any(area.overlaps(fixture.corners()) for area in areas), fixture.fixture_id
    slabs = [f for f in supports if f.kind == FixtureKind.SLAB]
    for position in positions:
        assert any(
            slab.bounds()[0].x <= position.point.x <= slab.bounds()[1].x
            and slab.bounds()[0].y <= position.point.y <= slab.bounds()[1].y
            for slab in slabs
        ), position.position_id


def test_the_scene_draws_zones_as_the_volumes_they_keep() -> None:
    keep_out = _keep_out(12.0, 15.0, 7.0, 9.0)
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(zones=[keep_out]))
    entity = next(e for e in scene.entities if e.entity_id == "gh_keep_out")

    assert entity.kind == SceneEntityKind.KEEP_OUT
    assert entity.color == KEEP_OUT_COLOR
    assert entity.shape == Box(size_x=3.0, size_y=2.0, size_z=2.0)
    assert entity.transform.position == Vector3(x=13.5, y=8.0, z=0.0)


def test_a_turned_zone_is_drawn_turned() -> None:
    across = Zone(
        zone_id="across",
        kind=ZoneKind.SERVICE,
        area=Strip(start=Point2(x=8.0, y=1.0), end=Point2(x=8.0, y=5.0), width=1.0),
        height=2.0,
    )
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(zones=[across]))
    entity = next(e for e in scene.entities if e.entity_id == "gh_across")
    x_axis = entity.transform.rotation.rotate(Vector3(x=1.0, y=0.0, z=0.0))

    assert entity.kind == SceneEntityKind.SERVICE_ZONE
    assert (x_axis.x, x_axis.y) == pytest.approx((0.0, 1.0))
    assert math.isclose(entity.transform.position.y, 3.0)


def test_the_compartment_keeps_its_paths_and_zones_clear_and_plants_every_position() -> None:
    config = SCENARIO_REGISTRY["tomato_compartment"]
    layout = config.layout

    assert len(layout.planting_positions()) == config.rows * config.columns
    assert [walkway_id for walkway_id, _ in layout.walkways()] == [
        "main_path",
        "side_path_right",
        "side_path_left",
    ]
    assert {zone.kind for zone in layout.zones} == {ZoneKind.SERVICE, ZoneKind.KEEP_OUT}
