"""What equipment does to the air, as source terms over a field's grid.

Whatever computes the air takes a piece of equipment's effect in the same
terms, cell by cell, so that no device depends on how the air is computed.
A piece's terms are the sum of its capabilities'
(`greenhouse_sim.world.capabilities`), whatever its kind (P14.5):

- **velocity added**, in m/s, for air it moves, as a jet
  (`greenhouse_sim.climate.jets`);
- **heat added**, in watts per cell, for heat it gives, as heating or
  waste heat;
- **water removed**, in kg/s per cell, for the air it dries.

Every term scales with the equipment's level and vanishes when it is off.

A unit standing on the floor fills the cells its body holds, which the air
does not reach (`greenhouse_sim.cfd.geometry.CfdGeometry.solid`): it gives
its heat to, and draws its water from, the air cells around its body
instead: those whose centres lie within a cell of it, beside it or above it.

Heat blown from an outlet, as a unit heater blows its warm air out of its
front (#261), is given to the cells that air passes through, weighted as a
round jet's speed is (`greenhouse_sim.climate.jets`), from its outlet along
its axis. Put into the few cells around its body, a heater sized to the
house warmed them past 100 °C in a run's first minutes, where a unit
heater's outlet is some 40 to 70 °C; its total heat is the same either way.
"""

import math
from dataclasses import dataclass
from typing import Final, Self

import numpy as np

from greenhouse_sim.climate.jets import JET_DECAY, JET_REACH_WIDTHS, jet_velocity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.world.capabilities import (
    Capability,
    Device,
    Dries,
    Heats,
    MovesAir,
    Outlet,
    WasteHeat,
)
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


def _around(piece: Device, grid: FieldGrid, solid: np.ndarray) -> np.ndarray:
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
# outlet's width (`climate.jets`). An exploratory heuristic (#261), not a
# model of a unit heater's plume: the heat is shared as the jet's speed is,
# and stops where its core does. Chosen on the reference greenhouse's
# 30 kW, where it keeps the warmest cells at 50 to 55 °C in a run's first
# minutes, within a unit heater's usual outlet temperatures (3 diameters
# gave 71 to 77 °C, 10 gave 38 to 41 °C); other heaters are not checked
# against one.
HEATER_JET_DIAMETERS: Final = JET_DECAY


def _heater_jet(blown: Outlet, grid: FieldGrid, solid: np.ndarray) -> np.ndarray | None:
    """How heat blown from an outlet is shared among the air cells of its
    jet: by the speed a round jet from the outlet would have at each cell's
    centre, up to `HEATER_JET_DIAMETERS` outlet diameters along its axis, or
    to the first obstacle on it. A jet too narrow for any cell's centre
    gives its heat to the cells its axis passes through; one whose outlet an
    obstacle blocks has none, and its heat stays around its body."""
    axis = blown.axis
    diameter = blown.diameter_m
    radius = diameter / 2
    outlet = blown.centre
    passed, reach = _axis_cells(outlet, axis, HEATER_JET_DIAMETERS * diameter, grid, solid)
    if not passed:
        return None
    xs, ys, zs = grid.centres()
    z, y, x = np.meshgrid(zs, ys, xs, indexing="ij")
    dx, dy, dz = x - outlet.x, y - outlet.y, z - outlet.z
    along = dx * axis.x + dy * axis.y + dz * axis.z
    across_squared = np.maximum(dx**2 + dy**2 + dz**2 - along**2, 0.0)
    width = np.maximum(radius, along / (2 * JET_DECAY))
    reached = (
        (along >= 0.0)
        & (along <= reach)
        & (across_squared <= (JET_REACH_WIDTHS * width) ** 2)
        & ~solid
    )
    weight: np.ndarray = np.where(reached, radius / width * np.exp(-across_squared / width**2), 0.0)
    if weight.sum() > 0.0:
        return weight
    for cell in passed:
        weight[cell] = 1.0
    return weight


def _axis_cells(
    outlet: Vector3, axis: Vector3, length: float, grid: FieldGrid, solid: np.ndarray
) -> tuple[list[tuple[int, int, int]], float]:
    """The air cells a line from `outlet` along `axis` passes through, in
    the grid's order (z, y, x), and how far along it they reach: to
    `length`, or to the first cell an obstacle fills, or the grid's edge.
    Walked half the smallest cell at a time, from half that in front of the
    outlet; none if the first cell is an obstacle's."""
    step = min(grid.cell_size.x, grid.cell_size.y, grid.cell_size.z) / 2
    nx, ny, nz = grid.shape
    passed: list[tuple[int, int, int]] = []
    along = step / 2
    while along <= length:
        point = (
            outlet.x + axis.x * along,
            outlet.y + axis.y * along,
            outlet.z + axis.z * along,
        )
        index = (
            math.floor((point[2] - grid.origin.z) / grid.cell_size.z),
            math.floor((point[1] - grid.origin.y) / grid.cell_size.y),
            math.floor((point[0] - grid.origin.x) / grid.cell_size.x),
        )
        if not (0 <= index[0] < nz and 0 <= index[1] < ny and 0 <= index[2] < nx) or solid[index]:
            return passed, along
        if not passed or passed[-1] != index:
            passed.append(index)
        along += step
    return passed, length


def source_terms(piece: Device, level: float, grid: FieldGrid, solid: np.ndarray) -> SourceTerms:
    """What a piece of equipment does to the air at a level, on a grid whose
    `solid` cells its obstacles fill: the sum of what each of its
    capabilities does."""
    terms = SourceTerms.none(grid)
    if level <= 0.0:
        return terms
    for capability in piece.capabilities():
        terms = terms + _capability_terms(piece, capability, level, grid, solid)
    return terms


def _capability_terms(
    piece: Device, capability: Capability, level: float, grid: FieldGrid, solid: np.ndarray
) -> SourceTerms:
    """What one of a piece's capabilities does to the air at a level."""
    none = SourceTerms.none(grid)
    match capability:
        case MovesAir():
            velocity = jet_velocity(capability, level, grid, solid)
            return SourceTerms(grid, velocity, none.heat_w, none.water_removed_kg_s)
        case Heats(power_w=power_w, outlet=outlet):
            # Heat blown from an outlet an obstacle blocks is given around
            # the piece's body.
            jet = None if outlet is None else _heater_jet(outlet, grid, solid)
            share = _share(piece, grid, solid) if jet is None else jet / jet.sum()
            return SourceTerms(
                grid, none.velocity, share * level * power_w, none.water_removed_kg_s
            )
        case WasteHeat(heat_w=heat_w):
            heat = _share(piece, grid, solid) * level * heat_w
            return SourceTerms(grid, none.velocity, heat, none.water_removed_kg_s)
        case Dries(removal_kg_h=removal_kg_h):
            water = _share(piece, grid, solid) * level * removal_kg_h / HOUR_S
            return SourceTerms(grid, none.velocity, none.heat_w, water)


def _share(piece: Device, grid: FieldGrid, solid: np.ndarray) -> np.ndarray:
    """Each air cell's share of what a piece gives the air around its body."""
    region = _around(piece, grid, solid)
    share: np.ndarray = region / region.sum()
    return share
