"""Commands to the greenhouse's equipment, and the levels they leave it at.

A command sets one piece of equipment to a level, from 0 (off) to 1 (full),
at a moment of a climate run, in seconds from its start. Every piece starts
off. A schedule is the commands for a run; the viewer's manual changes are
commands too, at the moment they are made. Commands at the same moment
apply in the order they are given, so a later one wins.

Commands are data: the same schedule always leaves the same levels at the
same moments, and the log of a run (`applied`) is the commands it applied,
in order.
"""

from collections.abc import Iterable
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, model_validator

type Level = Annotated[float, Field(ge=0.0, le=1.0)]


class Command(BaseModel):
    """Set one piece of equipment to a level, at a moment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_s: NonNegativeFloat
    actuator_id: str
    level: Level


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

    def applied(self, until_s: float) -> list[Command]:
        """The commands a run applies up to and including `until_s`, in order:
        its log."""
        return [command for command in self.commands if command.time_s <= until_s]

    def levels_at(self, actuator_ids: Iterable[str], time_s: float) -> dict[str, float]:
        """Each actuator's level at `time_s`: off, unless a command set it."""
        levels = dict.fromkeys(actuator_ids, 0.0)
        for command in self.applied(time_s):
            if command.actuator_id in levels:
                levels[command.actuator_id] = command.level
        return levels

    def moments(self) -> list[float]:
        """The moments commands are given at, in order."""
        return sorted({command.time_s for command in self.commands})
