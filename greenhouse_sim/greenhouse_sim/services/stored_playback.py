"""A stored epoch played back as a position (P17.4, decision 0065).

An epoch kept in the run store (`run_store`) is read through a `StoredEpoch`:
its descriptor, how far it is committed (its frontier), and the records it
delivered by a moment, counted in the epoch's logs as a consumer counts them.
A `Position` is where a viewer stands over one: at or before the frontier,
playing at a pace, paused, seeking to any moment up to the frontier, or
following the frontier as it advances. It is not a clock the epoch keeps: any
number of positions read one epoch, none changes it, and a seek is never a new
epoch (so a viewer that scrubs moves nothing a consumer reads). An epoch still
computing is played over what is computed; a position waits at its frontier.

The scene at a position is drawn on demand, as the viewer's by-moment services
draw any moment of a run: for the run the epoch's manifest names (`run`).
Seeking restores the nearest checkpoint the store holds into the simulator's
kept states, so that those services take the state over instead of working the
days before it out again; a checkpoint made by another version of the
scenario or its models is not restored, and the days are worked out. The changes
given to the epoch are in its log (P17.8), and its scene is drawn under the plan
they made, as the checkpoint at its frontier keeps it: what it carried out by
then, whatever it was refused, and whoever may do what on the simulator reading
it. A position stands at or before the frontier, so it needs no more than that.
"""

import json
import secrets
import threading
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from time import monotonic
from typing import TYPE_CHECKING, Final

from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.core.clock import DAY_S, day_start, days_ended
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.playback import DEFAULT_SECONDS_PER_DAY, check_pace, delivered
from greenhouse_sim.services.run_store import (
    CHECKPOINT_TYPE,
    Commit,
    EpochStore,
    ForkOf,
    Kind,
    ObjectStore,
    Page,
    Status,
    decompress,
)
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.sensors import run_start

if TYPE_CHECKING:
    # Typed only: the simulator owns the positions, and imports this module.
    from greenhouse_sim.services.simulator import Simulator

# How many positions a simulator holds at once; one opened beyond it lets go
# of the one used least recently.
MOST_POSITIONS: Final = 256
ID_BYTES: Final = 6


class PositionState(BaseModel):
    """Where a position stands over its epoch: the epoch, the moment, both as
    an instant and as seconds into the run (as the viewer asks for a moment),
    whether it plays or follows, how far the epoch is committed, whether a playback
    holds the epoch's clock, as the runs listed say, and the changes given to it, as
    its plan holds them, spelled as a run's `&targets=`, `&schedule=` and `&crop=`
    write them, for the viewer to draw it under."""

    model_config = ConfigDict(frozen=True)

    position_id: str
    scenario_id: str
    run_id: str
    epoch: int
    layout: str
    seed: int | None
    # The weather its run is under, by name: none for its scenario's own
    # (decision 0075). The viewer draws the scene under it.
    weather: str | None = None
    status: Status
    started_at: datetime
    simulated_now: datetime
    time_s: float
    day: int
    playing: bool
    following: bool
    seconds_per_day: float
    frontier_s: float
    duration_s: float | None
    # Where what the epoch holds begins, and for a fork where it comes from.
    start_s: float = 0.0
    fork: ForkOf | None = None
    # Whether the epoch it was forked from is still in the store: it can be
    # deleted, and a fork stands by what it inherited.
    parent_kept: bool = False
    targets: list[tuple[float, str, float]] = []
    commands: list[tuple[float, str, float]] = []
    crop: list[tuple[float, str, str, str]] = []


class Records[RecordT]:
    """Records of an epoch's log after a position of it that its position
    has delivered, the position after them, and whether more are delivered."""

    def __init__(self, records: Sequence[RecordT], next_: int, has_more: bool) -> None:
        self.records = tuple(records)
        self.next = next_
        self.has_more = has_more


