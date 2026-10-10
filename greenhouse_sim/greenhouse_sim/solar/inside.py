"""The sun's and the sky's light inside the greenhouse (P08.3, P08.4).

At a moment of a run, the light outside (`solar.sky`) under the sun where
it stands (`solar.position`) reaches each point inside through the glass
(`solar.glass`):

- **On a surface** facing the unit normal n, the beam's DNI times its cosine
  with the sun's direction s, max(n · s, 0), times the share the glass it
  crosses on its way passes; and the diffuse sky's DHI times the surface's
  view of the sky, (1 + n_z) / 2, times the glass's diffuse transmittance.
  Light reflected from the ground is left out.
- **On a level surface** at each of a grid's cells' centres, as the climate
  run's field carries it: its shortwave irradiance in W/m², and its PAR in
  µmol/m²/s.

What shades it (P08.5) comes next.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import numpy as np

from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.solar.glass import DIFFUSE_TRANSMITTANCE, Glazing
from greenhouse_sim.solar.position import SunPosition, sun_position
from greenhouse_sim.solar.sky import PAR_UMOL_M2_S_PER_W_M2, OutsideLight, outside_light
from greenhouse_sim.weather.sources import RunWeather
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site

UP: Final = Vector3(x=0.0, y=0.0, z=1.0)


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


def sky_view(normal: Vector3) -> float:
    """The share of the sky a surface facing the unit `normal` sees."""
    return (1.0 + normal.z) / 2.0


class Sunlight:
    """The light inside a house, its envelope `envelope`, through a run, at
    `site`, under `weather`, over `grid`."""

    def __init__(
        self, site: Site, weather: RunWeather, grid: FieldGrid, envelope: Envelope
    ) -> None:
        self.site = site
        self.weather = weather
        self.grid = grid
        self.glazing = Glazing(envelope)
        xs, ys, zs = grid.centres()
        z, y, x = np.meshgrid(zs, ys, xs, indexing="ij")
        self._centres = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)

    def sun_at(self, time_s: float) -> SunPosition:
        """Where the sun stands `time_s` into the run."""
        return sun_position(self.weather.start + timedelta(seconds=time_s), self.site)

    def outside_at(self, time_s: float) -> OutsideLight:
        """The light outside `time_s` into the run."""
        moment = self.weather.start + timedelta(seconds=time_s)
        return outside_light(
            self.weather.at(time_s).global_radiation_w_m2, self.sun_at(time_s), moment
        )

    def _irradiance(self, points: np.ndarray, normal: Vector3, time_s: float) -> np.ndarray:
        light = self.outside_at(time_s)
        towards = self.sun_at(time_s).direction(self.site)
        beam = light.dni_w_m2 * max(_dot(normal, towards), 0.0)
        passed = (
            self.glazing.beam_transmittance(points, towards) if beam > 0 else np.zeros(len(points))
        )
        return beam * passed + light.dhi_w_m2 * sky_view(normal) * DIFFUSE_TRANSMITTANCE

    def on(self, point: Vector3, normal: Vector3, time_s: float) -> float:
        """The shortwave irradiance on a surface at `point` inside, facing the
        unit `normal`, `time_s` into the run, in W/m²."""
        return float(self._irradiance(np.array([[point.x, point.y, point.z]]), normal, time_s)[0])

    def at(self, time_s: float) -> InsideLight:
        """The light on a level surface at each of the grid's cells' centres,
        `time_s` into the run."""
        nx, ny, nz = self.grid.shape
        irradiance = self._irradiance(self._centres, UP, time_s).reshape((nz, ny, nx))
        return InsideLight(
            time_s=time_s,
            irradiance_w_m2=irradiance,
            par_umol_m2_s=irradiance * PAR_UMOL_M2_S_PER_W_M2,
        )
