"""The sun's and the sky's light inside the greenhouse (P08.3 to P08.7).

At a moment of a run, the light outside (`solar.sky`) under the sun where
it stands (`solar.position`) reaches each point inside through the glass
(`solar.glass`), unless something shades it (`solar.shadows`):

- **On a surface** facing the unit normal n, the beam's DNI times its cosine
  with the sun's direction s, max(n · s, 0), times the share the glass it
  crosses on its way passes, if nothing stands in its way; and the diffuse
  sky's DHI times the surface's view of the sky, (1 + n_z) / 2, times the
  glass's diffuse transmittance, less the share the roof's structure
  covers (`solar.shadows.roof_shading`). Light reflected from the ground is
  left out.
- **On a level surface** at each of a grid's cells' centres, as the climate
  run's field carries it: its shortwave irradiance in W/m², and its PAR in
  µmol/m²/s. Which cells the beam reaches unshaded is worked out once for
  the sun where it stands at each `SHADOW_EVERY_S` of a run, and kept: the
  sun moves about 1° in five minutes, and a shadow's edge a few
  centimetres for each metre between the solid and the cell.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import numpy as np

from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.solar.glass import DIFFUSE_TRANSMITTANCE, Glazing
from greenhouse_sim.solar.position import SunPosition, sun_position
from greenhouse_sim.solar.shadows import Shadows, roof_shading
from greenhouse_sim.solar.sky import PAR_UMOL_M2_S_PER_W_M2, OutsideLight, outside_light
from greenhouse_sim.weather.sources import RunWeather
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site

UP: Final = Vector3(x=0.0, y=0.0, z=1.0)
# How often the cells the beam reaches are worked out afresh, in seconds.
SHADOW_EVERY_S: Final = 300.0


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
    `site`, under `weather`, over `grid`, its beam shaded by `shadows`, or
    by nothing."""

    def __init__(
        self,
        site: Site,
        weather: RunWeather,
        grid: FieldGrid,
        envelope: Envelope,
        shadows: Shadows | None = None,
    ) -> None:
        self.site = site
        self.weather = weather
        self.grid = grid
        self.glazing = Glazing(envelope)
        self.shadows = shadows
        # The share of the diffuse sky that reaches inside, past the glass
        # and the roof's structure.
        self.diffuse_passed = DIFFUSE_TRANSMITTANCE * (1.0 - roof_shading(envelope))
        xs, ys, zs = grid.centres()
        z, y, x = np.meshgrid(zs, ys, xs, indexing="ij")
        self._centres = np.stack([x.ravel(), y.ravel(), z.ravel()], axis=1)
        self._lit: dict[int, np.ndarray] = {}

    def sun_at(self, time_s: float) -> SunPosition:
        """Where the sun stands `time_s` into the run."""
        return sun_position(self.weather.start + timedelta(seconds=time_s), self.site)

    def outside_at(self, time_s: float) -> OutsideLight:
        """The light outside `time_s` into the run."""
        moment = self.weather.start + timedelta(seconds=time_s)
        return outside_light(
            self.weather.at(time_s).global_radiation_w_m2, self.sun_at(time_s), moment
        )

    def _unshaded(self, points: np.ndarray, towards: Vector3) -> np.ndarray:
        if self.shadows is None:
            return np.ones(len(points), dtype=bool)
        return self.shadows.lit(points, towards)

    def cells_lit(self, time_s: float) -> np.ndarray:
        """Which of the grid's cells' centres, in the grid's order flattened,
        the beam reaches unshaded, as the sun stands at the `SHADOW_EVERY_S`
        nearest `time_s`."""
        step = round(time_s / SHADOW_EVERY_S)
        lit = self._lit.get(step)
        if lit is None:
            towards = self.sun_at(step * SHADOW_EVERY_S).direction(self.site)
            lit = self._unshaded(self._centres, towards)
            self._lit[step] = lit
        return lit

    def _irradiance(
        self,
        points: np.ndarray,
        normal: Vector3,
        time_s: float,
        lit: np.ndarray | None = None,
    ) -> np.ndarray:
        """The irradiance on surfaces facing `normal` at `points`, the beam
        reaching those `lit` says, or, if it says nothing, those nothing
        shades now."""
        light = self.outside_at(time_s)
        towards = self.sun_at(time_s).direction(self.site)
        beam = light.dni_w_m2 * max(_dot(normal, towards), 0.0)
        if beam > 0:
            reached = self._unshaded(points, towards) if lit is None else lit
            passed = np.where(reached, self.glazing.beam_transmittance(points, towards), 0.0)
        else:
            passed = np.zeros(len(points))
        return beam * passed + light.dhi_w_m2 * sky_view(normal) * self.diffuse_passed

    def irradiance(self, points: np.ndarray, normal: Vector3, time_s: float) -> np.ndarray:
        """The shortwave irradiance on surfaces at `points` (rows of x, y, z)
        inside, each facing the unit `normal`, `time_s` into the run, in
        W/m², each shaded exactly."""
        return self._irradiance(points, normal, time_s)

    def on(self, point: Vector3, normal: Vector3, time_s: float) -> float:
        """The shortwave irradiance on a surface at `point` inside, facing the
        unit `normal`, `time_s` into the run, in W/m²."""
        return float(self.irradiance(np.array([[point.x, point.y, point.z]]), normal, time_s)[0])

    def at(self, time_s: float) -> InsideLight:
        """The light on a level surface at each of the grid's cells' centres,
        `time_s` into the run."""
        nx, ny, nz = self.grid.shape
        lit = self.cells_lit(time_s) if self.sun_at(time_s).is_up() else None
        irradiance = self._irradiance(self._centres, UP, time_s, lit).reshape((nz, ny, nx))
        return InsideLight(
            time_s=time_s,
            irradiance_w_m2=irradiance,
            par_umol_m2_s=irradiance * PAR_UMOL_M2_S_PER_W_M2,
        )