class StoredEpoch:
    """One epoch of a run in a store, read by any number of positions."""

    def __init__(self, simulator: Simulator, objects: ObjectStore, run_id: str, epoch: int) -> None:
        if epoch not in stored_epochs(objects, run_id):
            raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
        self._simulator = simulator
        self.store = EpochStore(objects, run_id, epoch)
        manifest = self.store.manifest()
        self.run_id, self.epoch = run_id, epoch
        self.scenario_id, self.layout, self.seed, self.weather = (
            manifest.scenario_id,
            manifest.layout,
            manifest.seed,
            manifest.weather,
        )
        self.duration_s = manifest.duration_s
        self.fork = manifest.fork
        self.start_s = 0.0 if manifest.fork is None else manifest.fork.start_s
        self.start = run_start(simulator.catalogue, manifest.scenario_id)
        self._lock = threading.Lock()
        self._commits: list[Commit] = []
        # The outcomes read, and how many commits they were read at.
        self._outcomes: tuple[int, list[ActionOutcome]] = (-1, [])
        # The plan through its frontier, and how many commits it was read at.
        self._plan: tuple[int, RunPlan] = (0, RunPlan())

    def plan(self) -> RunPlan:
        """The plan it was worked out under up to its frontier, as the checkpoint
        there keeps it; nothing to read if it was given no change."""
        commits = len(self.commits())
        with self._lock:
            if commits == self._plan[0]:
                return self._plan[1]
        made = RunPlan()
        if self.store.logged():
            found = self.store.checkpoint_at(self.frontier_s())
            if found is not None and found[1] == CHECKPOINT_TYPE:
                made = RunPlan.model_validate(json.loads(decompress(found[0])).get("plan", {}))
        with self._lock:
            self._plan = (commits, made)
        return made

    def run(self) -> RunRequest:
        """The run the epoch is of, as the by-moment services take it."""
        return RunRequest(
            self.scenario_id,
            layout=self.layout,
            weather=self.weather,
            plan=self.plan(),
            seed=self.seed,
        )

    def status(self) -> Status:
        return self.store.manifest().status

    def commits(self) -> list[Commit]:
        """Its commits, those read before kept: they are written once."""
        with self._lock:
            self._commits += self.store.commits(len(self._commits))
            return list(self._commits)

    def frontier_s(self) -> float:
        """How far the epoch is committed, in seconds into its run: where it
        begins, until a commit says otherwise."""
        commits = self.commits()
        return commits[-1].end_s if commits else self.start_s

    def observations(self, after: int, limit: int, at_s: float) -> Records[Observation]:
        """The observations after position `after` of its log that were
        delivered by `at_s`, at most `limit`."""
        return self._records(Kind.OBSERVATIONS, self.store.observations, after, limit, at_s)

    def events(self, after: int, limit: int, at_s: float) -> Records[Event]:
        return self._records(Kind.EVENTS, self.store.events, after, limit, at_s)

    def outcomes(self, after: int, limit: int, at_s: float) -> Records[ActionOutcome]:
        """The outcomes after position `after` of its log that were delivered
        by `at_s`, in the log's order, which ends at the first not yet."""
        held = self._outcome_log()
        until = self.start + timedelta(seconds=at_s)
        visible = 0
        for outcome in held:
            if (outcome.delivered_at or outcome.resolved_at) > until:
                break
            visible += 1
        chosen = held[after : min(visible, after + limit)]
        reached = max(after, after + len(chosen))
        return Records(chosen, reached, reached < visible)

    def _outcome_log(self) -> list[ActionOutcome]:
        commits = len(self.commits())
        with self._lock:
            if self._outcomes[0] != commits:
                self._outcomes = (commits, self.store.outcomes(0).records)
            return self._outcomes[1]

    def _records[RecordT: (Observation, Event)](
        self,
        kind: Kind,
        read: Callable[[int, int | None], Page[RecordT]],
        after: int,
        limit: int,
        at_s: float,
    ) -> Records[RecordT]:
        visible = self._visible(kind, read, at_s)
        wanted = max(0, min(limit, visible - after))
        page = read(after, wanted).records if wanted else []
        reached = after + len(page)
        return Records(page, reached, reached < visible)

    def _visible[RecordT: (Observation, Event)](
        self, kind: Kind, read: Callable[[int, int | None], Page[RecordT]], at_s: float
    ) -> int:
        """How many records of a log were delivered by `at_s`: those of every
        segment ended by then, and of the one it falls in, those delivered by
        it, which a segment holds in delivery order."""
        counted = 0
        for commit in self.commits():
            held = commit.counts[kind]
            if commit.end_s <= at_s:
                counted += held
                continue
            if commit.start_s <= at_s and held:
                records = read(counted, held).records
                delivered_s = [(delivered(r) - self.start).total_seconds() for r in records]
                counted += bisect_right(delivered_s, at_s)
            break
        return counted

    def parent_kept(self) -> bool:
        """Whether the epoch this one was forked from is still in the store; an
        epoch that is no fork has none."""
        return self.fork is not None and self.fork.epoch in stored_epochs(
            self.store.objects, self.fork.run_id
        )

    def restore_near(self, at_s: float) -> int | None:
        """Gives the simulator's kept states the nearest checkpoint the store
        holds at or before `at_s`, so that the run's services take its state
        over instead of working its days out again; the day it is of, or none
        if there is none, or it was made by another version of the scenario or
        its models (then the days are worked out, as they were). A moment that
        ends its day is charted through that day (`day_start`), which began a
        checkpoint earlier: that one is given too, or the day's first moment
        would be worked out from the run's start."""
        charted_from = day_start(at_s)
        if charted_from != days_ended(at_s) * DAY_S:
            self._restored(charted_from)
        return self._restored(at_s)

    def _restored(self, at_s: float) -> int | None:
        """Gives the simulator's kept states the checkpoint `restore_near`
        says, and says which day it is of."""
        found = self.store.checkpoint_at(at_s)
        if found is None or found[1] != CHECKPOINT_TYPE:
            return None
        try:
            return checkpoints.upload_checkpoint(
                self._simulator, json.loads(decompress(found[0]))
            ).day
        except InvalidRequest:
            return None


