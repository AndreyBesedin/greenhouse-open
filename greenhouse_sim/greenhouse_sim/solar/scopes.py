"""The sun's light above each scope of a crop grown by area (P14.9,
decision 0062).

A crop grown by area has no crowns: its model works out how much of the
light above its canopy the canopy absorbs, through its leaf area. What the
run gives it is that light, incident and not absorbed:

- **A scope's PAR** at a moment is the mean of the PAR on a level surface
  `height_m` above each of its planting positions, the house's frames and
  fixtures in the way, in µmol/m²/s. The height is the canopy's, as its
  model's parameters give it, since a crop grown by area grows no height of
  its own. A canopy shades nothing of the house's light: a canopy
  intercepting its neighbours' is a capability no model has yet.
- **Its hours' PAR** is its PAR's mean through each hour of a day, summed
  every `DAY_EVERY_S` by the trapezoid rule, as a plant's daily light
  integral is (`greenhouse_sim.solar.plants`): an hour's mean is its
  integral over the hour, and a day's hours add up to the day's integral.
"""

from collections.abc import Sequence
from typing import Final

import numpy as np

from greenhouse_sim.solar.inside import UP, Sunlight
from greenhouse_sim.solar.plants import DAY_EVERY_S, END_WEIGHT, UMOL_PER_MOL
from greenhouse_sim.solar.sky import PAR_UMOL_M2_S_PER_W_M2
from greenhouse_sim.units import DAY_S, HOUR_S, HOURS_A_DAY
from greenhouse_sim.world.scopes import CropScope

# How many times an hour's light is summed: every `DAY_EVERY_S`, at both of
# its ends.
STEPS_AN_HOUR: Final = int(HOUR_S // DAY_EVERY_S)
# A point's coordinates.
_XYZ: Final = ("x", "y", "z")


class ScopeLight:
    """The light above each of `scopes`, `height_m` above their planting
    positions, under `sunlight`, which a crop grown by area does not
    shade."""

    def __init__(self, sunlight: Sunlight, scopes: Sequence[CropScope], height_m: float) -> None:
        self.sunlight = sunlight
        self.scopes = list(scopes)
        self.height_m = height_m
        points = [
            [position.point.x, position.point.y, position.point.z + height_m]
            for scope in self.scopes
            for position in scope.positions
        ]
        self._points = np.array(points).reshape(-1, len(_XYZ))
        self._counts = [len(scope.positions) for scope in self.scopes]
        self._hours: dict[int, dict[str, tuple[float, ...]]] = {}

    def par_at(self, time_s: float) -> dict[str, float]:
        """Each scope's PAR above its canopy `time_s` into the run, in
        µmol/m²/s."""
        if not self.scopes:
            return {}
        level = self.sunlight.irradiance(self._points, UP, time_s) * PAR_UMOL_M2_S_PER_W_M2
        ends = np.cumsum(self._counts)
        return {
            scope.scope_id: float(part.mean())
            for scope, part in zip(self.scopes, np.split(level, ends[:-1]), strict=True)
        }

    def hours_par(self, day: int) -> dict[str, tuple[float, ...]]:
        """Each scope's mean PAR above its canopy through each hour of the
        run's `day`th day, from 0, in µmol/m²/s."""
        kept = self._hours.get(day)
        if kept is not None:
            return kept
        start = day * DAY_S
        moments = [start + step * DAY_EVERY_S for step in range(HOURS_A_DAY * STEPS_AN_HOUR + 1)]
        read = [self.par_at(moment) for moment in moments]
        hours = {
            scope.scope_id: tuple(
                sum(
                    (END_WEIGHT if step in (0, STEPS_AN_HOUR) else 1.0)
                    * read[hour * STEPS_AN_HOUR + step][scope.scope_id]
                    for step in range(STEPS_AN_HOUR + 1)
                )
                / STEPS_AN_HOUR
                for hour in range(HOURS_A_DAY)
            )
            for scope in self.scopes
        }
        self._hours[day] = hours
        return hours

    def daily_light_integral(self, day: int) -> dict[str, float]:
        """Each scope's light integral above its canopy on the run's `day`th
        day, from 0, in mol/m²/d: its hours' PAR added up."""
        return {
            scope_id: sum(hours) * HOUR_S / UMOL_PER_MOL
            for scope_id, hours in self.hours_par(day).items()
        }
