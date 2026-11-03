"""Who is working an epoch (P17.9, decision 0065).

An epoch the store calls `running` is worked by a process, and that process may
be gone: killed, or its machine stopped. The store alone cannot tell, since a
status is only what its writer last said. So a process that says an epoch runs
also holds its *lease*, an object beside the epoch's manifest that it writes
again every `REFRESH_EVERY_S` seconds from a thread of its own, for as long as
the manifest says the epoch is worked. An epoch `running` whose lease has not
been written for `EXPIRES_AFTER_S` seconds (or has none) has no one working it.

A lease and not a process id, because the worker of a server that was killed
is a process of its own and goes on writing the epoch: its lease stays fresh,
and a server started after it must not take the epoch over. Not a check that a
process lives either, which says nothing about whether it is the one that
works the epoch. The two clocks are one: the store is a folder on one machine.

The lease is held when an epoch is told `running` and let go when it is told
it ended (`EpochStore.set_status`), so that a producer need do nothing else.
Whoever says an epoch was interrupted (the scheduler, finding its worker dead)
clears the lease of the process that died. The thread keeps no registry: it
reads the manifest each time, and ends, clearing the lease, when the epoch is
no longer worked, whoever told it so.
"""

import json
import logging
import threading
import time
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from greenhouse_sim.services.run_store import ObjectStore

logger = logging.getLogger(__name__)

LEASE: Final = "lease.json"
# How often a process writes the leases it holds, and how long a lease not
# written is believed: a few missed writes, since a thread may wait on a long
# computation that holds the interpreter.
REFRESH_EVERY_S: float = 5.0
EXPIRES_AFTER_S: Final = 30.0
# What a manifest says of an epoch that is worked on, as `Status` spells it.
_WORKED: Final = ("queued", "running")


def _name(home: str) -> str:
    return f"{home}/{LEASE}"


def hold(objects: ObjectStore, home: str) -> None:
    """Takes the lease of the epoch kept under `home`: written now, and again
    every `REFRESH_EVERY_S` seconds until the epoch is no longer worked."""
    _write(objects, home)
    threading.Thread(
        target=_beat, args=(objects, home), name=f"lease of {home}", daemon=True
    ).start()


def release(objects: ObjectStore, home: str) -> None:
    """Lets go of the lease of the epoch under `home`, whoever held it: the
    object is removed, so that an epoch told it ended is never mistaken for
    one that is worked until the lease would have expired."""
    objects.delete(_name(home))


def alive(objects: ObjectStore, home: str, *, now: float | None = None) -> bool:
    """Whether the epoch under `home` has a lease written lately."""
    data = objects.get(_name(home))
    if data is None:
        return False
    try:
        refreshed = float(json.loads(data)["refreshed_at"])
    except ValueError, KeyError, TypeError:
        return False
    return (time.time() if now is None else now) - refreshed <= EXPIRES_AFTER_S


def _worked(objects: ObjectStore, home: str) -> bool:
    manifest = objects.get(f"{home}/manifest.json")
    return manifest is not None and json.loads(manifest).get("status") in _WORKED


def _write(objects: ObjectStore, home: str) -> None:
    objects.put(_name(home), json.dumps({"refreshed_at": time.time()}).encode())


def _beat(objects: ObjectStore, home: str) -> None:
    """Writes the lease again while the epoch is worked; clears it, and ends,
    when it is not."""
    while True:
        time.sleep(REFRESH_EVERY_S)
        try:
            if not _worked(objects, home):
                release(objects, home)
                return
            _write(objects, home)
        except Exception:
            # Whatever a write found wrong, the next one tries again; the
            # lease is the only thing this thread keeps.
            logger.exception("the lease of %s could not be written", home)
