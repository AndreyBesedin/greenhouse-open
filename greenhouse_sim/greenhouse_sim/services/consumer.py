"""What a consumer reads of the simulator's running scenarios (P10.4): the
consumer interface (`greenhouse_protocol.contracts.consumer`, decision
0040), served from the runs played back against a clock (`playback`,
decision 0041).

A run here is a playback: its identity is its run's, its epoch the
playback's, and its clock the playback's. A consumer reaches observed
records only: what the run's sensors delivered by the clock, and what
happened in it. Nothing here reads the run's truth, its model state, its
scene, or anything of QA mode; the consumer's routes reach the simulator
through this module alone, and a test holds both to that.

A cursor counts the records delivered in one epoch of one log. A cursor the
producer never gave in the current epoch, one kept from an epoch before, is
answered with an empty batch at the same position, so that a client sees
the epoch change and starts again from the beginning.
"""

import threading
from typing import Final

from greenhouse_protocol.contracts.consumer import (
    CONSUMER_PREFIX,
    FIRST_CURSOR,
    EventBatch,
    ObservationBatch,
    RunClock,
    RunDescriptor,
    RunList,
)
from greenhouse_protocol.enums import SourceType
from greenhouse_protocol.greenhouse import GreenhouseDescription, GreenhouseLayout, Plant

from greenhouse_sim.services import playback
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.playback import Playback, PlaybackState
from greenhouse_sim.services.scenarios import plant_ids, scenario

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


def runs() -> RunList:
    """The runs a consumer can follow: every playback started."""
    return RunList(runs=tuple(_descriptor(found.state()) for found in playback.playbacks()))


def _played(run_id: str) -> Playback:
    for found in playback.playbacks():
        if found.run_id == run_id:
            return found
    raise NotFound(f"no run {run_id!r}")


def run(run_id: str) -> RunDescriptor:
    """A run's identity, epoch and clock."""
    return _descriptor(_played(run_id).state())


def greenhouse(run_id: str) -> GreenhouseDescription:
    """The greenhouse a run describes: its plants, row by row, as the
    scenario lays them out, described when its run starts."""
    found = _played(run_id)
    config = scenario(found.scenario_id)
    plants = tuple(
        Plant(
            plant_id=plant_id,
            variety=config.variety,
            row=index // config.columns + 1,
            position_in_row=index % config.columns + 1,
        )
        for index, plant_id in enumerate(plant_ids(config))
    )
    return GreenhouseDescription(
        greenhouse_id=config.greenhouse_id,
        name=config.name,
        description=config.description,
        source_type=SourceType.SIMULATION,
        crop=config.variety,
        layout=GreenhouseLayout(kind="grid", rows=config.rows, columns=config.columns),
        plants=plants,
        created_at=found.start,
    )


class _Given:
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


_given = _Given()


def _limit(limit: int | None) -> int:
    if limit is None:
        return MOST_PER_BATCH
    if limit < 1:
        raise InvalidRequest("a batch's limit is 1 or more")
    return min(limit, MOST_PER_BATCH)


def observations(
    run_id: str, after: int | None = None, limit: int | None = None
) -> ObservationBatch:
    """The observations a run's sensors delivered after the cursor, by its
    clock, in delivery order, from the first if no cursor is given."""
    cursor = FIRST_CURSOR if after is None else after
    if cursor < FIRST_CURSOR:
        raise InvalidRequest("a cursor is 0 or more")
    found = _played(run_id)
    now = found.state()
    if not _given.knows(run_id, "observations", now.epoch, cursor):
        return ObservationBatch(
            run_id=run_id,
            epoch=now.epoch,
            after=cursor,
            next=cursor,
            simulated_now=now.simulated_now,
            observations=(),
        )
    cut = found.records_after(cursor, _limit(limit))
    _given.give(run_id, "observations", cut.state.epoch, cut.next)
    return ObservationBatch(
        run_id=run_id,
        epoch=cut.state.epoch,
        after=cursor,
        next=cut.next,
        simulated_now=cut.state.simulated_now,
        has_more=cut.has_more,
        observations=cut.records,
    )


def events(run_id: str, after: int | None = None, limit: int | None = None) -> EventBatch:
    """The events delivered in a run after the cursor, by its clock, in
    delivery order, from the first if no cursor is given: its crop's
    harvests."""
    cursor = FIRST_CURSOR if after is None else after
    if cursor < FIRST_CURSOR:
        raise InvalidRequest("a cursor is 0 or more")
    found = _played(run_id)
    now = found.state()
    if not _given.knows(run_id, "events", now.epoch, cursor):
        return EventBatch(
            run_id=run_id,
            epoch=now.epoch,
            after=cursor,
            next=cursor,
            simulated_now=now.simulated_now,
            events=(),
        )
    cut = found.events_after(cursor, _limit(limit))
    _given.give(run_id, "events", cut.state.epoch, cut.next)
    return EventBatch(
        run_id=run_id,
        epoch=cut.state.epoch,
        after=cursor,
        next=cut.next,
        simulated_now=cut.state.simulated_now,
        has_more=cut.has_more,
        events=cut.records,
    )
