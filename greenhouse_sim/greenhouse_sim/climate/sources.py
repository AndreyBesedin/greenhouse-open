"""What equipment does to the air, as source terms over a field's grid.

Whatever computes the air takes a piece of equipment's effect in the same
terms, cell by cell, so that no device depends on how the air is computed:

- **velocity added**, in m/s, for a fan's jet (`greenhouse_sim.climate.jets`);
- **heat added**, in watts per cell, for a heater, and for a dehumidifier's
  waste heat;
- **water removed**, in kg/s per cell, for a dehumidifier.

Every term scales with the equipment's level and vanishes when it is off.

A unit standing on the floor fills the cells its body holds, which the air
does not reach (`greenhouse_sim.cfd.geometry.CfdGeometry.solid`): it gives
its heat to, and draws its water from, the air cells around its body
instead: those whose centres lie within a cell of it, beside it or above it.

A unit heater blows its warm air out of its front (#261): its heat is given
to the cells that air passes through, weighted as a round jet's speed is
(`greenhouse_sim.climate.jets`), from an outlet as wide as its front, along
its heading. Put into the few cells around its body, a heater sized to the
house warmed them past 100 °C in a run's first minutes, where a unit
heater's outlet is some 40 to 70 °C; its total heat is the same either way.
"""

from dataclasses import dataclass
from typing import Final, Self

import numpy as np

from greenhouse_sim.climate.jets import JET_DECAY, JET_REACH_WIDTHS, jet_velocity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.world.equipment import Dehumidifier, Equipment, Fan, Heater
from greenhouse_sim.world.geometry import Vector3


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


# How far along its heading a heater's warm air carries its heat, in
# diameters of its outlet: the jet's core, where a round jet keeps its
# outlet's width (`climate.jets`). On the reference greenhouse's 30 kW it
# keeps its warmest cells at 50 to 55 °C in a run's first minutes, within a
# unit heater's usual outlet temperatures.
HEATER_JET_DIAMETERS: Final = JET_DECAY


def _heater_jet(piece: Heater, grid: FieldGrid, solid: np.ndarray) -> np.ndarray:
    """How a heater's heat is shared among the air cells of its jet: by the
    speed a round jet from its outlet would have at each cell's centre, up
    to `HEATER_JET_DIAMETERS` outlet diameters along its heading. Its outlet
    is the middle of its front, as wide as its front is high or wide,
    whichever is less."""
    axis = piece.facing()
    diameter = min(piece.size_y, piece.size_z)
    radius = diameter / 2
    front = piece.size_x / 2
    xs, ys, zs = grid.centres()
    z, y, x = np.meshgrid(zs, ys, xs, indexing="ij")
    dx = x - (piece.base.x + axis.x * front)
    dy = y - (piece.base.y + axis.y * front)
    dz = z - (piece.base.z + piece.size_z / 2)
    along = dx * axis.x + dy * axis.y + dz * axis.z
    across_squared = np.maximum(dx**2 + dy**2 + dz**2 - along**2, 0.0)
    width = np.maximum(radius, along / (2 * JET_DECAY))
    reached = (
        (along >= 0.0)
        & (along <= HEATER_JET_DIAMETERS * diameter)
        & (across_squared <= (JET_REACH_WIDTHS * width) ** 2)
        & ~solid
    )
    weight: np.ndarray = np.where(reached, radius / width * np.exp(-across_squared / width**2), 0.0)
    return weight


def source_terms(piece: Equipment, level: float, grid: FieldGrid, solid: np.ndarray) -> SourceTerms:
    """What a piece of equipment does to the air at a level, on a grid whose
    `solid` cells its obstacles fill."""
    terms = SourceTerms.none(grid)
    if level <= 0.0:
        return terms
    if isinstance(piece, Fan):
        return SourceTerms(
            grid=grid,
            velocity=jet_velocity(piece, level, grid, solid),
            heat_w=terms.heat_w,
            water_removed_kg_s=terms.water_removed_kg_s,
        )
    region = _around(piece, grid, solid)
    share = region / region.sum()
    if isinstance(piece, Heater):
        jet = _heater_jet(piece, grid, solid)
        # A heater whose outlet faces a wall gives its heat around its body.
        if jet.sum() > 0.0:
            share = jet / jet.sum()
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
        water_removed_kg_s=share * level * piece.removal_kg_h / HOUR_S,
    )
