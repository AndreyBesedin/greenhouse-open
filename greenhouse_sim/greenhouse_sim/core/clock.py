"""A run's clock (P09.2): its moments are seconds from its start, its start
date's midnight at its site (P07.1), and its days are that clock's days.

A moment belongs to the day it lies in, or, at a midnight, to the day it
ends: the end of a run's first day, 86 400 s, is still its day 0, as the
end of its last day is still its last. So a day is a span from its
midnight, exclusive unless it is the first, to the next, inclusive, and a
run of `d` days has days 0 to `d − 1`, whatever moment of it is asked for.

Its crop lives each day at the midnight that ends it, so at the end of a
run's first day its crop has lived one day, though the moment is still the
day's (`days_ended`).
"""

import math

# A day's length is the simulator's unit; the clock's users find it here.
from greenhouse_sim.units import DAY_S as DAY_S


def run_day(time_s: float) -> int:
    """The day of a run a moment belongs to: the one it lies in, or ends."""
    return max(0, math.ceil(time_s / DAY_S) - 1)


def day_start(time_s: float) -> float:
    """When the day a moment belongs to began, in seconds from the run's
    start."""
    return run_day(time_s) * DAY_S


def days_ended(time_s: float) -> int:
    """How many of a run's days have ended by a moment, at it or before: the
    days its crop has lived (`greenhouse_sim.core.crop`), as its plants live
    each at the midnight that ends it."""
    return math.floor(time_s / DAY_S)
