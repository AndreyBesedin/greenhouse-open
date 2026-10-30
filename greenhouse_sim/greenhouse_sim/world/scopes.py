"""Where an instance of a run's crop grows, and its areas (P14.9, decision
0062).

A crop instance is a model on a spatial scope. The first scope is a row of
the layout's crop rows (`greenhouse_sim.world.rows.CropRows`): its planting
positions, kept clear of paths and zones as the layout keeps them, and its
areas, kept apart:

- **its cultivated area,** the ground its planting positions take: each
  position as long as the plant pitch, and as wide as the row's share of
  the rows' spacing, which is the whole spacing for rows evenly spaced and
  half of it for paired rows, whose spacing runs from one pair to the next.
  A position kept clear takes none.
- **its floor,** its share of the house's floor (`Envelope`: its length by
  its width, as heat is given per m² of it), by its cultivated area: the
  paths, the headlands and the ground between the rows are shared out
  among the rows as their crop is.

A crop model declares which area its quantities are per (`AreaBasis`). A
quantity of a scope is converted from one basis to another explicitly
(`converted`), and so is a total of the scope from a quantity per m²
(`total`): the total is the same on every basis, and every scope's floor
adds up to the house's.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, PositiveFloat, PositiveInt

from greenhouse_sim.domain.scopes import AreaBasis, ScopeKind
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import CropRows, PlantingPosition

# How a row's scope is named, by its number from 1.
ROW_SCOPE: Final = "row_{row}"
# Paired rows share one spacing, from a pair to the next, two to a pair.
ROWS_TO_A_PAIR: Final = 2


class CropScope(BaseModel):
    """Where an instance of a run's crop grows: see the module."""

    model_config = ConfigDict(frozen=True)

    scope_id: str
    kind: ScopeKind
    row: PositiveInt
    # Its planting positions, in their order along it.
    positions: tuple[PlantingPosition, ...]
    cultivated_m2: PositiveFloat
    floor_m2: PositiveFloat

    def area_m2(self, basis: AreaBasis) -> float:
        """Its area on `basis`, in m²."""
        match basis:
            case AreaBasis.FLOOR:
                return self.floor_m2
            case AreaBasis.CULTIVATED:
                return self.cultivated_m2

    def density(self, plants: int, basis: AreaBasis) -> float:
        """How many plants it holds per m² of `basis`, if it holds
        `plants`."""
        return plants / self.area_m2(basis)


def row_share(rows: CropRows) -> float:
    """How wide each row's share of the ground is, across the rows: from one
    row to the next, or, with paired rows, half a pair's (m)."""
    return rows.row_spacing if rows.pair_gap is None else rows.row_spacing / ROWS_TO_A_PAIR


def band_offset(rows: CropRows, row: int) -> float:
    """Where the middle of row `row`'s share of the ground lies, across the
    rows from the row itself (m): on it, or, with paired rows, so that the
    pair's two shares meet halfway between its rows."""
    if rows.pair_gap is None:
        return 0.0
    toward_its_pair = (rows.pair_gap - row_share(rows)) / 2
    first_of_its_pair = (row - 1) % ROWS_TO_A_PAIR == 0
    return toward_its_pair if first_of_its_pair else -toward_its_pair


def row_scopes(layout: Layout, envelope: Envelope) -> list[CropScope]:
    """A scope for each row of the layout's crop rows that keeps a planting
    position, in the rows' order; none without crop rows."""
    rows = layout.crop_rows
    if rows is None:
        return []
    share = row_share(rows)
    kept = layout.planting_positions()
    by_row = {
        row: tuple(position for position in kept if position.row == row)
        for row in range(1, rows.rows + 1)
    }
    cultivated = {
        row: len(positions) * rows.plant_pitch * share
        for row, positions in by_row.items()
        if positions
    }
    every_row = sum(cultivated.values())
    floor = envelope.length * envelope.width
    return [
        CropScope(
            scope_id=ROW_SCOPE.format(row=row),
            kind=ScopeKind.ROW,
            row=row,
            positions=by_row[row],
            cultivated_m2=area,
            floor_m2=floor * area / every_row,
        )
        for row, area in cultivated.items()
    ]


def scope_plants(scopes: list[CropScope], plant_ids: list[str]) -> dict[str, list[str]]:
    """The plants each scope holds, by its name: the first plant stands at
    the first planting position the layout keeps, and so on, row by row, as
    a scenario's crop is planted; a position past the last plant holds
    none."""
    held: dict[str, list[str]] = {scope.scope_id: [] for scope in scopes}
    positions = [(scope.scope_id, position) for scope in scopes for position in scope.positions]
    for plant_id, (scope_id, _) in zip(plant_ids, positions, strict=False):
        held[scope_id].append(plant_id)
    return held


def total(per_m2: float, scope: CropScope, basis: AreaBasis) -> float:
    """A scope's total of a quantity given per m² of `basis`."""
    return per_m2 * scope.area_m2(basis)


def converted(per_m2: float, scope: CropScope, given: AreaBasis, wanted: AreaBasis) -> float:
    """A scope's quantity given per m² of `given`, per m² of `wanted`: the
    same total, over the other area."""
    return total(per_m2, scope, given) / scope.area_m2(wanted)
