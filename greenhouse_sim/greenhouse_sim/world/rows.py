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
"""

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt, model_validator

from greenhouse_sim.world.geometry import Point2, Vector3


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

    def point(self, row: int, along_row: float) -> Vector3:
        """The point of row `row` this far along it from its first position, on
        the floor."""
        offset = self.row_offset(row)
        along, across = self.along, self.across
        return Vector3(
            x=self.origin.x + along.x * along_row + across.x * offset,
            y=self.origin.y + along.y * along_row + across.y * offset,
            z=0.0,
        )

    def planting_positions(self) -> list[PlantingPosition]:
        """Every planting position, row by row, each row from its first."""
        return [
            PlantingPosition(
                position_id=f"row_{row}_position_{index}",
                row=row,
                index=index,
                point=self.point(row, (index - 1) * self.plant_pitch),
            )
            for row in range(1, self.rows + 1)
            for index in range(1, self.positions_per_row + 1)
        ]
