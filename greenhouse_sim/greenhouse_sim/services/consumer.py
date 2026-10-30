"""What a consumer reads of the simulator's running scenarios (P10.4): the
consumer interface (`greenhouse_protocol.contracts.consumer`, decision
0040), served from the runs played back against a clock (`playback`,
decision 0041).

A run here is a playback: its identity is its run's, its epoch the
playback's, and its clock the playback's. A consumer reaches observed
records only: what the run's sensors delivered by the clock, what happened
in it, and the outcomes of the actions its plans gave it (P13.3). Nothing
here reads the run's truth, its model state, its scene, or anything of QA
mode; the consumer's routes reach the simulator through this module alone,
and a test holds both to that.

A cursor counts the records delivered in one epoch of one log. A cursor the
producer never gave in the current epoch, one kept from an epoch before, is
answered with an empty batch at the same position, so that a client sees
the epoch change and starts again from the beginning.

What it reads is a simulator's (decision 0048), as `Reads` names it: the
runs it plays back, and the cursors it has given; nothing else of it.
"""

import threading
from typing import Final, Protocol

from greenhouse_protocol.contracts.consumer import (
    CONSUMER_PREFIX,
    FIRST_CURSOR,
    EventBatch,
    ObservationBatch,
    OutcomeBatch,
    RunClock,
    RunDescriptor,
    RunList,
)
from greenhouse_protocol.enums import SourceType
from greenhouse_protocol.greenhouse import GreenhouseDescription, GreenhouseLayout

from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.playback import Playback, Playbacks, PlaybackState
from greenhouse_sim.services.scenarios import Scenarios, described_plants, scenario

# The most records a batch holds, whatever a client asks for.
MOST_PER_BATCH: Final = 5_000
# Where the interface's routes live: `/consumer/v1`.
ROUTES_PREFIX: Final = CONSUMER_PREFIX


def _descriptor(state: PlaybackState) -> RunDescriptor:
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

    def forget(self) -> None:
        """Forget every cursor given."""
        with self._lock:
            self._given.clear()


class Reads(Protocol):
    """What a consumer reads of a simulator: the runs it plays back, the
    cursors it has given, and the scenarios their greenhouses are."""

    @property
    def playbacks(self) -> Playbacks: ...

    @property
    def catalogue(self) -> Scenarios: ...

    @property
    def cursors(self) -> Cursors: ...


def runs(reads: Reads) -> RunList:
    """The runs a consumer can follow: every playback started."""
    return RunList(runs=tuple(_descriptor(found.state()) for found in reads.playbacks.all()))


def _played(reads: Reads, run_id: str) -> Playback:
    return reads.playbacks.of_run(run_id)


def run(reads: Reads, run_id: str) -> RunDescriptor:
    """A run's identity, epoch and clock."""
    return _descriptor(_played(reads, run_id).state())


def greenhouse(reads: Reads, run_id: str) -> GreenhouseDescription:
    """The greenhouse a run describes: its plants, row by row, as the
    scenario lays them out, described when its run starts."""
    found = _played(reads, run_id)
    config = scenario(reads.catalogue, found.scenario_id)
    return GreenhouseDescription(
        greenhouse_id=config.greenhouse_id,
        name=config.name,
        description=config.description,
        source_type=SourceType.SIMULATION,
        crop=config.variety,
        layout=GreenhouseLayout(kind="grid", rows=config.rows, columns=config.columns),
        plants=described_plants(config),
        created_at=found.start,
    )


def _limit(limit: int | None) -> int:
    if limit is None:
        return MOST_PER_BATCH
    if limit < 1:
        raise InvalidRequest("a batch's limit is 1 or more")
    return min(limit, MOST_PER_BATCH)


def observations(
    reads: Reads, run_id: str, after: int | None = None, limit: int | None = None
) -> ObservationBatch:
    """The observations a run's sensors delivered after the cursor, by its
    clock, in delivery order, from the first if no cursor is given."""
    cursor = _cursor(after)
    cut = _played(reads, run_id).records_after(cursor, _limit(limit))
    # Judged by the epoch the records were cut in, which a restart between
    # a look at the epoch and the cut could not change.
    known = reads.cursors.knows(run_id, "observations", cut.state.epoch, cursor)
    if known:
        reads.cursors.give(run_id, "observations", cut.state.epoch, cut.next)
    return ObservationBatch(
        run_id=run_id,
        epoch=cut.state.epoch,
        after=cursor,
        next=cut.next if known else cursor,
        simulated_now=cut.state.simulated_now,
        has_more=cut.has_more if known else False,
        observations=cut.records if known else (),
    )


def events(
    reads: Reads, run_id: str, after: int | None = None, limit: int | None = None
) -> EventBatch:
    """The events delivered in a run after the cursor, by its clock, in
    delivery order, from the first if no cursor is given: its crop's
    harvests."""
    cursor = _cursor(after)
    cut = _played(reads, run_id).events_after(cursor, _limit(limit))
    known = reads.cursors.knows(run_id, "events", cut.state.epoch, cursor)
    if known:
        reads.cursors.give(run_id, "events", cut.state.epoch, cut.next)
    return EventBatch(
        run_id=run_id,
        epoch=cut.state.epoch,
        after=cursor,
        next=cut.next if known else cursor,
        simulated_now=cut.state.simulated_now,
        has_more=cut.has_more if known else False,
        events=cut.records if known else (),
    )


def outcomes(
    reads: Reads, run_id: str, after: int | None = None, limit: int | None = None
) -> OutcomeBatch:
    """The outcomes of a run's actions written after the cursor, by its
    clock, in the order written, from the first if no cursor is given: each
    action done, refused, cancelled or replaced, and why."""
    cursor = _cursor(after)
    cut, state = _played(reads, run_id).outcomes_after(cursor, _limit(limit))
    known = reads.cursors.knows(run_id, "outcomes", state.epoch, cursor)
    if known:
        reads.cursors.give(run_id, "outcomes", state.epoch, cut.next)
    return OutcomeBatch(
        run_id=run_id,
        epoch=state.epoch,
        after=cursor,
        next=cut.next if known else cursor,
        simulated_now=state.simulated_now,
        has_more=cut.has_more if known else False,
        outcomes=cut.outcomes if known else (),
    )


def _cursor(after: int | None) -> int:
    cursor = FIRST_CURSOR if after is None else after
    if cursor < FIRST_CURSOR:
        raise InvalidRequest("a cursor is 0 or more")
    return cursor
