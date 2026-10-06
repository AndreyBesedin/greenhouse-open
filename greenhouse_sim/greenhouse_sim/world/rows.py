"""Crop rows, and the planting positions along them.

Rows are straight and parallel, given in the greenhouse's frame. The first
row's first planting position stands at the rows' origin; each row runs
along the rows' heading, and the rows follow one another to its left (seen
from above), so with a heading of 0 rows run along the greenhouse's length
and follow one another across its width. Rows may come in pairs: the two
rows of a pair lie closer together than one pair does to the next.

Each planting position has an identifier from its row and its place along
that row, `row_<r>_position_<p>`, both counted from 1. Every position is its
own multiple of the pitch and spacing from the origin, never a running sum,
so none drifts along a long row or across many rows.

Rows may stand on a support: a generic structure along each row, such as a
crop gutter or a bench, with a top at a height, legs down to the floor, and
optionally a substrate slab along the top. The planting positions then stand
on the slab, or on the top. `TOMATO_GUTTER` and `BENCH` are presets.

Areas kept clear (`greenhouse_sim.world.zones`) take no planting positions:
a position inside one is left out, and the others keep their identifiers.
On a support, a position is also left out when the support could not reach
`LEAST_SUPPORT_REACH_M` beyond it without reaching into the area. A row's
support runs under each unbroken run of its positions, one support per run,
numbered along the row from 1, and stops short of any kept area it would
otherwise reach into.
"""

import math
from typing import Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from greenhouse_sim.world.fixtures import (
    CylinderPrimitive,
    Fixture,
    FixtureKind,
    Material,
    TrayPrimitive,
)
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.zones import EDGE_TOLERANCE_M, Strip

# A slab stops this short of each end of the support it lies on.
SLAB_INSET_M: Final = 0.05
# A plant on a support needs its support, and the slab on it, to reach this
# far beyond it.
LEAST_SUPPORT_REACH_M: Final = 2 * SLAB_INSET_M


class Slab(BaseModel):
    """Substrate laid along the top of a row's support."""

    model_config = ConfigDict(frozen=True)

    width: PositiveFloat
    height: PositiveFloat
    material: Material = Material.SUBSTRATE


class RowSupport(BaseModel):
    """What carries each crop row: a top along the row, its upper surface
    `height` above the floor, `width` across and `depth` thick, reaching
    `overhang` beyond the row's first and last positions, its centre line
    `offset` to the left of the row's. Legs stand under it at most
    `leg_spacing` apart, from the floor to its underside; without, it hangs
    from the structure above."""

    model_config = ConfigDict(frozen=True)

    kind: Literal[FixtureKind.CROP_GUTTER, FixtureKind.BENCH] = FixtureKind.CROP_GUTTER
    height: PositiveFloat
    width: PositiveFloat
    depth: PositiveFloat
    overhang: NonNegativeFloat = 0.25
    offset: float = 0.0
    material: Material | None = None
    leg_spacing: PositiveFloat | None = None
    leg_radius: PositiveFloat = 0.02
    slab: Slab | None = None

    @model_validator(mode="after")
    def _its_top_is_above_the_floor(self) -> Self:
        if self.depth >= self.height:
            raise ValueError(
                f"a support {self.depth} m deep cannot have its top at {self.height} m"
            )
        return self

    @property
    def planting_height(self) -> float:
        """How high the crop stands: on the slab, or on the top."""
        return self.height + (0.0 if self.slab is None else self.slab.height)


# A tomato gutter: galvanised steel, 30 cm wide and 12 cm deep, its top at
# 60 cm, on stands at most 2 m apart, with a stone wool slab 20 cm wide and
# 7.5 cm high along it.
TOMATO_GUTTER: Final = RowSupport(
    kind=FixtureKind.CROP_GUTTER,
    height=0.6,
    width=0.3,
    depth=0.12,
    leg_spacing=2.0,
    slab=Slab(width=0.2, height=0.075),
)
# A bench, or table: an aluminium top 1.2 m wide and 5 cm thick at 80 cm, on
# legs at most 1.5 m apart, for plants in pots.
BENCH: Final = RowSupport(
    kind=FixtureKind.BENCH,
    height=0.8,
    width=1.2,
    depth=0.05,
    leg_spacing=1.5,
)


