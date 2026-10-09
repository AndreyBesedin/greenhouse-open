"""Open doors and vents, as a climate run exchanges air through them (P05.5,
P07.6).

What each passes is the wind's and the stack's (`climate.openings`): a net
flow, into the house or out of it, which the run's flow carries across the
house to the openings it leaves by (`climate.projection`), and an exchange
each way besides. Both are shared evenly among the cells against it. The
air entering brings the outside's heat, water and CO2; the air leaving
takes the cells' own.

It also shows a draught there, so the arrows respond: the net flow through
the cells' faces, in or out; or, with none, the exchange, out of the house
when the air against it is warmer than the outside's and in when it is
cooler, as the stack effect would have it. A run's doors and vents are
those open at its start or opened by its schedule (P07.8), each at the
level the schedule leaves it at; shut, one passes nothing.
"""

from dataclasses import dataclass, replace
from typing import Final

import numpy as np

from greenhouse_sim.climate.openings import OpeningFlow, OpeningSite
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid
from greenhouse_sim.world.envelope import Opening

# Each array axis, (z, y, x), and the velocity component along it.
_COMPONENT: Final = {0: 2, 1: 1, 2: 0}


@dataclass(frozen=True, eq=False)
class Vent:
    """A door or vent a run may open: where it is (`OpeningSite`), the cells
    against it in the grid's order (z, y, x), the array axis square to the
    face it lies on, which way along it is out of the house, +1 or -1, and
    the opening itself, for its aperture as it is opened."""

    site: OpeningSite
    cells: np.ndarray
    axis: int
    outward: int
    opening: Opening

    def site_at(self, level: float) -> OpeningSite:
        """Where it is, opened to `level`, from 0 (shut) to 1 (fully)."""
        aperture = self.opening.model_copy(update={"opening": level}).aperture_area()
        return replace(self.site, aperture_m2=aperture)

    @property
    def opening_id(self) -> str:
        return self.site.opening_id

    @property
    def aperture_m2(self) -> float:
        return self.site.aperture_m2

    def spread(self, m3_s: float) -> np.ndarray:
        """A flow through it shared evenly among the cells against it."""
        count = int(self.cells.sum())
        share = m3_s / count if count else 0.0
        return np.where(self.cells, share, 0.0)

    def draught(
        self, grid: FieldGrid, flow: OpeningFlow, temperature: np.ndarray, outside_c: float
    ) -> np.ndarray:
        """The draught through it at each cell's centre (z, y, x, then its
        three components): its net flow, in or out, through the cells'
        faces; or, with none, its exchange, out when the air against it is
        warmer than the outside's and in when it is cooler."""
        nx, ny, nz = grid.shape
        velocity = np.zeros((nz, ny, nx, VECTOR_COMPONENTS))
        count = int(self.cells.sum())
        if count == 0:
            return velocity
        size = grid.cell_size
        faces = {0: size.x * size.y, 1: size.x * size.z, 2: size.y * size.z}
        if flow.net_m3_s != 0:
            outwards = -flow.net_m3_s
        else:
            warmer = float(temperature[self.cells].mean()) > outside_c
            outwards = flow.exchange_m3_s if warmer else -flow.exchange_m3_s
        speed = outwards / (count * faces[self.axis])
        velocity[..., _COMPONENT[self.axis]] = np.where(self.cells, self.outward * speed, 0.0)
        return velocity
