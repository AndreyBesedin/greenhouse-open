"""The states runs take over from checkpoints (P09.5,
`greenhouse_sim.services.checkpoints`).

A kept state is a run's state at the start of one of its days: its house's
air then, and an hour before, where the day's first hour draws its field
from, and its crop's plants then, of whichever model its rows grow, with
what each experienced on each day before. A run of the same house, under the same
weather, with the same doors and vents open from the start, whose schedule
agrees with the state's up to its moment, is the same run up to then
(`Schedule.same_until`), so it takes the state over in place of working its
days out again: a checkpoint's own run, restored, and a branch from it,
whose commands differ only from its moment on. Its crop is the same crop if
the run's own crop actions up to then are the state's too
(`crop_agrees`).

The climate's and the crop's services look here when they make a run; this
module looks at neither.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services.runs import CropPlan
from greenhouse_sim.services.stores import Store

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# A run's house: its scenario, layout and weather, by name, and its doors'
# and vents' openings from the start, sorted.
type House = tuple[str, str, str, tuple[tuple[str, float], ...]]


@dataclass(frozen=True)
class KeptState:
    """A run's state at the start of its day `day`: its house's air then,
    and its crop then with what it lived through; its run,
    `house` under `schedule`."""

    house: House
    schedule: Schedule
    day: int
    air: HouseAir
    # Its crop then, as a run's crop takes it back: its plants, or, grown
    # by area, its instances; and what each experienced on each day
    # before, by its name.
    crop: tuple[object, ...] = ()
    lived: tuple[Mapping[str, object], ...] = ()
    # Its house's air at moments before its day began, each with its moment:
    # where the field of the day's first hour starts its grid run.
    earlier: tuple[tuple[float, HouseAir], ...] = ()
    # Its run's own crop actions up to its day, its own included: what its
    # plants are the crop of.
    crop_actions: CropPlan = ()

    @property
    def moment_s(self) -> float:
        return self.day * DAY_S

    def airs(self) -> list[tuple[float, HouseAir]]:
        """Its house's air at each moment it keeps, the earliest first."""
        return [*self.earlier, (self.moment_s, self.air)]

    def agrees(self, house: House, schedule: Schedule) -> bool:
        """Whether a run of `house` under `schedule` is this state's run up
        to its moment."""
        return house == self.house and schedule.same_until(self.schedule) >= self.moment_s

    def crop_agrees(self, planned: CropPlan) -> bool:
        """Whether a run whose own crop actions are `planned`, and which is
        this state's run up to its moment, has this state's crop then."""
        return tuple(each for each in planned if each.at_s <= self.moment_s) == self.crop_actions


def new_store() -> Store[str, KeptState]:
    """A simulator's kept states (decision 0048), each kept as long as its
    checkpoint is."""
    return Store("kept states", label=str)


def keep(simulator: Simulator, key: str, state: KeptState) -> None:
    """Keep a state, under its checkpoint's identifier."""
    simulator.states.keep(key, state)


def drop(simulator: Simulator, key: str, state: KeptState) -> None:
    """Keep a checkpoint's state no longer: `state`, if it is still the one
    kept; not one kept since, as the same checkpoint uploaded again keeps."""
    simulator.states.drop(key, state)


def agreeing(simulator: Simulator, house: House, schedule: Schedule) -> list[KeptState]:
    """The kept states a run of `house` under `schedule` takes over, from
    its earliest day."""
    states = [state for _, state in simulator.states.values() if state.agrees(house, schedule)]
    return sorted(states, key=lambda s: s.day)
