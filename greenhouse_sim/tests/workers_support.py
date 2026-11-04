"""What the scheduler's tests run: a short run and a long one of the one-plant box
(`short_runs`), registered with a test's simulator, whose worker has them from the
store; workers that end at once or are killed, which a process imports by name;
and the wait for an epoch worked in a test's own process to be let go by it."""

import os
import signal
import threading
import time
from pathlib import Path
from typing import Final

import short_runs

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status
from greenhouse_sim.services.simulator import Simulator

SHORT: Final = "climate_box_short"
LONG: Final = "climate_box_long"
SHORT_DAYS: Final = 2
# Far longer than any test lets it go on: what a test does while it is running
# takes a few of its days, and a day takes a fraction of a second.
LONG_DAYS: Final = 120
# How often a test's own process writes the leases it holds (`leases.REFRESH_EVERY_S`),
# which lets `lease_let_go` wait for less than the five seconds it does by itself.
LEASE_BEAT_S: Final = 0.02
LEASE_WAIT_S: Final = 30.0


def short_simulator() -> Simulator:
    made = Simulator()
    for name, days in ((SHORT, SHORT_DAYS), (LONG, LONG_DAYS)):
        made.catalogue.register(short_runs.one_plant_box(name, days))
    return made


def ends_at_once(root: str, run_id: str, epoch: int) -> None:
    raise SystemExit(1)


def takes_it_up_and_is_killed(root: str, run_id: str, epoch: int) -> None:
    """A worker killed outright, with no chance to write why: its epoch is
    `running`, with one commit, as it left them."""
    kept = EpochStore(FolderStore(Path(root)), run_id, epoch)
    kept.set_status(Status.RUNNING)
    kept.commit(0.0, DAY_S)
    os.kill(os.getpid(), signal.SIGKILL)


def lease_let_go(epoch: EpochStore) -> None:
    """Waits until this process, having worked `epoch` here, no longer writes its
    lease. Its thread looks at the manifest only when it wakes: one still asleep as
    the epoch is queued to be carried on would take it to be worked, write the lease
    again, and have the worker refuse the epoch as worked by another."""
    name = f"lease of {epoch.run_id}/{epoch.epoch}"
    deadline = time.monotonic() + LEASE_WAIT_S
    while any(thread.name == name for thread in threading.enumerate()):
        assert time.monotonic() < deadline, f"waited for {name} to end"
        time.sleep(LEASE_BEAT_S)
