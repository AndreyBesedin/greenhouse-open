"""A scenario's run's timeline (P09.2, `greenhouse_sim.core.timeline`), as
the API serves it: asked for as its climate is, in a window of a day at
most, by default the day of the moment asked for.

Its events are written column by column, in the order they happen: each
one's moment, and the index of its process, subject and kind in the lists
of those, so that a day's thousands of samples stay small.
"""

from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.house import STEP_S
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.timeline import TURNS, RunProcesses, events
from greenhouse_sim.domain.processes import Process
from greenhouse_sim.scenarios.catalogue import Scenarios
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import run_schedule
from greenhouse_sim.services.runs import RunRequest, checked_window
from greenhouse_sim.services.scenarios import SceneChanges, changed, plant_ids, scenario
from greenhouse_sim.world.sensors import Camera, PointSensor

# The longest window a timeline is asked for: a day's.
LONGEST_WINDOW_S: Final = DAY_S


class TimelineDocument(BaseModel):
    """A run's events from `from_s` to `until_s`, in the order they happen,
    column by column."""

    model_config = ConfigDict(frozen=True)

    from_s: float
    until_s: float
    # The processes in the order they take their turns at a moment, and the
    # subjects and kinds of the events, each listed once.
    processes: list[str]
    subjects: list[str]
    kinds: list[str]
    times_s: list[float]
    process: list[int]
    subject: list[int]
    kind: list[int]


def timeline(
    catalogue: Scenarios, run: RunRequest, until_s: float = 0.0, from_s: float | None = None
) -> TimelineDocument:
    """A run's events from `from_s`, by default the start of the day
    `until_s` belongs to (`services.runs`), to `until_s`: with one of its
    scenario's layouts, its equipment at its levels from the start, then as
    its daily commands and its commands set it, checked as its climate's
    are. A window longer than a day is refused."""
    config = changed(
        catalogue,
        scenario(catalogue, run.scenario_id),
        SceneChanges(layout=run.layout or DEFAULT_LAYOUT),
    )
    first = checked_window(config, from_s, until_s)
    if until_s - first > LONGEST_WINDOW_S:
        raise InvalidRequest(
            f"a timeline's window is a day at most, {LONGEST_WINDOW_S:.15g} s, not "
            f"{until_s - first:.15g}"
        )
    processes = RunProcesses(
        schedule=run_schedule(catalogue, run),
        air_step_s=STEP_S if config.layout.equipment else None,
        plants=plant_ids(config),
        sensors=[sensor for sensor in config.layout.sensors if isinstance(sensor, PointSensor)],
        cameras=[sensor for sensor in config.layout.sensors if isinstance(sensor, Camera)],
        crop_work=config.crop_work,
    )
    found = events(processes, first, until_s)
    subjects = list(dict.fromkeys(event.subject for event in found))
    kinds = list(dict.fromkeys(event.kind for event in found))
    subject_at = {subject: index for index, subject in enumerate(subjects)}
    kind_at = {kind: index for index, kind in enumerate(kinds)}
    return TimelineDocument(
        from_s=first,
        until_s=until_s,
        processes=[process.value for process in Process],
        subjects=subjects,
        kinds=kinds,
        times_s=[event.time_s for event in found],
        process=[TURNS[event.process] for event in found],
        subject=[subject_at[event.subject] for event in found],
        kind=[kind_at[event.kind] for event in found],
    )
