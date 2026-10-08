"""Open doors and vents, as a climate run exchanges air through them (P05.5).

Until wind comes (P07), an open door or vent exchanges the air in the cells
against it with the outside's at a fixed speed through its aperture
(`ClimateSettings.vent_exchange_m_s`), as much in as out, so the flow inside
needs no more air than it has. That mixes the outside's temperature and
water into those cells, shared evenly among them.

It also shows a draught there, so the arrows respond: out of the house when
the air against it is warmer than the outside's, and in when it is cooler,
as the stack effect would have it, through the cells' faces at the speed
that carries the exchange. A closed door or vent exchanges nothing.
"""

from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.fields.field import VECTOR_COMPONENTS, FieldGrid

# Each array axis, (z, y, x), and the velocity component along it.
_COMPONENT: Final = {0: 2, 1: 1, 2: 0}


@dataclass(frozen=True, eq=False)
class Vent:
    """An open door or vent: its aperture, the cells against it in the grid's
    order (z, y, x), the array axis square to the face it lies on, and which
    way along it is out of the house, +1 or -1."""

    opening_id: str
    aperture_m2: float
    cells: np.ndarray
    axis: int
    outward: int

    def exchange_m3_s(self, speed_m_s: float) -> np.ndarray:
        """The outside air each of its cells takes in, and gives out, per
        second: its share of the speed through the aperture."""
        count = int(self.cells.sum())
        share = speed_m_s * self.aperture_m2 / count if count else 0.0
        return np.where(self.cells, share, 0.0)

    def draught(
        self, grid: FieldGrid, temperature: np.ndarray, outside_c: float, speed_m_s: float
    ) -> np.ndarray:
        """The draught through it at each cell's centre (z, y, x, then its
        three components): along its axis, out when the air against it is
        warmer than the outside's, in when it is cooler, at the speed that
        carries the exchange through the cells' faces."""
        nx, ny, nz = grid.shape
        velocity = np.zeros((nz, ny, nx, VECTOR_COMPONENTS))
        count = int(self.cells.sum())
        if count == 0:
            return velocity
        size = grid.cell_size
        faces = {0: size.x * size.y, 1: size.x * size.z, 2: size.y * size.z}
        speed = speed_m_s * self.aperture_m2 / (count * faces[self.axis])
        warmer = float(temperature[self.cells].mean()) > outside_c
        direction = self.outward if warmer else -self.outward
        velocity[..., _COMPONENT[self.axis]] = np.where(self.cells, direction * speed, 0.0)
        return velocity
