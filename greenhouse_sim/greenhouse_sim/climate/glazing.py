"""Heat through the glass, as the wind changes it (P07.4).

Glass passes heat through three resistances in turn: the still air film on
its inside, the glass itself, and the film on its outside,

    1 / U = 1 / h_in + R_glass + 1 / h_out,

and the outside film thins as the wind blows: h_out = 5.8 + 4.1 v W/m²K, a
common engineering correlation (McAdams). A scenario's configured U is read
as its glass's in a moderate wind, `REFERENCE_WIND_M_S`, the conditions
single glass's tabulated 6 W/m²K is quoted for; the films set U at every
other wind. Single glass passes about 3.4 W/m²K in still air, and 7 in a
gale.

A glazed surface's temperature lies between the air on either side, in
proportion to the resistances: T_s = T_in − (U / h_in) (T_in − T_out). The
glass has no heat capacity of its own, so it follows the air at once.

On the climate run's grid, a cell against the walls or under the roof
passes heat through the face it lies against (`climate.transport`): the
side and end walls are the grid's sides, and the roof slopes its top,
each slope over its half of its span.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.envelope import Envelope

# The outside film's coefficient in still air, and how much each metre a
# second of wind adds to it.
STILL_FILM_W_M2K: Final = 5.8
FILM_PER_WIND_W_M2K: Final = 4.1
# The wind a configured U is read at.
REFERENCE_WIND_M_S: Final = 4.0
# The glass itself: 4 mm of float glass, at 1.0 W/mK.
GLASS_RESISTANCE_M2K_W: Final = 0.004


def outside_film_w_m2k(wind_m_s: float) -> float:
    """The outside air film's heat transfer coefficient in a wind."""
    return STILL_FILM_W_M2K + FILM_PER_WIND_W_M2K * wind_m_s


def _inside_resistance(configured_u: float) -> float:
    """The resistance inside the outside film, the inner film's and the
    glass's, for a U configured at the reference wind."""
    return 1.0 / configured_u - 1.0 / outside_film_w_m2k(REFERENCE_WIND_M_S)


def most_u_w_m2k() -> float:
    """The highest U glass can have at the reference wind: the glass and the
    outside film alone, with no inner film at all."""
    return 1.0 / (GLASS_RESISTANCE_M2K_W + 1.0 / outside_film_w_m2k(REFERENCE_WIND_M_S))


def glazing_u_w_m2k(configured_u: float, wind_m_s: float) -> float:
    """The glass's U in a wind, for a U configured at the reference wind;
    glass configured to pass nothing passes nothing."""
    if configured_u <= 0:
        return 0.0
    return 1.0 / (_inside_resistance(configured_u) + 1.0 / outside_film_w_m2k(wind_m_s))


def inside_film_w_m2k(configured_u: float) -> float:
    """The inner air film's heat transfer coefficient."""
    return 1.0 / (_inside_resistance(configured_u) - GLASS_RESISTANCE_M2K_W)


def surface_temperature_c(
    inside_c: float, outside_c: float, configured_u: float, wind_m_s: float
) -> float:
    """A glazed surface's temperature, between the air inside and out; the
    inside air's, for glass configured to pass nothing."""
    if configured_u <= 0:
        return inside_c
    u = glazing_u_w_m2k(configured_u, wind_m_s)
    return inside_c - u / inside_film_w_m2k(configured_u) * (inside_c - outside_c)


@dataclass(frozen=True, eq=False)
class GlazedCells:
    """The air cells, in the grid's order (z, y, x), that pass heat through
    one glazed surface, and the area of each one's face against it."""

    cells: np.ndarray
    face_m2: float

    def area_m2(self) -> float:
        return float(self.cells.sum()) * self.face_m2


def glazed_cells(envelope: Envelope, grid: FieldGrid, solid: np.ndarray) -> dict[str, GlazedCells]:
    """The air cells that pass heat through each glazed surface, by the
    surface's identifier: the walls through the grid's sides, up to the
    eaves, and each roof slope through the top of the cells under its half
    of its span. A grid's corner cell lies against two walls."""
    nx, ny, nz = grid.shape
    size = grid.cell_size
    air = ~solid

    def masked(index: tuple[slice | int | np.ndarray, ...]) -> np.ndarray:
        mask = np.zeros((nz, ny, nx), dtype=bool)
        mask[index] = True
        glazed: np.ndarray = mask & air
        return glazed

    every = slice(None)
    along, across, top = size.y * size.z, size.x * size.z, size.x * size.y
    surfaces = {
        "side_wall_right": GlazedCells(masked((every, 0, every)), across),
        "side_wall_left": GlazedCells(masked((every, -1, every)), across),
        "end_wall_front": GlazedCells(masked((every, every, 0)), along),
        "end_wall_back": GlazedCells(masked((every, every, -1)), along),
    }
    _, ys, _ = grid.centres()
    span = envelope.span_width
    for index in range(envelope.spans):
        start = index * span
        right = (ys >= start) & (ys < start + span / 2)
        left = (ys >= start + span / 2) & (ys < start + span)
        surfaces[f"roof_{index + 1}_right"] = GlazedCells(masked((-1, right, every)), top)
        surfaces[f"roof_{index + 1}_left"] = GlazedCells(masked((-1, left, every)), top)
    return surfaces


class SurfaceTemperature(BaseModel):
    """A glazed surface at a moment: the mean temperature of the air against
    it, its own temperature, and the heat it passes out of the house, in
    watts (negative in)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface_id: str
    air_c: float
    surface_c: float
    loss_w: float


class GlazingAt(BaseModel):
    """The glazing at a moment of a run: the outside's temperature, the
    glass's U in the wind, and each glazed surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_s: float
    outside_c: float
    u_w_m2k: float
    surfaces: list[SurfaceTemperature]


def glazing_at(
    glazed: Mapping[str, GlazedCells],
    temperature: np.ndarray,
    outside: WeatherState,
    configured_u: float,
    time_s: float,
) -> GlazingAt:
    """Each glazed surface's air, temperature and heat passed, for the air's
    `temperature` in every cell and the weather `outside`."""
    wind = outside.wind_speed_m_s
    u = glazing_u_w_m2k(configured_u, wind)
    outside_c = outside.air_temperature_c
    surfaces = []
    for surface_id, against in glazed.items():
        if not against.cells.any():
            continue
        air_c = float(temperature[against.cells].mean())
        loss_w = u * against.face_m2 * float((temperature[against.cells] - outside_c).sum())
        surfaces.append(
            SurfaceTemperature(
                surface_id=surface_id,
                air_c=air_c,
                surface_c=surface_temperature_c(air_c, outside_c, configured_u, wind),
                loss_w=loss_w,
            )
        )
    return GlazingAt(time_s=time_s, outside_c=outside_c, u_w_m2k=u, surfaces=surfaces)
