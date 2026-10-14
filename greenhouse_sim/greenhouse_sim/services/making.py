"""A value kept in a bounded store, made once, outside the store's lock.

The services keep their latest runs and crops in module-level stores, each
behind a lock. Making a new one can take long: building it, and carrying on
from the others kept. Held across that, the store's lock would stall every
request for anything kept, of any scenario. Here the lock is held only to
find a value, or to put the promise of one in its place; the request that
put the promise makes the value outside the lock, and others asking for
the same one wait for it alone.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import Future

type Kept[K: Hashable, V] = OrderedDict[K, Future[V]]


def made_once[K: Hashable, V](
    kept: Kept[K, V],
    keeping: threading.Lock,
    key: K,
    bound: int,
    related: Callable[[K], bool],
    make: Callable[[list[tuple[K, V]]], V],
) -> V:
    """The value kept for `key`, or a new one, which `make` makes from the
    others kept then that are `related` to it. The store keeps the latest
    `bound` values. A value whose making fails is not kept, and the request
    that made it and those waiting for it see why."""
    with keeping:
        promised = kept.get(key)
        mine = promised is None
        if promised is None:
            others = [(other, value) for other, value in kept.items() if related(other)]
            promised = kept[key] = Future()
            while len(kept) > bound:
                kept.popitem(last=False)
        else:
            kept.move_to_end(key)
    if not mine:
        return promised.result()
    try:
        value = make(_made(others))
    except BaseException as error:
        promised.set_exception(error)
        with keeping:
            if kept.get(key) is promised:
                del kept[key]
        raise
    promised.set_result(value)
    return value


def kept_values[K: Hashable, V](kept: Kept[K, V], keeping: threading.Lock) -> list[tuple[K, V]]:
    """The values kept, each with its key, once made; those whose making
    failed are left out."""
    with keeping:
        promised = list(kept.items())
    return _made(promised)


def _made[K: Hashable, V](promised: list[tuple[K, Future[V]]]) -> list[tuple[K, V]]:
    made = []
    for key, value in promised:
        if value.exception() is None:
            made.append((key, value.result()))
    return made
