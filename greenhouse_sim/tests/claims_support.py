"""What the tests of claims run in processes of their own, which a process imports
by its name: processes that race for an object or an epoch from a barrier, one that
is killed holding a claim, a worker that deletes its epoch, and a server to kill."""

import os
import signal
import threading
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path
from typing import Final

import workers_support

from greenhouse_sim.services import leases
from greenhouse_sim.services.run_store import EpochStore, FolderStore, delete_epoch
from greenhouse_sim.services.scheduler import LEFT_TO_ANOTHER, Scheduler
from greenhouse_sim.services.workers import Paced

LOOK_EVERY_S: Final = 0.05


def creates(root: str, rounds: int, ready: Barrier, won: Queue[tuple[int, int]]) -> None:
    """Asks for each round's object as the others do, and says which it made."""
    objects = FolderStore(Path(root))
    for number in range(rounds):
        ready.wait()
        if objects.create(f"race/{number}", str(os.getpid()).encode()):
            won.put((number, os.getpid()))


def claims(root: str, rounds: int, ready: Barrier, won: Queue[int]) -> None:
    """Claims each round's epoch as the others do, and says which it took."""
    objects = FolderStore(Path(root))
    for number in range(rounds):
        ready.wait()
        if EpochStore(objects, "run", number).claim():
            won.put(number)


def claims_and_is_killed(root: str, run_id: str, epoch: int) -> None:
    """A worker killed outright with the epoch claimed, as it left the store."""
    assert EpochStore(FolderStore(Path(root)), run_id, epoch).claim()
    os.kill(os.getpid(), signal.SIGKILL)


def deletes_its_epoch(root: str, run_id: str, epoch: int) -> None:
    """A worker whose epoch is deleted under it by another process."""
    delete_epoch(FolderStore(Path(root)), run_id, epoch)
    raise SystemExit(1)


def says_it_was_given(root: str, run_id: str, epoch: int) -> None:
    """A worker that leaves word that it was given an epoch, and ends at once."""
    FolderStore(Path(root)).put(f"given/{run_id}-{epoch}", b"")
    raise SystemExit(1)


def leaves_to_another(root: str, run_id: str, epoch: int) -> None:
    """A worker that finds a process holding the epoch: that process's claim is
    written here, and not again, as if that process died after this left."""
    assert leases.claim(FolderStore(Path(root)), f"{run_id}/{epoch}") == 0
    raise SystemExit(LEFT_TO_ANOTHER)


def a_server(root: str, told: Queue[tuple[str, int]], pace: float) -> None:
    """A server with one worker, computing a long run with a short one waiting, which
    says who is who once a day is kept and waits to be killed."""
    with workers_support.short_simulator() as simulator:
        simulator.runs = FolderStore(Path(root))
        made = Scheduler(simulator, Path(root), limit=1)
        simulator.scheduler = made
        computing = made.start(workers_support.LONG)
        waiting = made.start(workers_support.SHORT, driver=Paced(pace))
        epoch = EpochStore(simulator.runs, computing.run_id, computing.epoch)
        while not epoch.frontier_s():
            threading.Event().wait(LOOK_EVERY_S)
        (worker,) = made.workers()
        told.put((computing.run_id, computing.epoch))
        told.put((waiting.run_id, waiting.epoch))
        told.put(("worker", worker.pid))
        threading.Event().wait()
