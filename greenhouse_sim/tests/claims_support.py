"""What the tests of claims run in processes of their own, which a process imports
by its name: processes that race for an object or an epoch from a barrier, one that
is killed holding a claim, and one that leaves its epoch to another."""

import os
import signal
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from pathlib import Path

from greenhouse_sim.services import leases
from greenhouse_sim.services.run_store import EpochStore, FolderStore
from greenhouse_sim.services.scheduler import LEFT_TO_ANOTHER


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


def leaves_to_another(root: str, run_id: str, epoch: int) -> None:
    """A worker that finds a process holding the epoch: that process's claim is
    written here, and not again, as if that process died after this left."""
    assert leases.claim(FolderStore(Path(root)), f"{run_id}/{epoch}") == 0
    raise SystemExit(LEFT_TO_ANOTHER)
