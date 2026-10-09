"""The sun's and the sky's light inside the greenhouse (P08.3).

At a moment of a run, the light outside (`solar.sky`) under the sun where
it stands (`solar.position`) reaches each point inside:

- **On a surface** facing the unit normal n, the beam's DNI times its cosine
  with the sun's direction s, max(n · s, 0), and the diffuse sky's DHI
  times the surface's view of the sky, (1 + n_z) / 2. Light reflected from
  the ground is left out.
- **On a level surface** at each of a grid's cells' centres, as the climate
  run's field carries it: its shortwave irradiance in W/m², and its PAR in
  µmol/m²/s.

For now the light reaches every point as it is outside: the glass (P08.4)
and what shades it (P08.5) come next.
"""

from dataclasses import dataclass
from datetime import timedelta

import numpy as np

from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.solar.position import SunPosition, sun_position
from greenhouse_sim.solar.sky import PAR_UMOL_M2_S_PER_W_M2, OutsideLight, outside_light
from greenhouse_sim.weather.sources import RunWeather
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site


@dataclass(frozen=True, eq=False)
class InsideLight:
    """The light on a level surface at each of a grid's cells' centres at a
    moment: its shortwave irradiance, in W/m², and its PAR, in µmol/m²/s,
    each in the grid's order (z, y, x)."""

    time_s: float
    irradiance_w_m2: np.ndarray
    par_umol_m2_s: np.ndarray


def _dot(a: Vector3, b: Vector3) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


class Sunlight:
    """The light inside a house through a run, at `site`, under `weather`,
    over `grid`."""

    def __init__(self, site: Site, weather: RunWeather, grid: FieldGrid) -> None:
        self.site = site
        self.weather = weather
        self.grid = grid

    def sun_at(self, time_s: float) -> SunPosition:
        """Where the sun stands `time_s` into the run."""
        return sun_position(self.weather.start + timedelta(seconds=time_s), self.site)

    def outside_at(self, time_s: float) -> OutsideLight:
        """The light outside `time_s` into the run."""
        moment = self.weather.start + timedelta(seconds=time_s)
        return outside_light(
            self.weather.at(time_s).global_radiation_w_m2, self.sun_at(time_s), moment
        )

    def on(self, normal: Vector3, time_s: float, point: Vector3 | None = None) -> float:
        """The shortwave irradiance on a surface facing the unit `normal`,
        at `point` inside, `time_s` into the run, in W/m²; for now, the same
        at every point."""
        light = self.outside_at(time_s)
        towards = self.sun_at(time_s).direction(self.site)
        return (
            light.dni_w_m2 * max(_dot(normal, towards), 0.0)
            + light.dhi_w_m2 * (1.0 + normal.z) / 2.0
        )

    def at(self, time_s: float) -> InsideLight:
        """The light on a level surface at each of the grid's cells' centres,
        `time_s` into the run."""
        level = self.on(Vector3(x=0.0, y=0.0, z=1.0), time_s)
        nx, ny, nz = self.grid.shape
        irradiance = np.full((nz, ny, nx), level)
        return InsideLight(
            time_s=time_s,
            irradiance_w_m2=irradiance,
            par_umol_m2_s=irradiance * PAR_UMOL_M2_S_PER_W_M2,
        )
