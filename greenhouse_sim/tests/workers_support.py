"""What the scheduler's tests run: a short run and a long one of the one-plant box
(`short_runs`), registered with a test's simulator, whose worker has them from the
store; and workers that end at once or are killed, which a process imports by name."""

import os
import signal
import time
from pathlib import Path
from typing import Final

import short_runs

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services.run_store import EpochStore, FolderStore, ObjectStore, Status
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Stepped, execute, queued

SHORT: Final = "climate_box_short"
LONG: Final = "climate_box_long"
SHORT_DAYS: Final = 2
# Far longer than any test lets it go on: what a test does while it is running
# takes a few of its days, and a day takes a fraction of a second.
LONG_DAYS: Final = 120
PRIORITY_SAID: Final = "priority.txt"


def short_simulator() -> Simulator:
    made = Simulator()
    for name, days in ((SHORT, SHORT_DAYS), (LONG, LONG_DAYS)):
        made.catalogue.register(short_runs.one_plant_box(name, days))
    return made


def with_one_day_committed(simulator: Simulator, objects: ObjectStore) -> EpochStore:
    """An epoch of the short run stopped after its first day, `interrupted`."""
    epoch = queued(simulator, objects, SHORT)
    execute(simulator, epoch, Stepped([DAY_S]))
    return epoch


def holds_its_place(root: str, run_id: str, epoch: int) -> None:
    """A worker that computes nothing and is there until it is ended."""
    while True:
        time.sleep(1.0)


def works_and_says_its_priority(root: str, run_id: str, epoch: int) -> None:
    """A worker as any is, which writes its priority beside the store as it ends."""
    from greenhouse_sim.services.scheduler import work

    try:
        work(root, run_id, epoch)
    finally:
        priority = str(os.getpriority(os.PRIO_PROCESS, 0))
        EpochStore(FolderStore(Path(root)), run_id, epoch).objects.put(
            PRIORITY_SAID, priority.encode()
        )


def ends_at_once(root: str, run_id: str, epoch: int) -> None:
    raise SystemExit(1)


def takes_it_up_and_is_killed(root: str, run_id: str, epoch: int) -> None:
    """A worker killed outright, with no chance to write why: its epoch is
    `running`, with one commit, as it left them."""
    kept = EpochStore(FolderStore(Path(root)), run_id, epoch)
    kept.set_status(Status.RUNNING)
    kept.commit(0.0, DAY_S)
    os.kill(os.getpid(), signal.SIGKILL)
