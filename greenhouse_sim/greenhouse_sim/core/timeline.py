"""A run's timeline (P09.2): what each of its processes does, and when, in
a window of the run, in the order it happens.

- **Commands** (`greenhouse_sim.climate.commands`) at their moments, each
  an event; a daily command's on each of the run's days.
- **The house's air** (`greenhouse_sim.climate.house`), worked on in
  stretches of at most a minute, each ending at a minute's end or at a
  command's moment: an event at the end of each, where the run works a
  climate.
- **Each plant's day** at each midnight, from that day's air and light; and
  then, at the start of a day its crop work does something, what it does
  to each plant (`greenhouse_sim.core.crop`): a harvest round, then a
  lowering round.
- **Each sensor's samples** and **each camera's frames**, every
  `cadence_s` from the run's start: the samples taken, whether or not a
  sample drops out or arrives late.

At a moment, the processes take their turns in that order: commands, then
the air, then the plants, then the sensors, then the cameras, so that an
observation at a moment sees what changed at it. Within a process, its
subjects take theirs in the order the run lists them.

The timeline is enumerated from the cadences and the commands, so nothing
is kept to draw it, and the same run always has the same events, in the
same order. A window holds the moments after its start, or at it if it is
the run's start, up to and including its end: a day's window is that
day's moments, as on the run's clock (`greenhouse_sim.core.clock`).
"""

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Final

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import CropWork
from greenhouse_sim.domain.processes import Process
from greenhouse_sim.world.sensors import Camera, PointSensor

TURNS: Final = {process: turn for turn, process in enumerate(Process)}
# The house's air, worked on as one subject.
HOUSE: Final = "house"
# What a harvest round, and a lowering round, does to each plant.
HARVEST_ROUND: Final = "harvest round"
LOWERING_ROUND: Final = "lowering round"


@dataclass(frozen=True, slots=True)
class Event:
    """One thing a process does at a moment, to its subject: a command sets
    a level ("set to 0.5"), the house's air is worked on ("step"), a plant
    grows a day ("day 3"), is harvested ("harvest round") or lowered
    ("lowering round"), a sensor
    samples ("sample"), a camera takes a frame ("frame")."""

    time_s: float
    process: Process
    subject: str
    kind: str


@dataclass(frozen=True)
class RunProcesses:
    """What a run's timeline is enumerated from: its commands, how often its
    house's air is worked on at most, or None where the run works no
    climate, its plants, sensors and cameras, each in its order, and the
    work it does on its crop."""

    schedule: Schedule
    air_step_s: float | None
    plants: Sequence[str]
    sensors: Sequence[PointSensor]
    cameras: Sequence[Camera]
    crop_work: CropWork = field(default_factory=CropWork)


def within(moment: float, from_s: float, until_s: float) -> bool:
    """Whether a moment lies in a window: after its start, or at it if it
    is the run's start, up to and including its end."""
    return from_s < moment <= until_s or moment == from_s == 0.0


def _every(cadence_s: float, from_s: float, until_s: float) -> Iterator[float]:
    """Each multiple of `cadence_s` in a window, counted from the run's
    start."""
    first = 0 if from_s == 0.0 else math.floor(from_s / cadence_s) + 1
    for index in range(first, math.floor(until_s / cadence_s) + 1):
        yield index * cadence_s


def events(run: RunProcesses, from_s: float, until_s: float) -> list[Event]:
    """Every event of a run in a window, in the order they happen."""
    found = [
        Event(command.time_s, Process.COMMANDS, command.actuator_id, f"set to {command.level:g}")
        for command in run.schedule.commands
        if within(command.time_s, from_s, until_s)
    ]
    if run.air_step_s is not None:
        # No stretch of the air's ends at the run's start.
        ends = {moment for moment in _every(run.air_step_s, from_s, until_s) if moment > 0.0}
        ends |= {
            moment
            for moment in run.schedule.moments()
            if moment > 0.0 and within(moment, from_s, until_s)
        }
        found.extend(Event(moment, Process.AIR, HOUSE, "step") for moment in sorted(ends))
    for midnight in _every(DAY_S, from_s, until_s):
        if midnight > 0.0:
            starting = round(midnight / DAY_S)
            grown = f"day {starting - 1}"
            found.extend(Event(midnight, Process.PLANTS, plant, grown) for plant in run.plants)
            for round_kind, due in (
                (HARVEST_ROUND, run.crop_work.harvests_on(starting)),
                (LOWERING_ROUND, run.crop_work.lowers_on(starting)),
            ):
                if due:
                    found.extend(
                        Event(midnight, Process.PLANTS, plant, round_kind) for plant in run.plants
                    )
    for sensor in run.sensors:
        found.extend(
            Event(moment, Process.SENSORS, sensor.sensor_id, "sample")
            for moment in _every(sensor.cadence_s, from_s, until_s)
        )
    for camera in run.cameras:
        found.extend(
            Event(moment, Process.CAMERAS, camera.sensor_id, "frame")
            for moment in _every(camera.cadence_s, from_s, until_s)
        )
    # A stable sort: within a process at a moment, its subjects keep their
    # order.
    found.sort(key=lambda event: (event.time_s, TURNS[event.process]))
    return found
