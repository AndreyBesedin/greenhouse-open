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
reads the store each time, and ends, clearing the lease, when the epoch is no
longer worked, whoever told it so.

A lease names its holder, a token `hold` makes, because a thread asleep outlives
the epoch's end in a process that goes on: one that wakes after the epoch was
queued to be carried on, or taken by another, finds no lease of its own, and ends
without writing. So a queued epoch is not worked as far as a thread goes, though
`interrupted` leaves one alone: it has no lease until its worker takes it up. A
lease an earlier version wrote names no one; `alive` believes it until it expires,
and no thread writes it again.

Reading a lease and writing it are two calls, as a store has no *create unless it
exists* yet (P18.4): a thread stopped between them, while the epoch ended and a new
holder took it, writes over that holder's lease and holds it from then on.
"""

import json
import logging
import threading
import time
import uuid
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
# What a manifest says of an epoch a thread keeps a lease for, as `Status` spells it.
_WORKED: Final = "running"


def _name(home: str) -> str:
    return f"{home}/{LEASE}"


def hold(objects: ObjectStore, home: str) -> None:
    """Takes the lease of the epoch kept under `home`, whoever held it: written
    now, and again every `REFRESH_EVERY_S` seconds until the epoch is no longer
    worked or the lease is another's."""
    holder = uuid.uuid4().hex
    _write(objects, home, holder)
    threading.Thread(
        target=_beat, args=(objects, home, holder), name=f"lease of {home}", daemon=True
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
    return manifest is not None and json.loads(manifest).get("status") == _WORKED


def _holds(objects: ObjectStore, home: str, holder: str) -> bool:
    data = objects.get(_name(home))
    if data is None:
        return False
    try:
        return bool(json.loads(data)["holder"] == holder)
    except ValueError, KeyError, TypeError:
        return False


def _write(objects: ObjectStore, home: str, holder: str) -> None:
    objects.put(_name(home), json.dumps({"refreshed_at": time.time(), "holder": holder}).encode())


def _beat(objects: ObjectStore, home: str, holder: str) -> None:
    """Writes the lease again while it is `holder`'s and the epoch is worked.
    Ends when the lease is not `holder`'s, leaving whatever is there, and when
    the epoch is not worked, clearing the lease."""
    while True:
        time.sleep(REFRESH_EVERY_S)
        try:
            if not _holds(objects, home, holder):
                return
            if _worked(objects, home):
                _write(objects, home, holder)
                # An end told before that write removed nothing it wrote, so it
                # is seen here; one told after it removes the lease itself.
                if _worked(objects, home):
                    continue
            # Read again: a new holder may have come since the epoch ended.
            if _holds(objects, home, holder):
                release(objects, home)
            return
        except Exception:
            # Whatever a write found wrong, the next one tries again; the
            # lease is the only thing this thread keeps.
            logger.exception("the lease of %s could not be written", home)
