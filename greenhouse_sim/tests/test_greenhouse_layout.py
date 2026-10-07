"""P02's final QA, `greenhouse-layout`, over many layouts: rows of several
pitches, spacings and headings, single or paired, on the floor, on gutters or
on benches, with and without aisles across them and a keep-out volume over
them. In each, the layout fits its greenhouse, the plants' spacing is what was
asked, no position lies in an area kept clear, every supported plant stands
on its support, walkways stay clear, identifiers survive a layout file, and
every fixture is an obstacle to what it obstructs.

The browser side of the walkthrough is `web/e2e/greenhouse-layout.spec.ts`.
"""

import itertools
import math
from typing import NamedTuple

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.layout import FixtureKind, Obstruction, ZoneKind
from greenhouse_sim.scenarios.layout_files import layout_document
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.fixtures import (
    BoxPrimitive,
    PipeRunPrimitive,
    Primitive,
    WalkwayPrimitive,
)
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.layout import WALKWAY_HEADROOM_M, Layout, outside_the_greenhouse
from greenhouse_sim.world.rows import (
    BENCH,
    PIPE_RAIL,
    TOMATO_GUTTER,
    CropRows,
    CropWires,
    RowSupport,
)
from greenhouse_sim.world.zones import Strip, Zone

HOUSES = (
    Envelope(length=24.0, width=9.6, eave_height=4.0, ridge_height=4.65, spans=3, bays=6),
    Envelope(length=48.0, width=19.2, eave_height=5.0, ridge_height=5.8, spans=4, bays=12),
)
HEADINGS = (0.0, math.pi / 2)
PITCHES = (0.4, 0.5)
# Row spacing, and the gap within a pair, for rows in pairs.
SPACINGS = ((1.6, None), (2.0, None), (3.2, 0.8))
SUPPORTS = (None, TOMATO_GUTTER, BENCH)
# Room left at the ends of the rows and beside the outer ones, clear of the
# aisles along the walls.
END_MARGIN_M = 1.75
SIDE_MARGIN_M = 1.8
WIRES_BELOW_THE_EAVES_M = 0.5
AISLE_WIDTH_M = 1.2
KEEP_OUT_HEIGHT_M = 2.0
# Positions are compared with supports' edges to a nanometre: rounding only.
EDGE_M = 1e-9

# What a support or slab is drawn on, in each layout, by the kind of fixture
# the plants stand on.
STANDS_ON = {TOMATO_GUTTER.kind: FixtureKind.SLAB, BENCH.kind: FixtureKind.BENCH}
# What obstructs airflow: everything solid enough to hold back air.
AIRFLOW_KINDS = {FixtureKind.CROP_GUTTER, FixtureKind.BENCH, FixtureKind.SLAB, FixtureKind.OBSTACLE}


def _count(length: float, step: float, pair_gap: float | None = None) -> int:
    """How many rows (or positions) of this step, or pairs of this spacing
    and gap, fit in `length` from the first."""
    if pair_gap is None:
        return math.floor(length / step + 1e-9) + 1
    pairs = math.floor(length / step + 1e-9)
    return 2 * pairs + (2 if pairs * step + pair_gap <= length else 1)


def _layout(
    house: Envelope,
    heading: float,
    pitch: float,
    spacing: tuple[float, float | None],
    support: RowSupport | None,
    aisles: bool,
) -> Layout:
    """Rows filling the house along its length (heading 0) or across it (a
    quarter turn), with, if asked, an aisle along the front and one along the
    right side, an aisle across the middle of the rows, and a keep-out volume
    over the far end of the last row."""
    length, width = house.length, house.width
    row_spacing, pair_gap = spacing
    along, across = (length, width) if heading == 0.0 else (width, length)
    positions = _count(along - 2 * END_MARGIN_M, pitch)
    rows = _count(across - 2 * SIDE_MARGIN_M, row_spacing, pair_gap)
    origin = (
        Point2(x=END_MARGIN_M, y=SIDE_MARGIN_M)
        if heading == 0.0
        else Point2(x=length - SIDE_MARGIN_M, y=END_MARGIN_M)
    )
    crop_rows = CropRows(
        origin=origin,
        heading=heading,
        rows=rows,
        positions_per_row=positions,
        plant_pitch=pitch,
        row_spacing=row_spacing,
        pair_gap=pair_gap,
        support=support,
        rails=PIPE_RAIL,
        wires=CropWires(height=house.eave_height - WIRES_BELOW_THE_EAVES_M),
    )
    placed: list[Primitive] = [
        PipeRunPrimitive(
            fixture_id="heating_pipes",
            start=Vector3(x=1.3, y=0.15, z=0.3),
            end=Vector3(x=length - 0.2, y=0.15, z=0.3),
            radius=0.0255,
            count=3,
            step=Vector3(x=0.0, y=0.0, z=0.15),
        )
    ]
    zones = []
    if aisles:
        half = AISLE_WIDTH_M / 2
        middle = Point2(x=length / 2, y=width / 2)
        across_the_rows = (
            (Point2(x=middle.x, y=0.2), Point2(x=middle.x, y=width - 0.2))
            if heading == 0.0
            else (Point2(x=1.3, y=middle.y), Point2(x=length - 0.2, y=middle.y))
        )
        placed += [
            WalkwayPrimitive(
                fixture_id="front_aisle",
                start=Point2(x=0.1 + half, y=0.2),
                end=Point2(x=0.1 + half, y=width - 0.2),
                width=AISLE_WIDTH_M,
            ),
            WalkwayPrimitive(
                fixture_id="side_aisle",
                start=Point2(x=1.3, y=0.7),
                end=Point2(x=length - 0.2, y=0.7),
                width=0.8,
            ),
            WalkwayPrimitive(
                fixture_id="central_aisle",
                start=across_the_rows[0],
                end=across_the_rows[1],
                width=AISLE_WIDTH_M,
            ),
            BoxPrimitive(
                fixture_id="cabinet",
                base=Vector3(x=length - 0.6, y=width - 0.6, z=0.0),
                size_x=0.6,
                size_y=0.6,
                size_z=1.8,
            ),
        ]
        zones.append(
            Zone(
                zone_id="keep_out",
                kind=ZoneKind.KEEP_OUT,
                area=Strip(
                    start=Point2(x=length - 4.0, y=width - 1.4),
                    end=Point2(x=length - 0.2, y=width - 1.4),
                    width=2.4,
                ),
                height=KEEP_OUT_HEIGHT_M,
            )
        )
    return Layout(crop_rows=crop_rows, placed=placed, zones=zones)


