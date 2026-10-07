"""What carries the crop rows: a support along each row, at its height and
size, on legs, with a slab on top, and the planting positions on it."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.layout import FixtureKind, Material
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SceneEntityKind, greenhouse_scene
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.fixtures import Fixture
from greenhouse_sim.world.geometry import Box, Cylinder, Point2, Vector3
from greenhouse_sim.world.layout import Layout, outside_the_greenhouse
from greenhouse_sim.world.rows import BENCH, SLAB_INSET_M, TOMATO_GUTTER, CropRows, RowSupport

# Three rows of eight, 0.5 m apart along each row: 3.5 m from first to last.
ROWS = CropRows(
    origin=Point2(x=2.0, y=1.6),
    rows=3,
    positions_per_row=8,
    plant_pitch=0.5,
    row_spacing=1.6,
    support=TOMATO_GUTTER,
)
HOUSE = Envelope(length=12.0, width=6.4, eave_height=3.0, ridge_height=3.65, spans=2)


def _by_id(rows: CropRows) -> dict[str, Fixture]:
    return {fixture.fixture_id: fixture for fixture in rows.fixtures()}


def _close(actual: Vector3, expected: tuple[float, float, float]) -> bool:
    return all(
        math.isclose(a, e, abs_tol=1e-9)
        for a, e in zip((actual.x, actual.y, actual.z), expected, strict=True)
    )


def test_planting_positions_stand_on_the_slab() -> None:
    heights = [position.point.z for position in ROWS.planting_positions()]

    assert heights == pytest.approx([0.6 + 0.075] * len(heights))
    assert ROWS.model_copy(update={"support": None}).planting_positions()[0].point.z == 0.0


def test_each_row_has_a_support_from_before_its_first_position_to_beyond_its_last() -> None:
    gutter = _by_id(ROWS)["row_2_support_1"]
    low, high = gutter.bounds()

    assert gutter.kind == FixtureKind.CROP_GUTTER
    assert gutter.material == Material.STEEL
    assert isinstance(gutter.shape, Box)
    assert (gutter.shape.size_x, gutter.shape.size_y, gutter.shape.size_z) == pytest.approx(
        (3.5 + 2 * 0.25, 0.3, 0.12)
    )
    assert _close(low, (1.75, 3.2 - 0.15, 0.6 - 0.12))
    assert _close(high, (5.75, 3.2 + 0.15, 0.6))


def test_a_supports_legs_stand_evenly_from_end_to_end_up_to_its_underside() -> None:
    fixtures = _by_id(ROWS)
    legs = [fixtures[f"row_1_support_1_leg_{leg}"] for leg in (1, 2, 3)]

    # 4 m of gutter, legs at most 2 m apart: three legs, the end ones flush
    # with the gutter's ends.
    radius = TOMATO_GUTTER.leg_radius
    assert "row_1_support_1_leg_4" not in fixtures
    assert [leg.transform.position.x for leg in legs] == pytest.approx(
        [1.75 + radius, 3.75, 5.75 - radius]
    )
    for leg in legs:
        assert leg.kind == FixtureKind.CROP_GUTTER
        assert isinstance(leg.shape, Cylinder)
        assert leg.transform.position.z == 0.0
        assert leg.shape.height == pytest.approx(0.6 - 0.12)


@pytest.mark.parametrize(
    ("leg_spacing", "legs"), [(0.5, 9), (1.0, 5), (1.3, 5), (4.0, 2), (9.0, 2)]
)
def test_legs_are_never_further_apart_than_their_spacing(leg_spacing: float, legs: int) -> None:
    support = TOMATO_GUTTER.model_copy(update={"leg_spacing": leg_spacing})
    fixtures = ROWS.model_copy(update={"support": support}).fixtures()
    xs = sorted(
        f.transform.position.x for f in fixtures if f.fixture_id.startswith("row_1_support_1_leg")
    )

    assert len(xs) == legs
    assert max(b - a for a, b in zip(xs, xs[1:], strict=False)) <= leg_spacing + 1e-12


def test_a_hung_support_has_no_legs() -> None:
    hung = ROWS.model_copy(
        update={"support": TOMATO_GUTTER.model_copy(update={"leg_spacing": None})}
    )

    assert not [f for f in hung.fixtures() if "_leg_" in f.fixture_id]


def test_the_slab_lies_on_the_support_short_of_its_ends() -> None:
    slab = _by_id(ROWS)["row_3_slab_1"]
    low, high = slab.bounds()

    assert slab.kind == FixtureKind.SLAB
    assert slab.material == Material.SUBSTRATE
    assert _close(low, (1.75 + SLAB_INSET_M, 4.8 - 0.1, 0.6))
    assert _close(high, (5.75 - SLAB_INSET_M, 4.8 + 0.1, 0.675))


def test_a_support_can_lie_beside_its_row() -> None:
    beside = ROWS.model_copy(update={"support": TOMATO_GUTTER.model_copy(update={"offset": 0.2})})
    low, high = _by_id(beside)["row_1_support_1"].bounds()

    assert (low.y, high.y) == pytest.approx((1.6 + 0.2 - 0.15, 1.6 + 0.2 + 0.15))


def test_a_support_follows_its_rows_heading() -> None:
    # Rows running along +y, following one another towards -x.
    turned = ROWS.model_copy(update={"origin": Point2(x=9.0, y=1.0), "heading": math.pi / 2})
    low, high = _by_id(turned)["row_1_support_1"].bounds()

    assert (low.x, high.x) == pytest.approx((9.0 - 0.15, 9.0 + 0.15))
    assert (low.y, high.y) == pytest.approx((0.75, 4.75))


def test_the_bench_preset_carries_pots_at_bench_height() -> None:
    benches = ROWS.model_copy(update={"support": BENCH})
    bench = _by_id(benches)["row_1_support_1"]

    assert bench.kind == FixtureKind.BENCH
    assert bench.material == Material.ALUMINIUM
    assert not [f for f in benches.fixtures() if f.kind == FixtureKind.SLAB]
    assert {p.point.z for p in benches.planting_positions()} == {0.8}


def test_a_support_too_deep_for_its_height_is_refused() -> None:
    with pytest.raises(ValidationError, match="cannot have its top at"):
        RowSupport(height=0.1, width=0.3, depth=0.12)


def test_a_support_must_fit_inside_the_greenhouse() -> None:
    # The first gutter's overhang reaches through the front wall.
    near_the_wall = ROWS.model_copy(update={"origin": Point2(x=0.1, y=1.6)})

    outside = outside_the_greenhouse(Layout(crop_rows=near_the_wall), HOUSE)

    # Each row's gutter, its first leg and its slab.
    assert sorted(outside) == sorted(
        f"row_{row}_{part}"
        for row in (1, 2, 3)
        for part in ("support_1", "support_1_leg_1", "slab_1")
    )


def test_the_scene_draws_each_part_of_a_support_as_its_kind() -> None:
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(crop_rows=ROWS))
    kinds = {entity.entity_id: entity.kind for entity in scene.entities}

    assert kinds["gh_row_1_support_1"] == SceneEntityKind.CROP_GUTTER
    assert kinds["gh_row_1_support_1_leg_1"] == SceneEntityKind.CROP_GUTTER
    assert kinds["gh_row_1_slab_1"] == SceneEntityKind.SLAB
    benches = greenhouse_scene(
        "gh", HOUSE, layout=Layout(crop_rows=ROWS.model_copy(update={"support": BENCH}))
    )
    assert {e.kind for e in benches.entities if e.entity_id.startswith("gh_row_1_support")} == {
        SceneEntityKind.BENCH
    }


def test_the_compartments_plants_grow_in_tomato_gutters() -> None:
    config = SCENARIO_REGISTRY["tomato_compartment"]
    rows = config.layout.crop_rows

    assert rows is not None
    assert rows.support == TOMATO_GUTTER
    assert len([f for f in config.layout.fixtures() if f.kind == FixtureKind.SLAB]) == 8
