"""Epochs found in the store that no one works (P17.9, decision 0065).

A producer that crashed leaves its epoch `running` in the store, or `queued` if
it never took it up. At startup, and when a person asks to carry one on, such
an epoch is told `interrupted` with what it had committed, so that it can be
resumed (`workers.resume`) and so that nothing reads it as still on its way.

An epoch is worked if a process holds its lease (`leases`), or this simulator's
scheduler holds it in its queue; a queued epoch is not leased, and one just
asked for is given `leases.EXPIRES_AFTER_S` seconds to be taken up. Nothing else
is believed: the worker of a server that was killed is a process of its own and
writes the epoch still, and it is no one's to take over.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from greenhouse_sim.services import leases
from greenhouse_sim.services.run_store import EpochStore, ObjectStore, Status, StoredRun, stored_run
from greenhouse_sim.services.run_store import epochs as stored_epochs

if TYPE_CHECKING:
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

_WORKED = (Status.QUEUED, Status.RUNNING)


def mark(simulator: Simulator, *, now: float | None = None) -> list[StoredRun]:
    """Tells `interrupted` every epoch of the simulator's run store that is
    `queued` or `running` and that no one works, and lists them. Only the
    epochs' manifests are read."""
    objects = simulator.runs
    if objects is None:
        return []
    found = []
    for run_id in objects.children():
        for number in stored_epochs(objects, run_id):
            told = _tell(simulator, objects, run_id, number, now)
            if told is not None:
                found.append(told)
    return found


def mark_epoch(
    simulator: Simulator, run_id: str, epoch: int, *, now: float | None = None
) -> StoredRun | None:
    """The same for one epoch: it as it is listed now if it was told
    `interrupted`, else none."""
    objects = simulator.runs
    if objects is None or epoch not in stored_epochs(objects, run_id):
        return None
    return _tell(simulator, objects, run_id, epoch, now)


def _tell(
    simulator: Simulator, objects: ObjectStore, run_id: str, number: int, now: float | None
) -> StoredRun | None:
    epoch = EpochStore(objects, run_id, number)
    manifest = epoch.manifest()
    if manifest.status not in _WORKED or _worked(simulator, epoch, now):
        return None
    if manifest.status == Status.QUEUED and _just_asked_for(manifest.created_at, now):
        return None
    if epoch.manifest().status not in _WORKED:
        # It ended while this looked.
        return None
    logger.warning(
        "epoch %d of %s was %s, with no one working it: interrupted",
        number,
        run_id,
        manifest.status,
    )
    epoch.set_status(Status.INTERRUPTED)
    return stored_run(objects, run_id, number)


def _worked(simulator: Simulator, epoch: EpochStore, now: float | None) -> bool:
    if epoch.worked(now=now):
        return True
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