class Position:
    """A place over one stored epoch: see the module. `clock` is the real
    seconds it plays by."""

    def __init__(
        self,
        epoch: StoredEpoch,
        position_id: str,
        *,
        seconds_per_day: float = DEFAULT_SECONDS_PER_DAY,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        check_pace(seconds_per_day)
        self.epoch = epoch
        self.position_id = position_id
        self._clock = clock
        self._lock = threading.Lock()
        self._time_s = epoch.start_s
        # A fork is first shown at the moment it was made from, which may lie
        # inside the day it begins with: where this position is bound until it
        # gets there, as that day is computed, or is moved.
        self._bound_for = None if epoch.fork is None else epoch.fork.at_s
        self._playing = False
        self._following = False
        self._seconds_per_day = seconds_per_day
        self._since = clock()
        # Whether it waited at the frontier of an epoch still computing when
        # it last looked, and the epoch's status then.
        self._waiting = False
        self._status = epoch.status()

    def _advance(self) -> float:
        """Moves the position on by the real time since it last looked, to
        the epoch's frontier at most, and returns the frontier. It waits at
        the frontier of an epoch still computing, and the time it waited is
        not played when the epoch computes on, as a playback's clock starts
        again from the work done; at the end of a finished epoch it stops.

        The status is read before the frontier: a worker commits its last day
        before it tells the epoch finished, so a finished epoch's frontier,
        read after, is its last, and a position never stops short of it."""
        now = self._clock()
        elapsed, self._since = now - self._since, now
        self._status = self.epoch.status()
        frontier = self.epoch.frontier_s()
        if self._bound_for is not None:
            self._time_s = min(self._bound_for, frontier)
            if self._time_s >= self._bound_for:
                self._bound_for = None
        if self._following:
            self._time_s = frontier
        elif self._playing:
            if self._waiting:
                elapsed = 0.0
            self._time_s = min(frontier, self._time_s + elapsed / self._seconds_per_day * DAY_S)
            if self._time_s >= frontier and self._status == Status.FINISHED:
                self._playing = False
        self._wait_if_at(frontier)
        return frontier

    def _wait_if_at(self, frontier: float) -> None:
        """Notes whether the position, playing, stands at the frontier of an
        epoch that is not finished: then it waits."""
        self._waiting = (
            self._playing
            and not self._following
            and self._time_s >= frontier
            and self._status != Status.FINISHED
        )

    def _state(self, frontier: float) -> PositionState:
        epoch = self.epoch
        planned = epoch.plan()
        return PositionState(
            position_id=self.position_id,
            scenario_id=epoch.scenario_id,
            run_id=epoch.run_id,
            epoch=epoch.epoch,
            layout=epoch.layout,
            seed=epoch.seed,
            weather=epoch.weather,
            status=self._status,
            started_at=epoch.start,
            simulated_now=epoch.start + timedelta(seconds=self._time_s),
            time_s=self._time_s,
            day=int(self._time_s // DAY_S),
            playing=self._playing,
            following=self._following,
            seconds_per_day=self._seconds_per_day,
            frontier_s=frontier,
            duration_s=epoch.duration_s,
            start_s=epoch.start_s,
            fork=epoch.fork,
            parent_kept=epoch.parent_kept(),
            targets=list(planned.targeted()),
            commands=list(planned.commanded()),
            crop=list(planned.crop_spelled()),
        )

    def state(self) -> PositionState:
        with self._lock:
            return self._state(self._advance())

    def play(self) -> PositionState:
        """Plays on from where it is; a position that follows the frontier
        stops following."""
        with self._lock:
            frontier = self._advance()
            self._following, self._bound_for = False, None
            self._playing = not (self._time_s >= frontier and self._status == Status.FINISHED)
            self._wait_if_at(frontier)
            return self._state(frontier)

    def pause(self) -> PositionState:
        with self._lock:
            frontier = self._advance()
            self._playing = self._following = False
            self._wait_if_at(frontier)
            return self._state(frontier)

    def set_pace(self, seconds_per_day: float) -> PositionState:
        check_pace(seconds_per_day)
        with self._lock:
            frontier = self._advance()
            self._seconds_per_day = seconds_per_day
            return self._state(frontier)

    def seek(self, time_s: float) -> PositionState:
        """Moves to `time_s` into the run: from its start to the epoch's
        frontier, not past it. The position stops following; it keeps playing
        if it played. The nearest checkpoint is restored for the scene."""
        with self._lock:
            frontier = self._advance()
            first = self.epoch.start_s
            if not first <= time_s <= frontier:
                raise InvalidRequest(
                    f"a position is between where the epoch begins and its frontier, "
                    f"{first:.15g} to {frontier:.15g} s, not at {time_s:.15g} s"
                )
            self._time_s, self._following, self._bound_for = time_s, False, None
            self._wait_if_at(frontier)
            at = self._time_s
        self.epoch.restore_near(at)
        with self._lock:
            return self._state(frontier)

    def follow(self) -> PositionState:
        """Goes to the frontier and stays at it as it advances."""
        with self._lock:
            frontier = self._advance()
            self._time_s, self._following, self._playing = frontier, True, False
            self._bound_for = None
            self._wait_if_at(frontier)
        self.epoch.restore_near(frontier)
        with self._lock:
            return self._state(frontier)

    def observations(self, after: int = 0, limit: int = 5_000) -> Records[Observation]:
        return self.epoch.observations(after, limit, self._moment())

    def events(self, after: int = 0, limit: int = 5_000) -> Records[Event]:
        return self.epoch.events(after, limit, self._moment())

    def outcomes(self, after: int = 0, limit: int = 5_000) -> Records[ActionOutcome]:
        return self.epoch.outcomes(after, limit, self._moment())

    def _moment(self) -> float:
        with self._lock:
            self._advance()
            return self._time_s


class Positions:
    """A simulator's positions (decision 0048), by their identifiers: the
    latest `MOST_POSITIONS` used."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held: OrderedDict[str, Position] = OrderedDict()

    def open(
        self,
        simulator: Simulator,
        objects: ObjectStore,
        run_id: str,
        epoch: int,
        *,
        seconds_per_day: float = DEFAULT_SECONDS_PER_DAY,
        clock: Callable[[], float] = monotonic,
    ) -> Position:
        """A new position at the start of an epoch in the store, or for a fork
        at the moment it was made from; an epoch the store does not hold is not
        found."""
        made = Position(
            StoredEpoch(simulator, objects, run_id, epoch),
            secrets.token_hex(ID_BYTES),
            seconds_per_day=seconds_per_day,
            clock=clock,
        )
        with self._lock:
            self._held[made.position_id] = made
            while len(self._held) > MOST_POSITIONS:
                self._held.popitem(last=False)
        return made

    def get(self, position_id: str) -> Position:
        with self._lock:
            found = self._held.get(position_id)
            if found is None:
                raise NotFound(f"no position {position_id!r}")
            self._held.move_to_end(position_id)
            return found

    def close(self, position_id: str) -> None:
        with self._lock:
            if self._held.pop(position_id, None) is None:
                raise NotFound(f"no position {position_id!r}")

    def close_over(self, run_id: str, epoch: int) -> None:
        """Closes the positions over an epoch, which is going."""
        with self._lock:
            for position_id in [
                held_id
                for held_id, held in self._held.items()
                if (held.epoch.run_id, held.epoch.epoch) == (run_id, epoch)
            ]:
                del self._held[position_id]

    def forget(self) -> None:
        with self._lock:
            self._held.clear()
