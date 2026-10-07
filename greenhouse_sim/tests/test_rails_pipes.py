"""Rails between the rows, crop wires above them, and runs of repeated pipes:
where the configuration puts them, clear of the areas kept clear, and
overhead where they cross a walkway."""

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.layout import FixtureKind, Obstruction
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SceneEntityKind, greenhouse_scene
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.fixtures import Fixture, PipePrimitive, PipeRunPrimitive, WalkwayPrimitive
from greenhouse_sim.world.geometry import Cylinder, Point2, Vector3
from greenhouse_sim.world.layout import WALKWAY_HEADROOM_M, Layout
from greenhouse_sim.world.rows import (
    PIPE_RAIL,
    ROW_OVERHANG_M,
    SHORTEST_RAIL_M,
    TOMATO_GUTTER,
    CropRows,
    CropWires,
)

HOUSE = Envelope(length=16.0, width=9.6, eave_height=4.0, ridge_height=4.65, spans=3)
# Five rows of 26 along the length, 1.6 m apart, on gutters 0.25 m beyond
# their ends: from x = 1.5 to 14.5 m.
ROWS = CropRows(
    origin=Point2(x=1.75, y=2.0),
    rows=5,
    positions_per_row=26,
    plant_pitch=0.5,
    row_spacing=1.6,
    support=TOMATO_GUTTER,
    rails=PIPE_RAIL,
    wires=CropWires(height=3.5),
)
CENTRAL_AISLE = WalkwayPrimitive(
    fixture_id="central_aisle", start=Point2(x=8.0, y=0.2), end=Point2(x=8.0, y=9.4), width=1.2
)


def _by_id(fixtures: list[Fixture]) -> dict[str, Fixture]:
    return {fixture.fixture_id: fixture for fixture in fixtures}


def _axis(fixture: Fixture) -> tuple[Vector3, Vector3]:
    assert isinstance(fixture.shape, Cylinder)
    return (
        fixture.transform.apply(Vector3(x=0.0, y=0.0, z=0.0)),
        fixture.transform.apply(Vector3(x=0.0, y=0.0, z=fixture.shape.height)),
    )


def test_a_rail_runs_along_the_middle_of_each_path_between_rows() -> None:
    fixtures = _by_id(ROWS.fixtures())
    tubes = sorted(name for name in fixtures if name.startswith("rail_"))

    # Four paths between five rows, each a rail of two tubes.
    assert tubes == [f"rail_{gap}_1_{side}" for gap in (1, 2, 3, 4) for side in ("left", "right")]
    start, end = _axis(fixtures["rail_2_1_right"])
    # The path between rows 2 (y = 3.6) and 3 (y = 5.2); its right is towards -y.
    assert (start.x, start.y, start.z) == pytest.approx((1.5, 4.4 - PIPE_RAIL.gauge / 2, 0.1))
    assert (end.x, end.y, end.z) == pytest.approx((14.5, 4.4 - PIPE_RAIL.gauge / 2, 0.1))
    assert fixtures["rail_2_1_right"].kind == FixtureKind.RAIL


def test_a_path_too_narrow_for_a_rail_gets_none() -> None:
    # Rows in pairs 0.8 m apart: with 0.3 m gutters, 0.5 m is left within a
    # pair, too little for a rail 0.6 m across; between pairs there is room.
    paired = ROWS.model_copy(update={"pair_gap": 0.8, "row_spacing": 3.2, "rows": 4})
    rails = {
        name.rsplit("_", 2)[0] for name in _by_id(paired.fixtures()) if name.startswith("rail")
    }

    assert rails == {"rail_2"}


def test_a_rail_is_laid_in_pieces_either_side_of_an_aisle() -> None:
    fixtures = _by_id(Layout(crop_rows=ROWS, placed=[CENTRAL_AISLE]).fixtures())
    first, second = _axis(fixtures["rail_1_1_left"]), _axis(fixtures["rail_1_2_left"])
    # The band of a rail, its gauge and tubes, reaches the aisle's edge at 7.4
    # and 8.6 m, where the rail stops.
    assert (first[0].x, first[1].x) == pytest.approx((1.5, 7.4))
    assert (second[0].x, second[1].x) == pytest.approx((8.6, 14.5))
    assert "rail_1_3_left" not in fixtures


def test_a_piece_of_rail_too_short_to_ride_on_is_not_laid() -> None:
    # An aisle from 1.9 to 3.1 m leaves 0.4 m of rail before it, from 1.5 m:
    # too short, so the rail starts beyond the aisle.
    near_the_end = CENTRAL_AISLE.model_copy(
        update={"start": Point2(x=2.5, y=0.2), "end": Point2(x=2.5, y=9.4)}
    )
    fixtures = _by_id(Layout(crop_rows=ROWS, placed=[near_the_end]).fixtures())
    first = _axis(fixtures["rail_1_1_left"])

    assert 1.9 - 1.5 < SHORTEST_RAIL_M
    assert first[0].x == pytest.approx(3.1)
    assert "rail_1_2_left" not in fixtures


