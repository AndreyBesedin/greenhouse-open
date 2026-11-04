"""Epochs found in the store that no one works (P17.9, decision 0065).

A producer that crashed leaves its epoch `running` in the store, or `queued` if
it never took it up. At startup, and when a person asks to carry one on, such
an epoch is told `interrupted` with what it had committed, so that it can be
resumed (`workers.resume`) and so that nothing reads it as still on its way. One
a scheduler put in line waits again, in the queue of the scheduler that starts
after it (`scheduler.restore`), and is that scheduler's to tell.

An epoch is worked if a process holds its claim (`leases`), or this simulator's
scheduler holds it in its queue; one just asked for is given
`leases.EXPIRES_AFTER_S` seconds to be taken up. Nothing else
is believed: the worker of a server that was killed is a process of its own and
writes the epoch still, and it is no one's to take over.

A server started within that time of a crash finds the claim still fresh, so the
epochs it leaves alone at startup are looked at again until each has ended or
has no one working it (`watch`).

Telling an epoch `interrupted` is itself a claim on it, held for that write
(`EpochStore.end_unless_worked`), so that no lock across processes is needed: of a
worker taking the epoch up and this, whichever claims it first has it.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from greenhouse_sim.services import leases
from greenhouse_sim.services.run_store import EpochStore, ObjectStore, Status, StoredRun, stored_run
from greenhouse_sim.services.run_store import epochs as stored_epochs

if TYPE_CHECKING:
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

_WORKED: Final = (Status.QUEUED, Status.RUNNING)
# How often the epochs left alone at startup are looked at again.
RECHECK_EVERY_S: float = 5.0


@dataclass(frozen=True)
class Scan:
    """What a look at the store found: the epochs told `interrupted`, and the
    epochs left alone for now because someone works them, or may be about to."""

    told: list[StoredRun]
    left: list[tuple[str, int]]


def scan(simulator: Simulator, *, now: float | None = None) -> Scan:
    """Tells `interrupted` every epoch of the simulator's run store that is
    `queued` or `running` and that no one works. Only the epochs' manifests are
    read."""
    objects = simulator.runs
    if objects is None:
        return Scan([], [])
    told, left = [], []
    for run_id in objects.children():
        for number in stored_epochs(objects, run_id):
            found, waiting = _tell(simulator, objects, run_id, number, now)
            if found is not None:
                told.append(found)
            if waiting:
                left.append((run_id, number))
    return Scan(told, left)


def mark(simulator: Simulator, *, now: float | None = None) -> list[StoredRun]:
    """The epochs `scan` told `interrupted`."""
    return scan(simulator, now=now).told


def watch(simulator: Simulator) -> None:
    """Scans the store, and looks again at the epochs it left alone, in a
    thread of its own, until each has ended, has been told `interrupted` or the
    simulator is closed: a server started soon after a crash finds the lease
    of the epoch it left fresh, and no start would find it again."""
    left = scan(simulator).left
    if left:
        threading.Thread(
            target=_watch, args=(simulator, left), name="interrupted epochs", daemon=True
        ).start()


def _watch(simulator: Simulator, left: list[tuple[str, int]]) -> None:
    objects = simulator.runs
    while left and objects is not None and not simulator.closed:
        time.sleep(RECHECK_EVERY_S)
        if simulator.closed:
            return
        try:
            left = [key for key in left if _tell(simulator, objects, key[0], key[1], None)[1]]
        except Exception:
            # The next look tries again; what is left alone stays so meanwhile.
            logger.exception("the epochs left alone at startup could not be looked at again")


def mark_epoch(
    simulator: Simulator, run_id: str, epoch: int, *, now: float | None = None
) -> StoredRun | None:
    """The same for one epoch: it as it is listed now if it was told
    `interrupted`, else none."""
    objects = simulator.runs
    if objects is None or epoch not in stored_epochs(objects, run_id):
        return None
    return _tell(simulator, objects, run_id, epoch, now)[0]


def _tell(
    simulator: Simulator, objects: ObjectStore, run_id: str, number: int, now: float | None
) -> tuple[StoredRun | None, bool]:
    """The epoch as listed if it was told `interrupted`; and whether it was
    left alone because someone works it or may be about to."""
    epoch = EpochStore(objects, run_id, number)
    manifest = epoch.manifest()
    if manifest.status not in _WORKED:
        return None, False
    if _worked(simulator, epoch, now):
        return None, not _with_scheduler(simulator, epoch)
    if manifest.status == Status.QUEUED and _just_asked_for(manifest.created_at, now):
        return None, True
    if not epoch.end_unless_worked(Status.INTERRUPTED, now=now):
        return None, epoch.manifest().status in _WORKED
    logger.warning(
        "epoch %d of %s was %s, with no one working it: interrupted",
        number,
        run_id,
        manifest.status,
    )
    return stored_run(objects, run_id, number), False


def _worked(simulator: Simulator, epoch: EpochStore, now: float | None) -> bool:
    return epoch.worked(now=now) or _with_scheduler(simulator, epoch)


def _with_scheduler(simulator: Simulator, epoch: EpochStore) -> bool:
    """Whether the simulator's scheduler holds the epoch, and so says what becomes
    of it: it need not be looked at again."""
    scheduler = simulator.scheduler
    if scheduler is None:
        return False
    key = (epoch.run_id, epoch.epoch)
    return key in scheduler.waiting() or any(
        (worker.run_id, worker.epoch) == key for worker in scheduler.workers()
    )


def _just_asked_for(created_at: datetime | None, now: float | None) -> bool:
    """Whether an epoch was started so lately that its worker may be starting."""
    if created_at is None:
        return False
    at = datetime.fromtimestamp(now, UTC) if now is not None else datetime.now(UTC)
    return (at - created_at).total_seconds() <= leases.EXPIRES_AFTER_S
