"""What equipment does to the air, as source terms over a field's grid.

Whatever computes the air takes a piece of equipment's effect in the same
terms, cell by cell, so that no device depends on how the air is computed:

- **velocity added**, in m/s, for a fan's jet (P05.2);
- **heat added**, in watts per cell, for a heater, and for a dehumidifier's
  waste heat;
- **water removed**, in kg/s per cell, for a dehumidifier.

Every term scales with the equipment's level and vanishes when it is off.

A unit standing on the floor fills the cells its body holds, which the air
does not reach (`greenhouse_sim.cfd.geometry.CfdGeometry.solid`): it gives
its heat to, and draws its water from, the air cells around its body
instead: those whose centres lie within a cell of it, beside it or above it.
"""

from dataclasses import dataclass
from typing import Final, Self

import numpy as np

from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid
from greenhouse_sim.world.equipment import Dehumidifier, Equipment, Fan, Heater
from greenhouse_sim.world.geometry import Vector3

SECONDS_PER_HOUR: Final = 3600


@dataclass(frozen=True, eq=False)
class SourceTerms:
    """What equipment adds to the air in each cell of a grid, in its order
    (z, y, x): velocity (m/s, three components), heat (W) and water removed
    (kg/s)."""

    grid: FieldGrid
    velocity: np.ndarray
    heat_w: np.ndarray
    water_removed_kg_s: np.ndarray

    @classmethod
    def none(cls, grid: FieldGrid) -> Self:
        nx, ny, nz = grid.shape
        return cls(
            grid=grid,
            velocity=np.zeros((nz, ny, nx, VECTOR_COMPONENTS)),
            heat_w=np.zeros((nz, ny, nx)),
            water_removed_kg_s=np.zeros((nz, ny, nx)),
        )

    def __add__(self, other: SourceTerms) -> SourceTerms:
        if other.grid != self.grid:
            raise ValueError("source terms on different grids cannot be added")
        return SourceTerms(
            grid=self.grid,
            velocity=self.velocity + other.velocity,
            heat_w=self.heat_w + other.heat_w,
            water_removed_kg_s=self.water_removed_kg_s + other.water_removed_kg_s,
        )

    def total_heat_w(self) -> float:
        return float(self.heat_w.sum())

    def total_water_removed_kg_s(self) -> float:
        return float(self.water_removed_kg_s.sum())


def _around(piece: Heater | Dehumidifier, grid: FieldGrid, solid: np.ndarray) -> np.ndarray:
    """The air cells around a unit's body: those whose centres lie within a
    cell of its box, beside it or above it, and that it does not fill; or,
    if there are none, the air cell nearest its middle."""
    low, high = piece.fixture().bounds()
    size = grid.cell_size
    xs, ys, zs = grid.centres()
    near = (
        ((zs >= low.z) & (zs <= high.z + size.z))[:, None, None]
        & ((ys >= low.y - size.y) & (ys <= high.y + size.y))[None, :, None]
        & ((xs >= low.x - size.x) & (xs <= high.x + size.x))[None, None, :]
    )
    region: np.ndarray = near & ~solid
    if region.any():
        return region
    middle = Vector3(x=(low.x + high.x) / 2, y=(low.y + high.y) / 2, z=(low.z + high.z) / 2)
    distance = (
        (zs - middle.z)[:, None, None] ** 2
        + (ys - middle.y)[None, :, None] ** 2
        + (xs - middle.x)[None, None, :] ** 2
    )
    distance = np.where(solid, np.inf, distance)
    nearest = np.zeros_like(solid)
    nearest[np.unravel_index(int(np.argmin(distance)), distance.shape)] = True
    return nearest


def source_terms(piece: Equipment, level: float, grid: FieldGrid, solid: np.ndarray) -> SourceTerms:
    """What a piece of equipment does to the air at a level, on a grid whose
    `solid` cells its obstacles fill."""
    terms = SourceTerms.none(grid)
    if level <= 0.0 or isinstance(piece, Fan):
        # A fan's jet comes with P05.2.
        return terms
    region = _around(piece, grid, solid)
    share = region / region.sum()
    if isinstance(piece, Heater):
        return SourceTerms(
            grid=grid,
            velocity=terms.velocity,
            heat_w=share * level * piece.power_w,
            water_removed_kg_s=terms.water_removed_kg_s,
        )
    return SourceTerms(
        grid=grid,
        velocity=terms.velocity,
        heat_w=share * level * piece.heat_w,
        water_removed_kg_s=share * level * piece.removal_kg_h / SECONDS_PER_HOUR,
    )