def test_a_crop_wire_hangs_above_each_run_as_long_as_its_gutter() -> None:
    fixtures = _by_id(Layout(crop_rows=ROWS, placed=[CENTRAL_AISLE]).fixtures())
    wire, gutter = fixtures["row_3_wire_2"], fixtures["row_3_support_2"]
    start, end = _axis(wire)

    assert wire.kind == FixtureKind.WIRE
    assert wire.obstructs == frozenset()
    assert (start.y, start.z, end.z) == pytest.approx((5.2, 3.5, 3.5))
    assert (start.x, end.x) == pytest.approx((gutter.bounds()[0].x, gutter.bounds()[1].x))


def test_without_a_support_a_wire_reaches_beyond_its_row_as_a_gutter_would() -> None:
    soil = ROWS.model_copy(update={"support": None, "rails": None})
    start, end = _axis(_by_id(soil.fixtures())["row_1_wire_1"])

    assert (start.x, end.x) == pytest.approx((1.75 - ROW_OVERHANG_M, 14.25 + ROW_OVERHANG_M))


def test_a_pipe_run_repeats_its_pipe_a_step_apart() -> None:
    run = PipeRunPrimitive(
        fixture_id="heating",
        start=Vector3(x=1.0, y=0.2, z=0.3),
        end=Vector3(x=15.0, y=0.2, z=0.3),
        radius=0.0255,
        count=4,
        step=Vector3(x=0.0, y=0.0, z=0.15),
    )
    pipes = run.fixtures()

    assert [pipe.fixture_id for pipe in pipes] == [f"heating_{n}" for n in (1, 2, 3, 4)]
    for number, pipe in enumerate(pipes):
        start, end = _axis(pipe)
        assert (start.x, start.y, start.z) == pytest.approx((1.0, 0.2, 0.3 + 0.15 * number))
        assert end.x == pytest.approx(15.0)
        assert pipe.kind == FixtureKind.PIPE


def test_pipes_of_a_run_that_would_touch_are_refused() -> None:
    with pytest.raises(ValidationError, match="pipes overlap"):
        PipeRunPrimitive(
            fixture_id="heating",
            start=Vector3(x=1.0, y=0.2, z=0.3),
            end=Vector3(x=15.0, y=0.2, z=0.3),
            radius=0.0255,
            count=2,
            step=Vector3(x=0.0, y=0.0, z=0.04),
        )


def test_a_pipe_may_cross_a_walkway_overhead_but_not_below_head_height() -> None:
    def across(height: float) -> PipePrimitive:
        return PipePrimitive(
            fixture_id="pipe",
            start=Vector3(x=7.0, y=3.0, z=height),
            end=Vector3(x=9.0, y=3.0, z=height),
            radius=0.03,
        )

    assert Layout(placed=[CENTRAL_AISLE, across(WALKWAY_HEADROOM_M + 0.1)]).fixtures()
    with pytest.raises(ValidationError, match="pipe stands on the walkway"):
        Layout(placed=[CENTRAL_AISLE, across(WALKWAY_HEADROOM_M - 0.1)])


def test_the_scene_draws_wires_rails_and_pipes_as_their_kinds() -> None:
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(crop_rows=ROWS))
    kinds = {entity.entity_id: entity.kind for entity in scene.entities}

    assert kinds["gh_row_1_wire_1"] == SceneEntityKind.WIRE
    assert kinds["gh_rail_1_1_left"] == SceneEntityKind.RAIL
    # All of them are cylinders, which the viewer draws in instanced batches.
    assert {
        entity.shape.shape
        for entity in scene.entities
        if entity.kind in (SceneEntityKind.WIRE, SceneEntityKind.RAIL)
    } == {"cylinder"}


def test_gh_001_has_rails_between_its_rows_wires_above_them_and_heating_pipes() -> None:
    fixtures = SCENARIO_REGISTRY["gh_001"].layout.fixtures()
    count = {kind: sum(f.kind == kind for f in fixtures) for kind in FixtureKind}

    assert count[FixtureKind.RAIL] == 3 * 2
    assert count[FixtureKind.WIRE] == 4
    assert count[FixtureKind.PIPE] == 2 * 4
    assert all(Obstruction.MOVEMENT in f.obstructs for f in fixtures if f.kind == FixtureKind.RAIL)
