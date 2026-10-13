"""The states runs take over from checkpoints (P09.5,
`greenhouse_sim.services.checkpoints`).

A kept state is a run's state at the start of one of its days: its house's
air then, and its organ-level crop's plants then, with what each
experienced on each day before. A run of the same house, under the same
weather, with the same doors and vents open from the start, whose schedule
agrees with the state's up to its moment, is the same run up to then
(`Schedule.same_until`), so it takes the state over in place of working its
days out again: a checkpoint's own run, restored, and a branch from it,
whose commands differ only from its moment on.

The climate's and the crop's services look here when they make a run; this
module looks at neither.
"""

import threading
from dataclasses import dataclass

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import DAY_S

# A run's house: its scenario, layout and weather, by name, and its doors'
# and vents' openings from the start, sorted.
type House = tuple[str, str, str, tuple[tuple[str, float], ...]]


@dataclass(frozen=True)
class KeptState:
    """A run's state at the start of its day `day`: its house's air then,
    and its crop's plants then with what they lived through, none where it
    grows no organ-level crop; its run, `house` under `schedule`."""

    house: House
    schedule: Schedule
    day: int
    air: HouseAir
    plants: tuple[Plant, ...] = ()
    lived: tuple[dict[str, LocalEnvironment], ...] = ()

    @property
    def moment_s(self) -> float:
        return self.day * DAY_S

    def agrees(self, house: House, schedule: Schedule) -> bool:
        """Whether a run of `house` under `schedule` is this state's run up
        to its moment."""
        return house == self.house and schedule.same_until(self.schedule) >= self.moment_s


_STATES: dict[str, KeptState] = {}
_KEEPING = threading.Lock()


def keep(key: str, state: KeptState) -> None:
    """Keep a state, under its checkpoint's identifier."""
    with _KEEPING:
        _STATES[key] = state


def drop(key: str) -> None:
    """Keep a checkpoint's state no longer."""
    with _KEEPING:
        _STATES.pop(key, None)


def agreeing(house: House, schedule: Schedule) -> list[KeptState]:
    """The kept states a run of `house` under `schedule` takes over, from
    its earliest day."""
    with _KEEPING:
        states = list(_STATES.values())
    return sorted((state for state in states if state.agrees(house, schedule)), key=lambda s: s.day)
