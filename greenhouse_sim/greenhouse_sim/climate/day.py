"""A climate run through a day (P07.3), the fidelity ladder applied.

- **The house's air through the day** is the whole house's
  (`climate.house`): one well-mixed volume, from the run's start, under its
  schedule and weather.
- **The field at a moment** is a grid run's (`climate.run`). Through the
  run's first two hours it is the grid run from the start. After them, it
  is a grid run started from the whole house's air, the same in every
  cell, an hour before the moment's hour began: an hour is enough for a
  small house's air to take its shape. A moment at 5:20 is drawn from a
  grid run started at 4:00, and so is every moment until 6:00, so that
  scrubbing within an hour carries one run on.
- **What sensors sample** has to be the same air however later a run is
  looked at: the grid run's from the start through its first two hours,
  and after them the whole house's, the same in every cell, in the flow
  the equipment makes then. The field a later grid run draws is not kept
  for every moment of a day.

A few of a day's later grid runs are kept, the latest asked for.
"""

import math
from collections import OrderedDict
from typing import Final

import numpy as np

from greenhouse_sim.climate.glazing import GlazingAt
from greenhouse_sim.climate.house import HouseAir, WholeHouse
from greenhouse_sim.climate.openings import OpeningsAt
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.transport import AirState
from greenhouse_sim.fields.field import EnvironmentField

HOUR_S: Final = 3600.0
# How long the grid run from the start is drawn, in seconds: its first two
# hours, after which the field comes from a later grid run.
FROM_THE_START_S: Final = 2 * HOUR_S
# How many of a day's later grid runs are kept.
KEPT_WINDOWS: Final = 3


def window_start(time_s: float) -> float:
    """When the grid run that draws the field at `time_s` starts: the start
    through the first two hours, and an hour before the moment's hour began
    after them."""
    return max(0.0, (math.floor(time_s / HOUR_S) - 1) * HOUR_S)


class ClimateDay:
    """A climate run through a day: its grid run from the start, the whole
    house it holds, and the later grid runs drawn from the whole house."""

    def __init__(self, run: ClimateRun) -> None:
        self.run = run
        self.house = WholeHouse(run)
        self._windows: OrderedDict[float, ClimateRun] = OrderedDict()

    def _uniform(self, air: HouseAir) -> AirState:
        shape = self.run.solid.shape
        return AirState(
            temperature=np.full(shape, air.temperature_c),
            humidity=np.full(shape, air.humidity_g_kg),
            co2=np.full(shape, air.co2_ppm),
            removed_kg=air.removed_kg,
            condensed_kg=air.condensed_kg,
        )

    def _started(self, start_s: float) -> ClimateRun:
        window = self._windows.get(start_s)
        if window is None:
            window = self.run.started_at(start_s, self._uniform(self.house.air_at(start_s)))
            self._windows[start_s] = window
            if len(self._windows) > KEPT_WINDOWS:
                self._windows.popitem(last=False)
        else:
            self._windows.move_to_end(start_s)
        return window

    def window(self, time_s: float) -> ClimateRun:
        """The grid run that draws the field at `time_s`."""
        start = window_start(time_s)
        return self.run if start == 0 else self._started(start)

    def field(self, field_id: str, time_s: float) -> EnvironmentField:
        """The air at `time_s`, cell by cell, as its grid run draws it."""
        return self.window(time_s).field(field_id, self.run.grid, time_s)

    def glazing_at(self, time_s: float) -> GlazingAt:
        """Each glazed surface at `time_s`, as the grid run that draws the
        field then has it."""
        return self.window(time_s).glazing_at(time_s)

    def openings_at(self, time_s: float) -> OpeningsAt:
        """What each open door and vent passes at `time_s`, as the grid run
        that draws the field then drives them."""
        window = self.window(time_s)
        flows = window.openings_for(window.air_at(time_s), window.weather.at(time_s))
        return OpeningsAt(time_s=time_s, openings=list(flows.values()))

    def sampled(self, field_id: str, time_s: float) -> EnvironmentField:
        """The air sensors sample at `time_s`: the grid run's from the start
        through its first two hours, the whole house's after them."""
        if time_s < FROM_THE_START_S:
            return self.run.field(field_id, self.run.grid, time_s)
        return self.run.field_of(self._uniform(self.house.air_at(time_s)), field_id, time_s)

    def carry_on_from(self, other: ClimateDay) -> None:
        """Take over what `other` has worked out up to the first moment its
        schedule and this day's differ: its grid run from the start, and its
        later grid runs, each from the same start."""
        self.run.carry_on_from(other.run)
        for start, theirs in other._windows.items():
            self._started(start).carry_on_from(theirs)
