"""Whether the long work a thread is doing is still wanted.

A thread cannot be stopped from outside, so a request whose client has gone
is given up by its own thread, at the places long work passes through
(`give_up_if_unwanted`): each step of a house's or a grid's air, whose steps
are kept, so that what was worked out stays for whoever asks next, and the
air at a moment is the same whatever was asked for before.

Only a thread that says what it is wanted by (`wanted_while`) can give up: a
worker, a playback and any other caller work on to the end, and what they work
out does not depend on this.
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Final

# How often a thread doing long work asks, in seconds: asking looks at a socket.
LOOK_EVERY_S: Final = 0.1


class NoLongerWanted(Exception):
    """Whoever asked for this work has gone."""


class _Asked(threading.local):
    """What the thread's work is wanted by, if anything says, and when to ask
    next."""

    still_wanted: Callable[[], bool] | None = None
    next_look_s: float = 0.0


_asked: Final = _Asked()


@contextmanager
def wanted_while(still_wanted: Callable[[], bool] | None) -> Iterator[None]:
    """This thread's work, within the block, is wanted while `still_wanted`
    says so, or to its end if it is None."""
    before = _asked.still_wanted
    _asked.still_wanted = still_wanted
    _asked.next_look_s = 0.0
    try:
        yield
    finally:
        _asked.still_wanted = before


def give_up_if_unwanted() -> None:
    """Raise `NoLongerWanted` if the thread's work has been let go, looking
    every `LOOK_EVERY_S` at most."""
    still_wanted = _asked.still_wanted
    if still_wanted is None:
        return
    now = time.monotonic()
    if now < _asked.next_look_s:
        return
    _asked.next_look_s = now + LOOK_EVERY_S
    if not still_wanted():
        raise NoLongerWanted
