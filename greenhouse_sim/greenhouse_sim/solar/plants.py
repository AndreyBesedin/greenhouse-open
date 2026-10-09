"""The sun's light on each plant (P08.6).

- **Each plant's crown** is a cylinder about its stem, as tall as its
  visible stem and `CROWN_DIAMETER_M` across, standing at its planting
  position: it shades the light below and beside it (`solar.shadows`), as
  the frames and fixtures do.
- **Each plant's PAR** at a moment is the mean of the PAR on a level
  surface at its crown's top, at its middle and at `RIM_POINTS` points
  around it halfway out, with the other plants' crowns, the fixtures and
  the frames in the way; in µmol/m²/s.
- **Its daily light integral** is its PAR summed through a day, every
  `DAY_EVERY_S` from the day's start to its end, by the trapezoid rule, in
  mol/m²/d.
- **The plant model consumes it** (`SunlitEnvironment`): each plant's own
  daily light integral, in place of a preset's, through the plant model's
  `Environment` contract (decision 0024), the rest of its day as another
  environment says. The crowns stand as tall as on the run's first day
  through every later one: joining the crop's days to the climate run's
  seconds is P09's.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.solar.inside import UP, Sunlight
from greenhouse_sim.solar.sky import PAR_UMOL_M2_S_PER_W_M2
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Cylinder, Transform, Vector3
from greenhouse_sim.world.rows import PlantingPosition
from greenhouse_sim.world.state import PlantWorld

# A crown's width; how many points around its top, besides its middle, its
# light is the mean of, and how far out, as a share of its radius; and how
# far above its top they stand, so that its own crown does not shade them.
CROWN_DIAMETER_M: Final = 0.25
RIM_POINTS: Final = 6
RIM_SHARE: Final = 0.5
TOP_CLEARANCE_M: Final = 1e-3
# A day's light integral sums the light this often, in seconds, over a day,
# its first and last moments each half a step's worth, by the trapezoid rule.
DAY_EVERY_S: Final = 600.0
END_WEIGHT: Final = 0.5
DAY_S: Final = 86_400.0
UMOL_PER_MOL: Final = 1e6
METRES_PER_CENTIMETRE: Final = 0.01
# A point's coordinates.
_XYZ: Final = ("x", "y", "z")


@dataclass(frozen=True)
class Crown:
    """A plant's crown: a cylinder `height_m` tall standing on `base`, its
    stem's foot, in the world."""

    plant_id: str
    base: Vector3
    height_m: float

    def solid(self) -> tuple[Transform, Cylinder]:
        """The crown as a solid that shades."""
        return (
            Transform(position=self.base),
            Cylinder(radius=CROWN_DIAMETER_M / 2, height=self.height_m),
        )

    def top(self) -> np.ndarray:
        """The points on its top its light is the mean of, as rows."""
        reach = CROWN_DIAMETER_M / 2 * RIM_SHARE
        angles = [2 * math.pi * index / RIM_POINTS for index in range(RIM_POINTS)]
        z = self.base.z + self.height_m + TOP_CLEARANCE_M
        return np.array(
            [
                [self.base.x, self.base.y, z],
                *(
                    [self.base.x + reach * math.cos(a), self.base.y + reach * math.sin(a), z]
                    for a in angles
                ),
            ]
        )


def crowns(
    plants: Sequence[PlantWorld], positions: Sequence[PlantingPosition], envelope: Envelope
) -> list[Crown]:
    """Each plant's crown, the first plant at the first planting position,
    and so on, placed in the world: as tall as its visible stem; none for a
    plant with no stem showing."""
    placed = []
    for plant, position in zip(plants, positions, strict=False):
        height = (plant.stem_length_cm - plant.lowered_length_cm) * METRES_PER_CENTIMETRE
        if height > 0:
            placed.append(
                Crown(
                    plant_id=plant.plant_id,
                    base=envelope.to_world(position.point),
                    height_m=height,
                )
            )
    return placed


class PlantLight:
    """The light on each plant's crown, under `sunlight`, which its crowns'
    shadows should be among."""

    def __init__(self, sunlight: Sunlight, plant_crowns: Sequence[Crown]) -> None:
        self.sunlight = sunlight
        self.crowns = list(plant_crowns)
        tops = [crown.top() for crown in self.crowns]
        self._points = np.concatenate(tops) if tops else np.zeros((0, len(_XYZ)))
        self._integrals: dict[int, dict[str, float]] = {}

    def par_at(self, time_s: float) -> dict[str, float]:
        """Each plant's PAR `time_s` into the run, in µmol/m²/s."""
        if not self.crowns:
            return {}
        level = self.sunlight.irradiance(self._points, UP, time_s) * PAR_UMOL_M2_S_PER_W_M2
        means = level.reshape(len(self.crowns), -1).mean(axis=1)
        return {crown.plant_id: float(mean) for crown, mean in zip(self.crowns, means, strict=True)}

    def daily_light_integral(self, day: int = 0) -> dict[str, float]:
        """Each plant's daily light integral on the run's `day`th day, from
        0, in mol/m²/d."""
        kept = self._integrals.get(day)
        if kept is not None:
            return kept
        steps = int(DAY_S // DAY_EVERY_S)
        start = day * DAY_S
        totals = dict.fromkeys((crown.plant_id for crown in self.crowns), 0.0)
        for step in range(steps + 1):
            weight = END_WEIGHT if step in (0, steps) else 1.0
            for plant_id, par in self.par_at(start + step * DAY_EVERY_S).items():
                totals[plant_id] += weight * par * DAY_EVERY_S / UMOL_PER_MOL
        self._integrals[day] = totals
        return totals


class SunlitEnvironment:
    """The plant model's environment where each plant's light is its own,
    as `light` gives it, and the rest of its day as `rest` says."""

    def __init__(self, light: PlantLight, rest: LocalEnvironment) -> None:
        self.light = light
        self.rest = rest

    def local(self, plant_id: str, day: int) -> LocalEnvironment:
        """What the plant experiences on this day: its own light."""
        integral = self.light.daily_light_integral(day).get(plant_id)
        if integral is None:
            raise LookupError(f"no plant {plant_id!r} under this light")
        return self.rest.model_copy(update={"par_mol_m2_day": integral})
