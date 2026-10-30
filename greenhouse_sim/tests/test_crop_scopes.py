"""Where an instance of a run's crop grows, and its areas (P14.9, decision
0062): a row of the crop rows, its cultivated area and its floor kept
apart, and every conversion between them explicit and conserved, across
layouts of one density, with paths or paired rows."""

from typing import Any, Final

import pytest

from greenhouse_sim.domain.layout import ZoneKind
from greenhouse_sim.domain.scopes import AreaBasis, ScopeKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.world.geometry import Point2
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import CropRows
from greenhouse_sim.world.scopes import CropScope, converted, row_scopes, scope_plants, total
from greenhouse_sim.world.zones import Strip, Zone


def _rows(layout: Layout) -> CropRows:
    assert layout.crop_rows is not None
    return layout.crop_rows


BOX: Final = SCENARIO_REGISTRY["climate_box"]
ROWS: Final = _rows(BOX.layout)
# A quantity given per m² of a scope's cultivated area, as a crop model of
# that basis would give it: say, grams of fruit.
PER_M2: Final = 250.0


def _with_rows(layout: Layout, **changes: Any) -> Layout:
    """A layout whose crop rows have `changes`, checked as a layout is."""
    assert layout.crop_rows is not None
    rows = layout.crop_rows.model_dump() | changes
    return Layout.model_validate(layout.model_dump() | {"crop_rows": rows})


def _with_a_path_across(layout: Layout) -> Layout:
    """A layout with a service zone across every row, a metre wide, a third
    of the way along them, where no plant stands."""
    rows = layout.crop_rows
    assert rows is not None
    along = rows.row_length / 3
    start = rows.point(1, along, across=-rows.row_spacing)
    end = rows.point(rows.rows, along, across=rows.row_spacing)
    zone = Zone(
        zone_id="path_across",
        kind=ZoneKind.SERVICE,
        area=Strip(start=Point2(x=start.x, y=start.y), end=Point2(x=end.x, y=end.y), width=1.0),
        height=2.0,
    )
    return layout.model_copy(update={"zones": [*layout.zones, zone]})


@pytest.mark.parametrize("scenario_id", list(SCENARIO_REGISTRY))
def test_each_row_is_a_scope_whose_floors_add_up_to_the_houses(scenario_id: str) -> None:
    config = SCENARIO_REGISTRY[scenario_id]
    rows = config.layout.crop_rows
    # Each packaged scenario's rows are evenly spaced.
    assert rows is not None and rows.pair_gap is None
    scopes = row_scopes(config.layout, config.envelope)

    assert [scope.scope_id for scope in scopes] == [f"row_{scope.row}" for scope in scopes]
    assert {scope.kind for scope in scopes} == {ScopeKind.ROW}
    assert sum(scope.floor_m2 for scope in scopes) == pytest.approx(
        config.envelope.length * config.envelope.width, rel=1e-12
    )
    for scope in scopes:
        assert {position.row for position in scope.positions} == {scope.row}
        assert scope.cultivated_m2 == pytest.approx(
            len(scope.positions) * rows.plant_pitch * rows.row_spacing, rel=1e-12
        )
    assert sum(len(scope.positions) for scope in scopes) == len(config.layout.planting_positions())


@pytest.mark.parametrize("scenario_id", list(SCENARIO_REGISTRY))
def test_each_plant_stands_in_the_scope_of_its_planting_positions_row(scenario_id: str) -> None:
    config = SCENARIO_REGISTRY[scenario_id]
    plants = plant_ids(config)
    held = scope_plants(row_scopes(config.layout, config.envelope), plants)

    assert [plant for scope in held.values() for plant in scope] == plants
    rows = {
        plant: training.position.row
        for plant, training in zip(plants, config.layout.trainings(), strict=False)
    }
    for scope_id, scope in held.items():
        assert {f"row_{rows[plant]}" for plant in scope} <= {scope_id}


def test_paired_rows_share_their_pairs_spacing() -> None:
    paired = _with_rows(BOX.layout, row_spacing=2 * ROWS.row_spacing, pair_gap=1.0)
    even = row_scopes(BOX.layout, BOX.envelope)
    pairs = row_scopes(paired, BOX.envelope)

    # Rows evenly spaced, and paired rows twice as far apart from pair to
    # pair: one density, the same ground cultivated.
    assert [scope.cultivated_m2 for scope in pairs] == pytest.approx(
        [scope.cultivated_m2 for scope in even], rel=1e-12
    )
    assert [scope.density(len(scope.positions), AreaBasis.CULTIVATED) for scope in pairs] == (
        pytest.approx([1 / (ROWS.plant_pitch * ROWS.row_spacing)] * len(pairs), rel=1e-12)
    )


def test_a_path_kept_clear_is_no_rows_ground_but_still_the_houses_floor() -> None:
    pathed = _with_a_path_across(BOX.layout)
    before = row_scopes(BOX.layout, BOX.envelope)
    after = row_scopes(pathed, BOX.envelope)

    lost = [len(a.positions) - len(b.positions) for a, b in zip(before, after, strict=True)]
    assert all(count > 0 for count in lost)
    assert [b.cultivated_m2 for b in after] == pytest.approx(
        [
            a.cultivated_m2 - count * ROWS.plant_pitch * ROWS.row_spacing
            for a, count in zip(before, lost, strict=True)
        ],
        rel=1e-12,
    )
    assert sum(scope.floor_m2 for scope in after) == pytest.approx(
        sum(scope.floor_m2 for scope in before), rel=1e-12
    )


def _totals(scopes: list[CropScope], basis: AreaBasis) -> float:
    """What a crop of `PER_M2` per m² of cultivated area holds in all, its
    quantity converted to `basis` scope by scope and summed back."""
    return sum(
        total(converted(PER_M2, scope, AreaBasis.CULTIVATED, basis), scope, basis)
        for scope in scopes
    )


@pytest.mark.parametrize(
    "layout",
    [
        BOX.layout,
        _with_rows(BOX.layout, row_spacing=2 * ROWS.row_spacing, pair_gap=1.0),
        _with_a_path_across(BOX.layout),
    ],
    ids=["even", "paired", "with_a_path"],
)
def test_a_quantity_converted_between_areas_keeps_its_total(layout: Layout) -> None:
    scopes = row_scopes(layout, BOX.envelope)
    cultivated = sum(scope.cultivated_m2 for scope in scopes)

    for basis in AreaBasis:
        assert _totals(scopes, basis) == pytest.approx(PER_M2 * cultivated, rel=1e-12)
    for scope in scopes:
        there = converted(PER_M2, scope, AreaBasis.CULTIVATED, AreaBasis.FLOOR)
        assert converted(there, scope, AreaBasis.FLOOR, AreaBasis.CULTIVATED) == pytest.approx(
            PER_M2, rel=1e-12
        )
        # The floor is the larger: a quantity per m² of it is the smaller.
        assert there < PER_M2


def test_one_density_on_two_layouts_holds_the_same_crop() -> None:
    """The same plants at one density per m² cultivated, on rows evenly
    spaced and on paired rows: the same ground, the same total."""
    even = row_scopes(BOX.layout, BOX.envelope)
    paired = row_scopes(
        _with_rows(BOX.layout, row_spacing=2 * ROWS.row_spacing, pair_gap=1.0), BOX.envelope
    )

    assert _totals(even, AreaBasis.CULTIVATED) == pytest.approx(
        _totals(paired, AreaBasis.CULTIVATED), rel=1e-12
    )
    assert _totals(even, AreaBasis.FLOOR) == pytest.approx(
        _totals(paired, AreaBasis.FLOOR), rel=1e-12
    )
