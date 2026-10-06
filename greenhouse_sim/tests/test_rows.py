"""Crop rows and planting positions: as many as configured, at exactly the
configured pitch and spacing, with identifiers that say where they are."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import (
    PLANTING_MARKER_RADIUS_M,
    SceneEntityKind,
    greenhouse_scene,
)
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Point2, Quaternion, Transform, Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import CropRows

ROWS = CropRows(
    origin=Point2(x=1.5, y=0.8),
    rows=4,
    positions_per_row=6,
    plant_pitch=0.5,
    row_spacing=1.6,
)
HOUSE = Envelope(length=12.0, width=9.6, eave_height=4.0, ridge_height=4.8, spans=3)


def test_there_is_a_position_for_every_row_and_place_along_it() -> None:
    positions = ROWS.planting_positions()

    assert len(positions) == 4 * 6
    assert [p.position_id for p in positions[:7]] == [
        *(f"row_1_position_{i}" for i in range(1, 7)),
        "row_2_position_1",
    ]
    assert len({p.position_id for p in positions}) == len(positions)


def test_positions_follow_the_pitch_along_a_row_and_the_spacing_across() -> None:
    positions = ROWS.planting_positions()
    first_row = [p.point for p in positions if p.row == 1]
    first_of_each_row = [p.point for p in positions if p.index == 1]

    assert [point.x for point in first_row] == [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    assert {point.y for point in first_row} == {0.8}
    assert [point.y for point in first_of_each_row] == pytest.approx([0.8, 2.4, 4.0, 5.6])
    assert {point.z for point in first_row} == {0.0}


def test_no_position_drifts_along_a_long_row() -> None:
    """Each position is its own multiple of the pitch: summing a pitch of 0.1 m
    a thousand times would drift away from it."""
    long_row = ROWS.model_copy(update={"rows": 1, "positions_per_row": 1000, "plant_pitch": 0.1})

    for position in long_row.planting_positions():
        assert position.point.x == 1.5 + (position.index - 1) * 0.1


def test_rows_run_along_their_heading_and_follow_one_another_to_its_left() -> None:
    # Turned a quarter, rows run along +y, and follow one another towards -x.
    across = ROWS.model_copy(update={"origin": Point2(x=9.0, y=1.0), "heading": math.pi / 2})
    positions = across.planting_positions()
    second = next(p for p in positions if p.row == 1 and p.index == 2)
    next_row = next(p for p in positions if p.row == 2 and p.index == 1)

    assert (second.point.x, second.point.y) == pytest.approx((9.0, 1.5))
    assert (next_row.point.x, next_row.point.y) == pytest.approx((7.4, 1.0))


def test_paired_rows_lie_a_gap_apart_within_a_pair_and_a_spacing_from_the_next() -> None:
    paired = ROWS.model_copy(update={"rows": 5, "pair_gap": 0.6})
    first_of_each_row = [p.point.y for p in paired.planting_positions() if p.index == 1]

    # The fifth row starts a third pair, on its own.
    assert first_of_each_row == pytest.approx([0.8, 1.4, 2.4, 3.0, 4.0])


def test_a_pair_that_would_reach_the_next_is_refused() -> None:
    with pytest.raises(ValidationError, match="reach the next pair"):
        CropRows.model_validate({**ROWS.model_dump(), "pair_gap": 1.6})


def test_a_layout_without_rows_has_no_planting_positions() -> None:
    assert Layout().planting_positions() == []


def test_a_scenario_needs_a_planting_position_for_every_plant() -> None:
    config = SCENARIO_REGISTRY["gh_001"]
    too_few = Layout(crop_rows=ROWS.model_copy(update={"rows": 3, "positions_per_row": 13}))

    with pytest.raises(ValidationError, match="40 plants, but only 39 planting positions"):
        config.model_validate({**config.model_dump(), "layout": too_few})


def test_a_scenario_refuses_planting_positions_outside_its_greenhouse() -> None:
    config = SCENARIO_REGISTRY["gh_001"]
    # Ten rows 1.6 m apart from y = 2.4 reach far beyond its 9.6 m width.
    wide = Layout(crop_rows=ROWS.model_copy(update={"origin": Point2(x=1.5, y=2.4), "rows": 10}))

    with pytest.raises(
        ValidationError,
        match="outside the greenhouse: row_6_position_1, row_6_position_2, row_6_position_3 "
        "and 27 more",
    ):
        config.model_validate({**config.model_dump(), "layout": wide})


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_every_scenario_has_its_rows_and_columns_of_planting_positions(scenario_id: str) -> None:
    config = SCENARIO_REGISTRY[scenario_id]
    rows = config.layout.crop_rows

    assert rows is not None
    assert (rows.rows, rows.positions_per_row) == (config.rows, config.columns)


def test_the_scene_marks_each_planting_position_with_its_row_and_place() -> None:
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(crop_rows=ROWS))
    markers = [e for e in scene.entities if e.kind == SceneEntityKind.PLANTING_POSITION]
    marker = next(e for e in markers if e.entity_id == "gh_row_2_position_3")

    assert len(markers) == 4 * 6
    position = marker.transform.position
    assert (position.x, position.y, position.z) == pytest.approx((2.5, 2.4, 0.0))
    assert marker.properties == {"row": 2, "position_in_row": 3}
    assert marker.label == "row 2 position 3"
    assert marker.shape.shape == "cylinder"
    assert marker.shape.radius == PLANTING_MARKER_RADIUS_M


def test_the_scene_places_planting_positions_with_the_greenhouse() -> None:
    quarter_turn = Quaternion(w=2**-0.5, x=0.0, y=0.0, z=2**-0.5)
    placed = HOUSE.model_copy(
        update={"origin": Transform(position=Vector3(x=100.0, y=0.0, z=0.0), rotation=quarter_turn)}
    )
    scene = greenhouse_scene("gh", placed, layout=Layout(crop_rows=ROWS))
    first = next(e for e in scene.entities if e.entity_id == "gh_row_1_position_1")

    # Turned a quarter, the greenhouse's x runs along the world's y.
    assert (first.transform.position.x, first.transform.position.y) == pytest.approx((99.2, 1.5))
