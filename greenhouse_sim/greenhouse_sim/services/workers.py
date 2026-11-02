"""A worker executes one epoch into the run store (P17.7, decision 0065).

`execute(simulator, epoch, driver)` works an epoch out, which has been
started in the store and is `queued`, and writes it there, a span at a time,
one commit each: the store is the only channel between the worker and whoever
reads the epoch. A reader (`stored_playback`) sees as far as the last commit
names, so that an epoch can be played over what is computed while it goes on.

The driver decides how the epoch advances:

- `Free`: as fast as it can be computed, a day at a time;
- `Paced`: by a clock at so many real seconds a simulated day, for a
  consumer on the wall clock; a day is written once the clock has passed it;
- `Stepped`: to the moments an experiment gives, in turn (decision 0061); it
  is in the caller's process, since the barriers come from the caller.

The epoch ends `finished`, `failed` or `interrupted`, as a played run's does.
"""

import logging
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import Conflict
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.playback import (
    DEFAULT_SECONDS_PER_DAY,
    FIRST_EPOCH,
    WAIT_STEP_S,
    Playback,
    PlaybackCommand,
    check_pace,
)
from greenhouse_sim.services.run_store import EpochManifest, EpochStore, ObjectStore, Status
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import layout_name, scenario
from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

# The statuses an epoch does not leave.
ENDED: Final = frozenset({Status.FINISHED, Status.FAILED, Status.INTERRUPTED})


@dataclass(frozen=True)
class Free:
    """Advances as fast as the epoch can be computed."""


@dataclass(frozen=True)
class Paced:
    """Advances by a clock, `seconds_per_day` real seconds to a simulated day."""

    seconds_per_day: float = DEFAULT_SECONDS_PER_DAY

    def __post_init__(self) -> None:
        check_pace(self.seconds_per_day)


@dataclass(frozen=True)
class Stepped:
    """Advances to each moment `barriers` gives, in seconds into the run, in
    turn, each no earlier than the one before; the epoch is interrupted if
    they end before the run does."""

    barriers: Iterable[float]


Driver = Free | Paced | Stepped


def queued(
    simulator: Simulator,
    objects: ObjectStore,
    scenario_id: str,
    *,
    layout: str | None = None,
    seed: int | None = None,
) -> EpochStore:
    """A new epoch of the run of `scenario_id` at `layout` and `seed`, in
    `objects`, `queued`: the run's next epoch, its manifest written. A
    scenario, a layout or a seed refused starts nothing. Whoever starts
    epochs of one store does it one at a time, so that two are never given a
    number."""
    config = scenario(simulator.catalogue, scenario_id)
    chosen = layout_name(layout or DEFAULT_LAYOUT)
    _, run_id = air_through_a_run(simulator, RunRequest(scenario_id, layout=chosen, seed=seed))
    started = stored_epochs(objects, run_id)
    return EpochStore.create(
        objects,
        EpochManifest(
            run_id=run_id,
            epoch=started[-1] + 1 if started else FIRST_EPOCH,
            scenario_id=scenario_id,
            seed=seed,
            layout=chosen,
            duration_s=config.duration_days * DAY_S,
            created_at=datetime.now(UTC),
        ),
    )


def execute(
    simulator: Simulator,
    epoch: EpochStore,
    driver: Driver | None = None,
    *,
    stop: threading.Event | None = None,
) -> Status:
    """Works `epoch` out into its store as `driver` advances it, and says how
    it ended. Told to `stop` between moments, it ends `interrupted`. An epoch
    is executed once: one that has begun is refused (resuming is another
    step), as is one whose run is not the one its manifest names."""
    driver = Free() if driver is None else driver
    manifest = epoch.manifest()
    if manifest.status != Status.QUEUED or epoch.commits():
        raise Conflict(f"epoch {epoch.epoch} of {epoch.run_id} has begun: it is {manifest.status}")
    stopping = threading.Event() if stop is None else stop
    run = Playback(
        simulator,
        manifest.scenario_id,
        layout=manifest.layout,
        seed=manifest.seed,
        seconds_per_day=driver.seconds_per_day
        if isinstance(driver, Paced)
        else DEFAULT_SECONDS_PER_DAY,
        epoch=epoch,
    )
    epoch.set_status(Status.RUNNING)
    try:
        if isinstance(driver, Paced):
            _paced(run, epoch, stopping)
        else:
            _stepped(
                run, epoch, _days(run) if isinstance(driver, Free) else driver.barriers, stopping
            )
    except Exception:
        logger.exception("the epoch %s of %s failed", epoch.epoch, epoch.run_id)
        epoch.set_status(Status.FAILED)
    status = epoch.manifest().status
    if status == Status.RUNNING:
        status = Status.INTERRUPTED
        epoch.set_status(status)
    return status


def _days(run: Playback) -> Iterable[float]:
    """The moments a free epoch is worked out to: the end of each day."""
    return (min((day + 1) * DAY_S, run.end_s) for day in range(round(run.end_s / DAY_S)))


def _stepped(
    run: Playback, epoch: EpochStore, barriers: Iterable[float], stopping: threading.Event
) -> None:
    """Works the epoch out to each barrier and writes the days it has passed,
    until the run ends (the epoch is finished by the last day written), the
    barriers do, or it is told to stop."""
    for barrier in barriers:
        if stopping.is_set():
            return
        run.step_to(barrier)
        run.keep()
        if epoch.manifest().status in ENDED:
            return


def _paced(run: Playback, epoch: EpochStore, stopping: threading.Event) -> None:
    """Lets the playback's own worker work the epoch out ahead of its clock,
    which plays at the pace, until it ends or it is told to stop."""
    run.begin()
    try:
        run.command(PlaybackCommand.PLAY)
        while epoch.manifest().status not in ENDED and not stopping.is_set():
            stopping.wait(WAIT_STEP_S)
    finally:
        run.stop()
