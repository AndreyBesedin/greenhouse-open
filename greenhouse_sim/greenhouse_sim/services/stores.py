"""The services' kept values, in one kind of store (AUDIT.7, W9).

The services keep their latest climate runs, crops, sunlight, checkpoints,
the states runs take over from checkpoints, and the runs played back, each
in a `Store`: a bounded map behind its own lock. Making a value can take
long: building it, and carrying on from the others kept. Held across that,
the store's lock would stall every request for anything kept, of any
scenario (AUDIT.29). Here the lock is held only to find a value, or to put
the promise of one in its place; the request that put the promise makes the
value outside the lock, and others asking for the same one wait for it
alone.

No store's lock is held while another's is taken: what a store does with a
value it lets go, such as dropping a checkpoint's state or stopping a
playback, it does once its lock is released. So the stores have no lock
order to keep.

Every store is listed as it is made, so that `forget_everything` forgets
them all, as a test asks for a clean slate: the stores made last, which
build on those made before, first.

A store logs, at INFO, each value it makes, with how long it took and how
many related values it was made from, each it is given to keep, and each
it lets go, with why (AUDIT.14). Each record carries the store's name and
what happened (`store`, `event`), so that a test asks the log what was
made rather than reading a store's insides.
"""

import logging
import threading
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import Future
from typing import Any, Literal

from greenhouse_sim.digests import short_digest

logger = logging.getLogger(__name__)

# How many hexadecimal digits name a kept value in the log.
LABEL_DIGITS = 8

# Why a value was let go: past its store's bound, dropped by its service,
# or forgotten with everything else.
type LetGo = Literal["past the bound", "dropped", "forgotten"]


def _never(key: object) -> bool:
    return False


def digest_label(key: object) -> str:
    """A kept value's name in the log: a digest of its key, short, the same
    for the same key in any process."""
    return f"#{short_digest(repr(key), LABEL_DIGITS)}"


class Store[K: Hashable, V]:
    """Values kept by key, the latest `bound` of them, or all without one,
    beside those pinned, which are never let go but by `forget`; each let
    go is handed to `on_drop`, once the store's lock is released."""

    def __init__(
        self,
        name: str,
        bound: int | None = None,
        on_drop: Callable[[K, V], None] | None = None,
        label: Callable[[K], str] = digest_label,
    ) -> None:
        self.name = name
        self._bound = bound
        self._on_drop = on_drop
        self._label = label
        self._kept: OrderedDict[K, Future[V]] = OrderedDict()
        self._pinned: set[K] = set()
        self._lock = threading.Lock()
        with _LISTING:
            _STORES.append(weakref.ref(self))

    def made_once(
        self,
        key: K,
        make: Callable[[list[tuple[K, V]]], V],
        related: Callable[[K], bool] = _never,
    ) -> V:
        """The value kept for `key`, or a new one, which `make` makes from the
        others kept then that are `related` to it. A value whose making fails
        is not kept, and the request that made it and those waiting for it
        see why."""
        with self._lock:
            promised = self._kept.get(key)
            mine = promised is None
            if promised is None:
                others = [(other, value) for other, value in self._kept.items() if related(other)]
                promised = self._kept[key] = Future()
                dropped = self._over_bound()
            else:
                self._kept.move_to_end(key)
                dropped = []
        self._dropped(dropped, "past the bound")
        if not mine:
            return promised.result()
        started = time.perf_counter()
        try:
            from_kept = _made(others)
            value = make(from_kept)
        except BaseException as error:
            promised.set_exception(error)
            with self._lock:
                if self._kept.get(key) is promised:
                    del self._kept[key]
            raise
        promised.set_result(value)
        self._log(
            "made",
            key,
            f"in {time.perf_counter() - started:.2f} s, from {len(from_kept)} kept",
        )
        return value

    def keep(self, key: K, value: V, *, pinned: bool = False) -> None:
        """Keep `value` for `key`, in place of any kept, as the latest; a
        pinned one beside the `bound` latest, never in their place."""
        made: Future[V] = Future()
        made.set_result(value)
        with self._lock:
            self._kept[key] = made
            self._kept.move_to_end(key)
            if pinned:
                self._pinned.add(key)
            dropped = self._over_bound()
        self._log("kept", key, "pinned" if pinned else "")
        self._dropped(dropped, "past the bound")

    def get(self, key: K) -> V | None:
        """The value kept for `key`, once made, or None."""
        with self._lock:
            promised = self._kept.get(key)
        made = [] if promised is None else _made([(key, promised)])
        return made[0][1] if made else None

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._kept

    def values(self) -> list[tuple[K, V]]:
        """The values kept, each with its key, the least recently asked for
        first, once made; those whose making failed are left out."""
        with self._lock:
            promised = list(self._kept.items())
        return _made(promised)

    def drop(self, key: K, kept: V | None = None) -> None:
        """Let the value kept for `key` go, if one is: only if it is `kept`,
        when given, so that a drop told late leaves a value kept since."""
        with self._lock:
            promised = self._kept.get(key)
            if promised is None or (kept is not None and not _is(promised, kept)):
                return
            del self._kept[key]
            self._pinned.discard(key)
        self._dropped([(key, promised)], "dropped")

    def forget(self) -> None:
        """Let every value kept go, the pinned ones too."""
        with self._lock:
            dropped = list(self._kept.items())
            self._kept.clear()
            self._pinned.clear()
        self._dropped(dropped, "forgotten")

    def _over_bound(self) -> list[tuple[K, Future[V]]]:
        """Let go of the oldest unpinned values past the bound: under the lock."""
        if self._bound is None:
            return []
        dropped = []
        unpinned = [key for key in self._kept if key not in self._pinned]
        while len(unpinned) > self._bound:
            oldest = unpinned.pop(0)
            dropped.append((oldest, self._kept.pop(oldest)))
        return dropped

    def _dropped(self, dropped: list[tuple[K, Future[V]]], why: LetGo) -> None:
        """Log what was let go, by its key alone, and hand it to `on_drop`:
        outside the lock. Only `on_drop` waits for a value still being made."""
        for key, _ in dropped:
            self._log("let go", key, why)
        if self._on_drop is None:
            return
        for key, value in _made(dropped):
            self._on_drop(key, value)

    def _log(self, event: str, key: K, detail: str) -> None:
        label = self._label(key)
        logger.info(
            "%s: %s %s%s",
            self.name,
            event,
            label,
            f" ({detail})" if detail else "",
            extra={"store": self.name, "event": event, "label": label},
        )


# Every store made, as long as it lasts: the services' last as long as the
# process; one a test makes, as long as the test.
_STORES: list[weakref.ref[Store[Any, Any]]] = []
_LISTING = threading.Lock()


def forget_everything() -> None:
    """Let go of everything every store keeps, the stores made last first:
    the playbacks, which work days out from the runs kept, stop before the
    runs go."""
    with _LISTING:
        _STORES[:] = [listed for listed in _STORES if listed() is not None]
        stores = [listed() for listed in reversed(_STORES)]
    for store in stores:
        if store is not None:
            store.forget()


def _is[V](promised: Future[V], value: V) -> bool:
    """Whether a value promised has been made, and is `value` itself."""
    return promised.done() and promised.exception() is None and promised.result() is value


def _made[K: Hashable, V](promised: list[tuple[K, Future[V]]]) -> list[tuple[K, V]]:
    """The values promised, each once made: waiting for those being made,
    as a run carrying on from another being made waits for it; those whose
    making failed are left out."""
    made = []
    for key, value in promised:
        if value.exception() is None:
            made.append((key, value.result()))
    return made
