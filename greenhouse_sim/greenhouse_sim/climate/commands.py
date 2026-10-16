"""Commands to the greenhouse's equipment, and the levels they leave it at.

A command sets one piece of equipment to a level, from 0 (off) to 1 (full),
at a moment of a climate run, in seconds from its start. Every piece starts
off. A schedule is the commands for a run; the viewer's manual changes are
commands too, at the moment they are made. Commands at the same moment
apply in the order they are given, so a later one wins.

Commands are data: the same schedule always leaves the same levels at the
same moments, and the log of a run (`applied`) is the commands it applied,
in order.

A daily command (P09.2) sets a level at a time of day, every day of a run:
a heater on every evening, a vent open every afternoon. It is a command at
that time on each of the run's days, before any other command at the same
moment, so that one given for that moment alone overrides it.
"""

import math
from bisect import bisect_right
from collections.abc import Iterable
from functools import cached_property
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, model_validator

from greenhouse_sim.core.clock import DAY_S

type Level = Annotated[float, Field(ge=0.0, le=1.0)]


class Command(BaseModel):
    """Set one piece of equipment to a level, at a moment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_s: NonNegativeFloat
    actuator_id: str
    level: Level


class DailyCommand(BaseModel):
    """Set one piece of equipment to a level at a time of day, every day of
    a run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_of_day_s: Annotated[float, Field(ge=0.0, lt=DAY_S)]
    actuator_id: str
    level: Level

    def through(self, days: int) -> list[Command]:
        """The command on each of a run's `days`, in order."""
        return [
            Command(
                time_s=day * DAY_S + self.time_of_day_s,
                actuator_id=self.actuator_id,
                level=self.level,
            )
            for day in range(days)
        ]


class Schedule(BaseModel):
    """The commands for a run, in the order they apply: by time, and in the
    order given at the same time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commands: list[Command] = []

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        times = [command.time_s for command in self.commands]
        if times != sorted(times):
            raise ValueError("commands must be in the order of their times")
        return self

    @classmethod
    def of(cls, commands: Iterable[Command]) -> Schedule:
        """A schedule of commands given in any order: sorted by time, keeping
        the given order at each time."""
        return cls(commands=sorted(commands, key=lambda command: command.time_s))

    @classmethod
    def from_start(cls, levels: dict[str, float]) -> Schedule:
        """Levels set at the start of a run, by actuator."""
        return cls(
            commands=[
                Command(time_s=0.0, actuator_id=actuator_id, level=level)
                for actuator_id, level in sorted(levels.items())
            ]
        )

    def unknown(self, actuator_ids: Iterable[str]) -> list[str]:
        """The actuators commanded that are not among `actuator_ids`."""
        known = set(actuator_ids)
        return sorted({c.actuator_id for c in self.commands} - known)

    # The schedule indexed by moment, worked out once: a run asks for its
    # levels at every step of a season, and a season's schedule holds
    # thousands of commands. A schedule is never changed, or copied with
    # changes, so the indexes stay its own.
    @cached_property
    def _times(self) -> list[float]:
        return [command.time_s for command in self.commands]

    @cached_property
    def _moments(self) -> list[float]:
        return sorted(set(self._times))

    @cached_property
    def _by_actuator(self) -> dict[str, tuple[list[float], list[float]]]:
        """Each actuator's commands' times and levels, in the order they
        apply."""
        index: dict[str, tuple[list[float], list[float]]] = {}
        for command in self.commands:
            times, levels = index.setdefault(command.actuator_id, ([], []))
            times.append(command.time_s)
            levels.append(command.level)
        return index

    def applied(self, until_s: float) -> list[Command]:
        """The commands a run applies up to and including `until_s`, in order:
        its log."""
        return self.commands[: bisect_right(self._times, until_s)]

    def commanded_levels(self, time_s: float) -> dict[str, float]:
        """The level each actuator commanded by `time_s` stands at: the last
        command's to it, at the latest moment up to `time_s`, or the last
        given at that moment. An actuator not yet commanded is left out."""
        levels = {}
        for actuator_id, (times, given) in self._by_actuator.items():
            applied = bisect_right(times, time_s)
            if applied:
                levels[actuator_id] = given[applied - 1]
        return levels

    def levels_at(self, actuator_ids: Iterable[str], time_s: float) -> dict[str, float]:
        """Each actuator's level at `time_s`: off, unless a command set it."""
        commanded = self.commanded_levels(time_s)
        return {actuator_id: commanded.get(actuator_id, 0.0) for actuator_id in actuator_ids}

    def moments(self) -> list[float]:
        """The moments commands are given at, in order."""
        return list(self._moments)

    def moments_between(self, after_s: float, until_s: float) -> list[float]:
        """The moments commands are given at after `after_s`, up to and
        including `until_s`, in order."""
        return self._moments[
            bisect_right(self._moments, after_s) : bisect_right(self._moments, until_s)
        ]

    def same_until(self, other: Schedule) -> float:
        """Up to when this schedule and `other` are the same: the moment of
        the first command one gives that the other does not give in its
        place, or infinity if they are the same throughout. A run under
        either is the same run up to and including it."""
        mine, theirs = self.commands, other.commands
        differing = next(
            (index for index, (a, b) in enumerate(zip(mine, theirs, strict=False)) if a != b),
            min(len(mine), len(theirs)),
        )
        moments = [command.time_s for command in (*mine[differing:], *theirs[differing:])]
        return min(moments, default=math.inf)