class Case(NamedTuple):
    house: int
    heading: float
    pitch: float
    spacing: tuple[float, float | None]
    support: RowSupport | None
    aisles: bool

    def name(self) -> str:
        spacing, gap = self.spacing
        held = "floor" if self.support is None else self.support.kind.value
        turned = "across" if self.heading else "along"
        paired = f"paired{gap}" if gap else "single"
        open_or_not = "aisles" if self.aisles else "open"
        return f"house{self.house}-{turned}-{self.pitch}-{spacing}{paired}-{held}-{open_or_not}"


CASES = [
    Case(*case)
    for case in itertools.product(
        range(len(HOUSES)), HEADINGS, PITCHES, SPACINGS, SUPPORTS, (False, True)
    )
    # Benches 1.2 m wide do not fit rows 0.8 m apart: refused, below.
    if not (case[4] is BENCH and case[3][1] is not None)
]


# About 20 seconds in all: run by the full checks and CI, not the quick pass.
@pytest.mark.slow
@pytest.mark.parametrize("case", CASES, ids=[case.name() for case in CASES])
def test_a_layout_keeps_its_promises(case: Case) -> None:
    house, pitch, support = HOUSES[case.house], case.pitch, case.support
    layout = _layout(house, case.heading, pitch, case.spacing, support, case.aisles)
    rows = layout.crop_rows
    assert rows is not None
    positions = layout.planting_positions()
    fixtures = layout.fixtures()
    areas = layout.kept_clear()

    # It fits its greenhouse, and has plants to grow.
    assert outside_the_greenhouse(layout, house) == []
    assert positions

    # The spacing asked for: along each row, positions lie their places'
    # multiples of the pitch apart; across, each row lies its offset away.
    for position in positions:
        dx, dy = position.point.x - rows.origin.x, position.point.y - rows.origin.y
        along = dx * rows.along.x + dy * rows.along.y
        across = dx * rows.across.x + dy * rows.across.y
        assert along == pytest.approx((position.index - 1) * pitch, abs=1e-9)
        assert across == pytest.approx(rows.row_offset(position.row), abs=1e-9)

    # No position in an area kept clear; every supported one on its support.
    for position in positions:
        assert not any(area.contains(position.point) for area in areas), position.position_id
    if support is not None:
        kind = STANDS_ON[support.kind]
        tops = [f.bounds() for f in fixtures if f.kind == kind]
        for position in positions:
            x, y, z = position.point.x, position.point.y, position.point.z
            assert any(
                low.x - EDGE_M <= x <= high.x + EDGE_M
                and low.y - EDGE_M <= y <= high.y + EDGE_M
                and z == pytest.approx(high.z)
                for low, high in tops
            ), position.position_id

    # Walkways stay clear of anything in the way below head height.
    in_the_way = [
        fixture.corners()
        for fixture in fixtures
        if Obstruction.MOVEMENT in fixture.obstructs and fixture.bounds()[0].z < WALKWAY_HEADROOM_M
    ]
    for walkway_id, walkway in layout.walkways():
        assert not any(walkway.overlaps(corners) for corners in in_the_way), walkway_id

    # Identifiers are unique, and survive a layout file.
    names = [f.fixture_id for f in fixtures] + [zone.zone_id for zone in layout.zones]
    assert len(set(names)) == len(names)
    document = layout_document(layout)
    again = Layout.model_validate({k: v for k, v in document.items() if k != "$schema"})
    assert again.fixtures() == fixtures
    assert again.planting_positions() == positions

    # Every fixture is an obstacle to what it obstructs, and to nothing else.
    airflow = {f.fixture_id for f in layout.obstructing(Obstruction.AIRFLOW)}
    light = {f.fixture_id for f in layout.obstructing(Obstruction.LIGHT)}
    movement = {f.fixture_id for f in layout.obstructing(Obstruction.MOVEMENT)}
    assert airflow == {f.fixture_id for f in fixtures if f.kind in AIRFLOW_KINDS}
    assert airflow <= light == movement
    nothing = {f.fixture_id for f in fixtures if f.kind in (FixtureKind.WALKWAY, FixtureKind.WIRE)}
    assert not nothing & (airflow | light | movement)


def test_benches_too_wide_for_paired_rows_are_refused() -> None:
    with pytest.raises(ValidationError, match="too close for supports"):
        _layout(HOUSES[0], 0.0, 0.5, (3.2, 0.8), BENCH, aisles=False)


def test_the_grid_holds_hundreds_of_layouts_of_every_kind() -> None:
    held = {case.support for case in CASES}

    assert len(CASES) >= 100
    assert held == set(SUPPORTS)
