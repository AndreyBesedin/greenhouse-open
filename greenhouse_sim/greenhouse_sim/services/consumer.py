"""The consumer interface's cursors and batches (`greenhouse_protocol.contracts.
consumer`, decision 0040), as the simulator's in-process services read a run by
them: the policy's port (`policy_port`, `policy_requests`) and a stored epoch's
records (`runs_kept`).

A cursor counts the records delivered in one epoch of one log. A cursor the
producer never gave in the current epoch, one kept from an epoch before, is
answered with an empty batch at the same position, so that a client sees
the epoch change and starts again from the beginning.

The simulator no longer serves the consumer interface over HTTP, nor reads a
run by its identifier for a consumer (decision 0074): the protocol's contract
describes what a producer implements.
"""

import threading
from typing import Final

from greenhouse_protocol.contracts.consumer import (
    FIRST_CURSOR,
    RunClock,
    RunDescriptor,
)

from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.playback import PlaybackState

# The most records a batch holds, whatever a client asks for.
MOST_PER_BATCH: Final = 5_000


def run_descriptor(state: PlaybackState) -> RunDescriptor:
    return RunDescriptor(
        run_id=state.run_id,
        epoch=state.epoch,
        greenhouse_id=state.greenhouse_id,
        scenario=state.scenario_id,
        started_at=state.started_at,
        clock=RunClock(simulated_now=state.simulated_now, day=state.day, playing=state.playing),
    )


class Cursors:
    """The cursors given in each log of each run, in its current epoch."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._given: dict[tuple[str, str], tuple[int, set[int]]] = {}

    def knows(self, run_id: str, log: str, epoch: int, cursor: int) -> bool:
        with self._lock:
            held = self._given.get((run_id, log))
            return cursor == FIRST_CURSOR or (
                held is not None and held[0] == epoch and cursor in held[1]
            )

    def give(self, run_id: str, log: str, epoch: int, cursor: int) -> None:
        with self._lock:
            held = self._given.get((run_id, log))
            if held is None or held[0] != epoch:
                held = (epoch, set())
                self._given[(run_id, log)] = held
            held[1].add(cursor)


def batch_limit(limit: int | None) -> int:
    if limit is None:
        return MOST_PER_BATCH
    if limit < 1:
        raise InvalidRequest("a batch's limit is 1 or more")
    return min(limit, MOST_PER_BATCH)


def batch_cursor(after: int | None) -> int:
    cursor = FIRST_CURSOR if after is None else after
    if cursor < FIRST_CURSOR:
        raise InvalidRequest("a cursor is 0 or more")
    return cursor