class PlantingPosition(BaseModel):
    """Where one plant can stand: on its row, in the greenhouse's frame."""

    model_config = ConfigDict(frozen=True)

    position_id: str
    # Its row, and its place along the row, each counted from 1.
    row: PositiveInt
    index: PositiveInt
    point: Vector3


class CropRows(BaseModel):
    """Parallel rows of planting positions, in metres and radians."""

    model_config = ConfigDict(frozen=True)

    # Where the first row's first planting position stands, on the floor.
    origin: Point2
    # Which way the rows run: a turn about the vertical from the greenhouse's x.
    heading: float = 0.0
    rows: PositiveInt
    positions_per_row: PositiveInt
    # From one planting position to the next along a row.
    plant_pitch: PositiveFloat
    # From one row to the next; with paired rows, from one pair to the next.
    row_spacing: PositiveFloat
    # With paired rows, how far the second row of each pair lies from the
    # first. Without, rows are evenly spaced.
    pair_gap: PositiveFloat | None = None
    # What carries each row; without, the crop stands on the floor.
    support: RowSupport | None = None

    @model_validator(mode="after")
    def _pairs_do_not_overlap(self) -> Self:
        if self.pair_gap is not None and self.pair_gap >= self.row_spacing:
            raise ValueError(
                f"a pair's rows ({self.pair_gap} m apart) reach the next pair "
                f"({self.row_spacing} m on)"
            )
        return self

    @property
    def along(self) -> Point2:
        """The unit direction the rows run in."""
        return Point2(x=math.cos(self.heading), y=math.sin(self.heading))

    @property
    def across(self) -> Point2:
        """The unit direction from one row to the next: to the left of `along`."""
        return Point2(x=-math.sin(self.heading), y=math.cos(self.heading))

    def row_offset(self, row: int) -> float:
        """How far row `row` (from 1) lies from the first, across the rows."""
        index = row - 1
        if self.pair_gap is None:
            return index * self.row_spacing
        pair, second = divmod(index, 2)
        return pair * self.row_spacing + second * self.pair_gap

    def point(self, row: int, along_row: float, *, across: float = 0.0, z: float = 0.0) -> Vector3:
        """The point of row `row` this far along it from its first position,
        `across` to its left and `z` above the floor."""
        offset = self.row_offset(row) + across
        along_unit, across_unit = self.along, self.across
        return Vector3(
            x=self.origin.x + along_unit.x * along_row + across_unit.x * offset,
            y=self.origin.y + along_unit.y * along_row + across_unit.y * offset,
            z=z,
        )

    @property
    def planting_height(self) -> float:
        """How high the planting positions stand: on the rows' support, or on
        the floor."""
        return 0.0 if self.support is None else self.support.planting_height

    @property
    def row_length(self) -> float:
        """From a row's first planting position to its last."""
        return (self.positions_per_row - 1) * self.plant_pitch

    def planting_positions(self, kept_clear: list[Strip] | None = None) -> list[PlantingPosition]:
        """Every planting position outside the areas kept clear, row by row,
        each row from its first."""
        return [
            PlantingPosition(
                position_id=f"row_{row}_position_{index}",
                row=row,
                index=index,
                point=self.point(row, (index - 1) * self.plant_pitch, z=self.planting_height),
            )
            for row in range(1, self.rows + 1)
            for index in self._kept(row, kept_clear or [])
        ]

    def _kept(self, row: int, kept_clear: list[Strip]) -> list[int]:
        """The places along a row (from 1) whose positions lie outside every
        area kept clear, with room for their support beyond them."""
        reach = 0.0 if self.support is None else LEAST_SUPPORT_REACH_M
        return [
            index
            for index in range(1, self.positions_per_row + 1)
            if not any(
                area.contains(self.point(row, (index - 1) * self.plant_pitch), reach)
                for area in kept_clear
            )
        ]

    def fixtures(self, kept_clear: list[Strip] | None = None) -> list[Fixture]:
        """Each row's supports, their legs and their slabs, if the rows have
        a support: one under each unbroken run of positions, clear of the
        kept areas."""
        areas = kept_clear or []
        return [
            fixture
            for row in range(1, self.rows + 1)
            for number, run in enumerate(self._runs(row, areas), start=1)
            for fixture in self._support_fixtures(row, number, run, areas)
        ]

    def _runs(self, row: int, kept_clear: list[Strip]) -> list[tuple[int, int]]:
        """The unbroken runs of a row's kept positions, each as its first and
        last place along the row."""
        runs: list[tuple[int, int]] = []
        for index in self._kept(row, kept_clear):
            if runs and runs[-1][1] == index - 1:
                runs[-1] = (runs[-1][0], index)
            else:
                runs.append((index, index))
        return runs

    def _support_span(
        self, row: int, run: tuple[int, int], kept_clear: list[Strip]
    ) -> tuple[float, float]:
        """How far along the row a support under a run starts and ends: the
        overhang beyond its first and last positions, cut short where any part
        of its width would reach into a kept area."""
        support = self.support
        assert support is not None
        first, last = ((index - 1) * self.plant_pitch for index in run)
        start, end = first - support.overhang, last + support.overhang
        line_start = self.point(row, 0.0, across=support.offset)
        for area in kept_clear:
            crossing = area.crossing(
                Point2(x=line_start.x, y=line_start.y), self.along, support.width / 2
            )
            if crossing is None:
                continue
            enters, leaves = crossing
            if start < leaves <= first + EDGE_TOLERANCE_M:
                start = min(leaves, first)
            if last - EDGE_TOLERANCE_M <= enters < end:
                end = max(enters, last)
        return start, end

    def _support_fixtures(
        self, row: int, number: int, run: tuple[int, int], kept_clear: list[Strip]
    ) -> list[Fixture]:
        """A support under a run of positions: its top, laid along the row,
        the legs under it, evenly spaced from end to end, and the slab on it."""
        support = self.support
        if support is None:
            return []
        support_id, slab_id = f"row_{row}_support_{number}", f"row_{row}_slab_{number}"
        start, end = self._support_span(row, run, kept_clear)
        bottom = support.height - support.depth
        across = support.offset
        fixtures = TrayPrimitive(
            fixture_id=support_id,
            kind=support.kind,
            start=self.point(row, start, across=across, z=bottom),
            end=self.point(row, end, across=across, z=bottom),
            width=support.width,
            depth=support.depth,
            material=support.material,
        ).fixtures()
        if support.leg_spacing is not None:
            # The end legs stand flush with the support's ends, not past them.
            first_leg, last_leg = start + support.leg_radius, end - support.leg_radius
            spans = math.ceil((last_leg - first_leg) / support.leg_spacing)
            for leg in range(spans + 1):
                along = first_leg + (last_leg - first_leg) * leg / spans
                fixtures += CylinderPrimitive(
                    fixture_id=f"{support_id}_leg_{leg + 1}",
                    kind=support.kind,
                    base=self.point(row, along, across=across),
                    radius=support.leg_radius,
                    height=bottom,
                    material=support.material,
                ).fixtures()
        if support.slab is not None:
            slab = support.slab
            fixtures += TrayPrimitive(
                fixture_id=slab_id,
                kind=FixtureKind.SLAB,
                start=self.point(row, start + SLAB_INSET_M, across=across, z=support.height),
                end=self.point(row, end - SLAB_INSET_M, across=across, z=support.height),
                width=slab.width,
                depth=slab.height,
                material=slab.material,
            ).fixtures()
        return fixtures
