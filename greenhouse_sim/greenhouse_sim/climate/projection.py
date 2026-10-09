"""The air's flow through a grid's faces, made to conserve its mass (P05.3).

A fan's jet appears at its rotor and grows as it entrains the air around it,
and it stops dead at a wall: added to the base airflow, it makes air appear
and vanish. Carried by such a flow, heat appears and vanishes too, and a
running fan would cool a heated house.

So the flow is projected before it carries anything. Each face's flow is its
area times the mean of its two cells' velocities across it, none through the
grid's faces or into a cell an obstacle fills. A pressure-like potential φ
over the air cells, solved from ∇²φ = ∇·F by conjugate gradients, then
takes its gradient out of every face's flow: F′ = F − (A / h)(φ_upper −
φ_lower). What flows into each cell then flows out of it. The fan now draws
the air it blows from behind it, and its jet turns back along the house
where it meets a wall.

Air may also cross the grid's faces where doors and vents open (P07.6):
given what enters each cell from outside, `inflow`, the projection makes
what flows out of each cell through its interior faces that much more than
flows in, and the air entering at one opening crosses the house to leave by
another.
"""

from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid

# The solve stops once what the flow leaves unbalanced in any cell is this
# share of the most it left before.
TOLERANCE: Final = 1e-10
# And in any case after this many iterations.
MOST_ITERATIONS: Final = 5000
# A grid's axes in its arrays, (z, y, x), with each one's velocity component.
AXES: Final = ((2, 0), (1, 1), (0, 2))
_ALL: Final = (slice(None), slice(None), slice(None))


def _low_high(axis: int) -> tuple[tuple[slice, ...], tuple[slice, ...]]:
    """Where the cells below and above every interior face along `axis` lie."""
    low = list(_ALL)
    high = list(_ALL)
    low[axis] = slice(0, -1)
    high[axis] = slice(1, None)
    return tuple(low), tuple(high)


@dataclass(frozen=True, eq=False)
class FaceFlows:
    """The air's flow through a grid's interior faces, m³/s from each face's
    lower cell to its upper, axis by axis in the grid's order (z, y, x), each
    with where its faces' lower and upper cells lie."""

    grid: FieldGrid
    flows: tuple[np.ndarray, np.ndarray, np.ndarray]

    def faces(self) -> list[tuple[int, tuple[slice, ...], tuple[slice, ...], np.ndarray]]:
        return [(axis, *_low_high(axis), self.flows[axis]) for axis in (0, 1, 2)]

    def divergence(self) -> np.ndarray:
        """What flows out of each cell, less what flows in, m³/s."""
        nx, ny, nz = self.grid.shape
        out = np.zeros((nz, ny, nx))
        for _, low, high, flow in self.faces():
            out[low] += flow
            out[high] -= flow
        return out

    def velocity(self) -> np.ndarray:
        """The velocity at each cell's centre, the mean of its two faces'
        along each axis over their area, in the grid's order (z, y, x) with
        its three components last."""
        nx, ny, nz = self.grid.shape
        velocity = np.zeros((nz, ny, nx, VECTOR_COMPONENTS))
        size = self.grid.cell_size
        areas = {2: size.y * size.z, 1: size.x * size.z, 0: size.x * size.y}
        for axis, component in AXES:
            low, high = _low_high(axis)
            flow = self.flows[axis] / areas[axis] / 2
            velocity[..., component][low] += flow
            velocity[..., component][high] += flow
        return velocity


def _areas_and_spacings(grid: FieldGrid) -> dict[int, tuple[float, float]]:
    size = grid.cell_size
    return {
        2: (size.y * size.z, size.x),
        1: (size.x * size.z, size.y),
        0: (size.x * size.y, size.z),
    }


def face_flows(grid: FieldGrid, velocity: np.ndarray, solid: np.ndarray) -> FaceFlows:
    """The flow through each interior face: its area times the mean of its two
    cells' velocities across it, none into a solid cell."""
    air = ~solid
    flows: dict[int, np.ndarray] = {}
    sides = _areas_and_spacings(grid)
    for axis, component in AXES:
        low, high = _low_high(axis)
        across = velocity[..., component]
        open_face = air[low] & air[high]
        area, _ = sides[axis]
        flows[axis] = np.where(open_face, area * (across[low] + across[high]) / 2, 0.0)
    return FaceFlows(grid=grid, flows=(flows[0], flows[1], flows[2]))


def conserving(flows: FaceFlows, solid: np.ndarray, inflow: np.ndarray | None = None) -> FaceFlows:
    """The flow with what makes air appear or vanish taken out: what flows
    into each air cell flows out of it, to `TOLERANCE`, but for what enters
    it from outside, `inflow` (m³/s, negative leaving), which must balance."""
    grid = flows.grid
    air = ~solid
    sides = _areas_and_spacings(grid)
    # Each face's conductance, A / h, open faces only.
    conductances = []
    for axis, low, high, _ in flows.faces():
        area, spacing = sides[axis]
        conductances.append((axis, low, high, np.where(air[low] & air[high], area / spacing, 0.0)))
    nx, ny, nz = grid.shape
    diagonal = np.zeros((nz, ny, nx))
    for _, low, high, conductance in conductances:
        diagonal[low] += conductance
        diagonal[high] += conductance
    linked = diagonal > 0

    def laplacian(potential: np.ndarray) -> np.ndarray:
        """Σ over a cell's faces of A/h (φ_cell − φ_neighbour)."""
        result = np.zeros_like(potential)
        for axis, low, high, conductance in conductances:
            step = conductance * np.diff(potential, axis=axis)
            result[low] -= step
            result[high] += step
        return result

    # Solve L φ = −∇·F over the linked air cells: their total is zero, as
    # nothing crosses the grid's faces; what rounding leaves is spread out.
    entering = np.zeros(diagonal.shape) if inflow is None else inflow
    divergence = np.where(linked, flows.divergence() - entering, 0.0)
    target = (
        np.where(linked, divergence - divergence[linked].mean(), 0.0)
        if linked.any()
        else divergence
    )
    scale = float(np.abs(target).max())
    potential = np.zeros_like(target)
    if scale > 0:
        inverse = np.where(linked, 1 / np.where(linked, diagonal, 1.0), 0.0)
        residual = -target - laplacian(potential)
        preconditioned = inverse * residual
        direction = preconditioned.copy()
        product = float((residual * preconditioned).sum())
        for _ in range(MOST_ITERATIONS):
            if float(np.abs(residual).max()) <= TOLERANCE * scale:
                break
            applied = laplacian(direction)
            length = product / float((direction * applied).sum())
            potential += length * direction
            residual -= length * applied
            preconditioned = inverse * residual
            following = float((residual * preconditioned).sum())
            direction = preconditioned + (following / product) * direction
            product = following
    corrected = []
    for axis, _, _, conductance in conductances:
        flow = flows.flows[axis]
        corrected.append(flow - conductance * np.diff(potential, axis=axis))
    return FaceFlows(grid=grid, flows=(corrected[0], corrected[1], corrected[2]))
