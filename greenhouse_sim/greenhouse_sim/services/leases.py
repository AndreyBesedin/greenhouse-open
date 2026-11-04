"""Who is working an epoch (P17.9 and P18.4, decisions 0065 and 0067).

An epoch the store calls `running` is worked by a process, and that process may
be gone: killed, or its machine stopped. The store alone cannot tell, since a
status is only what its writer last said. So a process that works an epoch first
*claims* it, and holds the claim by writing it again every `REFRESH_EVERY_S`
seconds from a thread of its own, for as long as the manifest says the epoch is
waiting or worked. An epoch whose newest claim has not been written for
`EXPIRES_AFTER_S` seconds (or that has none) has no one working it.

A claim and not a process id, because the worker of a server that was killed is
a process of its own and goes on writing the epoch: its claim stays fresh, and a
server started after it must not take the epoch over. Not a check that a process
lives either, which says nothing about whether it is the one that works the
epoch. The two clocks are one: the store is a folder on one machine.

Claims are numbered objects beside the epoch's manifest, `leases/{number}.json`,
each made with the store's `create`, which is all that decides between processes:

- To claim, a process reads the newest claim and, if it is not fresh, creates the
  next number. Of any number of processes that read the same claim, the store tells
  one that it made the next. One that read an older claim finds its number taken.
  A number is never made free while the epoch is kept, so this holds however late
  a process comes, and a claim that expired blocks no one: a crash costs
  `EXPIRES_AFTER_S` seconds, and no one has to remove what it left.
- A holder writes only the object of its own number. A thread stopped between
  reading and writing, whose claim has been let go or taken over, writes where no
  one reads, since only the newest claim is believed, and ends when it next looks.
- To let go is to create the next number with no time in it. The holder's thread
  cannot write over that, and it fails only for a claim that is no longer the
  newest, when there is nothing to let go of.

So the numbers an epoch has used stay until it is deleted: two small objects each
time it is worked, which no commit names and so no digest holds.

A claim is taken by `EpochStore.claim` before anything is done to the epoch, or
when it is told `running` by a process that took none, and let go when it is told
it ended (`EpochStore.set_status`), so that a producer need do nothing else.
Whoever says an epoch was interrupted (the scheduler, finding its worker dead) lets
go of the claim of the process that died. The thread keeps no registry: it reads the
store each time, and ends when its claim is not the newest; it lets go, and ends,
when the epoch has ended, whoever told it so.

An epoch from before claims may have a `lease.json`, which a worker of that version
writes again. It is believed until it expires, as a claim is, and goes when the
epoch's claim is let go.
"""

import json
import logging
import threading
import time
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from greenhouse_sim.services.run_store import ObjectStore

logger = logging.getLogger(__name__)

# The one object a holder wrote before claims were numbered.
LEASE: Final = "lease.json"
CLAIMS: Final = "leases"
_NUMBER_DIGITS: Final = 8
# How often a process writes the claims it holds, and how long a claim not
# written is believed: a few missed writes, since a thread may wait on a long
# computation that holds the interpreter.
REFRESH_EVERY_S: float = 5.0
EXPIRES_AFTER_S: Final = 30.0
# What a manifest says of an epoch a thread keeps a claim for, as `Status` spells
# them. Waiting too: a worker claims an epoch before it says it runs.
_WORKED: Final = ("queued", "running")
_LET_GO: Final = b"{}"


def _name(home: str, number: int) -> str:
    return f"{home}/{CLAIMS}/{number:0{_NUMBER_DIGITS}d}.json"


def _written_now() -> bytes:
    return json.dumps({"refreshed_at": time.time()}).encode()


def newest(objects: ObjectStore, home: str) -> int | None:
    """The number of the epoch's newest claim, or none if it was never claimed."""
    names = objects.names(f"{home}/{CLAIMS}/")
    found = (name.rpartition("/")[2].removesuffix(".json") for name in names)
    return max((int(number) for number in found if number.isdigit()), default=None)


def _fresh(data: bytes | None, at: float) -> bool:
    """Whether what a holder wrote says it was written lately. One let go says no
    time, and an object that is not one says nothing."""
    if data is None:
        return False
    try:
        return at - float(json.loads(data)["refreshed_at"]) <= EXPIRES_AFTER_S
    except ValueError, KeyError, TypeError:
        return False


def _believed(objects: ObjectStore, home: str, number: int | None, at: float) -> bool:
    if _fresh(objects.get(f"{home}/{LEASE}"), at):
        return True
    return number is not None and _fresh(objects.get(_name(home, number)), at)


def alive(objects: ObjectStore, home: str, *, now: float | None = None) -> bool:
    """Whether the epoch under `home` has a claim written lately."""
    at = time.time() if now is None else now
    return _believed(objects, home, newest(objects, home), at)


def claim(objects: ObjectStore, home: str, *, now: float | None = None) -> int | None:
    """Claims the epoch under `home` unless a process holds it: its number if this
    call took it, or none. Nothing writes it again until `keep` is called. The number
    tried is the one after the claim found not to be fresh, read once, so that a
    claim made since takes that number and this call is refused."""
    at = time.time() if now is None else now
    read = newest(objects, home)
    if _believed(objects, home, read, at):
        return None
    number = 0 if read is None else read + 1
    return number if objects.create(_name(home, number), _written_now()) else None


def keep(objects: ObjectStore, home: str, number: int) -> None:
    """Writes the claim `number` again every `REFRESH_EVERY_S` seconds, until it is
    not the newest or the epoch has ended."""
    threading.Thread(
        target=_beat, args=(objects, home, number), name=f"lease of {home}", daemon=True
    ).start()


def release(objects: ObjectStore, home: str, number: int | None = None) -> None:
    """Lets go of the claim `number` of the epoch under `home`, or of its newest,
    whoever holds it, so that an epoch told it ended is never mistaken for one that
    is worked until the claim would have expired."""
    objects.delete(f"{home}/{LEASE}")
    held = newest(objects, home) if number is None else number
    if held is not None and objects.get(_name(home, held)) != _LET_GO:
        objects.create(_name(home, held + 1), _LET_GO)


def _worked(objects: ObjectStore, home: str) -> bool:
    manifest = objects.get(f"{home}/manifest.json")
    return manifest is not None and json.loads(manifest).get("status") in _WORKED


def _beat(objects: ObjectStore, home: str, number: int) -> None:
    """Writes the claim `number` again while it is the newest and the epoch is
    worked. Whatever happens after it looks, its write reaches only this claim's
    own object, where it does no harm."""
    while True:
        time.sleep(REFRESH_EVERY_S)
        try:
            if newest(objects, home) != number:
                return
            if not _worked(objects, home):
                release(objects, home, number)
                return
            objects.put(_name(home, number), _written_now())
        except Exception:
            # Whatever a write found wrong, the next one tries again; the
            # claim is the only thing this thread keeps.
            logger.exception("the claim on %s could not be written", home)
