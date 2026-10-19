"""A scenario's own run played back against one clock (P10.2, decision
0041), so that what the viewer draws and what a consumer reads are the same
run.

A `Playback` works its run's records out day by day, on a thread of its
own, ahead of a clock that plays over them: the clock never passes what is
worked out, so a record the clock has reached is always there. The viewer
draws the run at the clock's moment as it draws any moment of a run (its
field, its crop, its sensors, `run_state`), and a consumer reads the records
delivered by then. Both name it by the run's identity (`air_through_a_run`),
its epoch and the clock's instant. A restart is a new epoch of the same run
from its start: the run is deterministic, so its records are the same again,
and are not worked out twice.

The records are the point sensors' readings at a consumer's cadence
(`every_s`): each sensor's own sample at that minute, noise and all, as the
viewer's sensor panel has it, so a consumer and the viewer never disagree
about what a sensor said. A camera's frames are not records a consumer
reads. A day's records are kept as compressed JSON, read back as asked for.

The run is the scenario's own: its layout, weather and daily commands, as
the viewer draws it when nothing is changed. A command given in the viewer
makes another run, which the playback does not follow.
"""

import gzip
import math
import threading
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from time import monotonic
from typing import Final

from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict, TypeAdapter

from greenhouse_sim.core.clock import DAY_S, run_day
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.sensors import delivered_between, run_start

# Ten real seconds a simulated day by default: a season of 100 days in under
# 17 minutes, each day long enough to watch.
DEFAULT_SECONDS_PER_DAY: Final = 10.0
# The cadence a consumer reads the sensors at, every fifth minute of their
# own minute-by-minute samples: enough for a dashboard's charts, a fifth of
# the records.
CONSUMER_CADENCE_S: Final = 300.0
# The first epoch of a run, as the consumer interface counts them.
FIRST_EPOCH: Final = 0
# How many days' records are kept read back at once.
DAYS_READ_BACK: Final = 4
# How often a wait for worked-out days looks again.
WAIT_STEP_S: Final = 0.05

_RECORDS: Final = TypeAdapter(list[Observation])


class PlaybackFailed(RuntimeError):
    """A playback's run could not be worked out, unexpectedly: a failure of
    the simulator's, not of a request, answered and logged as such."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"the playback of {run_id} could not work its run out")


class PlaybackCommand(StrEnum):
    """What a client can tell a playback to do, apart from its pace."""

    PLAY = "play"
    PAUSE = "pause"
    RESTART = "restart"


class PlaybackState(BaseModel):
    """Where a playback stands: the run it plays, its epoch, its clock, both
    as the instant it has reached and as seconds into the run, as the viewer
    asks for a moment; whether it plays and how fast; and how far ahead of
    it the run's records are worked out."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    run_id: str
    epoch: int
    greenhouse_id: str
    started_at: datetime
    simulated_now: datetime
    time_s: float
    day: int
    playing: bool
    seconds_per_day: float
    worked_out_s: float
    every_s: float


@dataclass(frozen=True)
class RecordsAfter:
    """The records delivered after a position in a run's log, up to the
    clock, in delivery order; the position after the last of them; whether
    more had been delivered than were given; and the state they were cut at."""

    records: tuple[Observation, ...]
    next: int
    has_more: bool
    state: PlaybackState


@dataclass(frozen=True)
class _Day:
    """One day's records: how many, when each was delivered, in seconds from
    the run's start, in order, and the records themselves, compressed."""

    count: int
    delivered_s: tuple[float, ...]
    packed: bytes


class Playback:
    """One scenario's own run, worked out ahead of a clock that plays over
    it; see the module."""

    def __init__(
        self,
        scenario_id: str,
        *,
        seconds_per_day: float = DEFAULT_SECONDS_PER_DAY,
        every_s: float = CONSUMER_CADENCE_S,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        config = scenario(scenario_id)
        _check_pace(seconds_per_day)
        self.scenario_id = scenario_id
        self.greenhouse_id = config.greenhouse_id
        self.start = run_start(scenario_id)
        self.end_s = config.duration_days * DAY_S
        self.every_s = every_s
        _, self.run_id = air_through_a_run(scenario_id, DEFAULT_LAYOUT)
        self._clock = clock
        self._lock = threading.Lock()
        self._days: list[_Day] = []
        self._read_back: OrderedDict[int, list[Observation]] = OrderedDict()
        self._epoch = FIRST_EPOCH
        self._time_s = 0.0
        self._playing = False
        self._seconds_per_day = seconds_per_day
        self._since = clock()
        self._stopped = threading.Event()
        self._failure: Exception | None = None
        self._worker = threading.Thread(target=self._work, daemon=True)

    def begin(self) -> None:
        """Starts working the run's days out, ahead of the clock."""
        self._worker.start()

    def stop(self) -> None:
        """Stops working days out, after the one under way."""
        self._stopped.set()

    def wait_for(self, days: int, timeout_s: float | None = None) -> bool:
        """Whether `days` days are worked out, waiting up to `timeout_s`."""
        deadline = None if timeout_s is None else monotonic() + timeout_s
        while True:
            with self._lock:
                if len(self._days) >= days or self._failure is not None:
                    return len(self._days) >= days
            if self._stopped.is_set() or (deadline is not None and monotonic() > deadline):
                return False
            self._stopped.wait(WAIT_STEP_S)

    def _work(self) -> None:
        for day in range(round(self.end_s / DAY_S)):
            if self._stopped.is_set() or not self.work_day(day):
                return

    def work_day(self, day: int) -> bool:
        """Works the run's day `day` out and publishes its records, the day
        after the last published; whether it could, any failure kept and
        said by `state` rather than lost with the worker."""
        try:
            records, run_id = delivered_between(
                self.scenario_id,
                None if day == 0 else day * DAY_S,
                (day + 1) * DAY_S,
                self.every_s,
            )
        except Exception as error:
            with self._lock:
                self._failure = error
            return False
        if run_id != self.run_id:
            with self._lock:
                self._failure = RuntimeError(f"its run is another now: {run_id}")
            return False
        worked = _Day(
            count=len(records),
            delivered_s=tuple(
                ((r.delivered_at or r.timestamp) - self.start).total_seconds() for r in records
            ),
            packed=gzip.compress(_RECORDS.dump_json(records)),
        )
        with self._lock:
            # The clock moved as far as it could before this day: from now
            # on it moves into it. Time it spent waiting is not banked,
            # however often anyone asked meanwhile.
            self._advance()
            self._days.append(worked)
        return True

    def _advance(self) -> None:
        """Moves the clock on by the real time since it last moved, at its
        pace, as far as the records are worked out and the run lasts."""
        now = self._clock()
        if self._playing:
            worked_out = len(self._days) * DAY_S
            moved = self._time_s + (now - self._since) * DAY_S / self._seconds_per_day
            self._time_s = min(moved, worked_out, self.end_s)
            if self._time_s >= self.end_s:
                self._playing = False
        self._since = now

    def _state(self) -> PlaybackState:
        if self._failure is not None:
            if isinstance(self._failure, ServiceError):
                raise self._failure
            raise PlaybackFailed(self.run_id) from self._failure
        return PlaybackState(
            scenario_id=self.scenario_id,
            run_id=self.run_id,
            epoch=self._epoch,
            greenhouse_id=self.greenhouse_id,
            started_at=self.start,
            simulated_now=self.start + timedelta(seconds=self._time_s),
            time_s=self._time_s,
            day=run_day(self._time_s),
            playing=self._playing,
            seconds_per_day=self._seconds_per_day,
            worked_out_s=len(self._days) * DAY_S,
            every_s=self.every_s,
        )

    def state(self) -> PlaybackState:
        with self._lock:
            self._advance()
            return self._state()

    def command(self, command: PlaybackCommand) -> PlaybackState:
        """Plays on, holds the clock, or starts the run over as a new epoch,
        playing; answers with the new state."""
        with self._lock:
            self._advance()
            match command:
                case PlaybackCommand.PLAY:
                    self._playing = self._time_s < self.end_s
                case PlaybackCommand.PAUSE:
                    self._playing = False
                case PlaybackCommand.RESTART:
                    self._epoch += 1
                    self._time_s = 0.0
                    self._playing = True
            return self._state()

    def set_pace(self, seconds_per_day: float) -> PlaybackState:
        """Plays a simulated day in `seconds_per_day` real seconds."""
        _check_pace(seconds_per_day)
        with self._lock:
            self._advance()
            self._seconds_per_day = seconds_per_day
            return self._state()

    def records_after(self, after: int, limit: int) -> RecordsAfter:
        """The records delivered after position `after` of the run's log and
        by the clock, at most `limit` of them."""
        if after < 0 or limit < 1:
            raise InvalidRequest("a position is 0 or more, and a limit 1 or more")
        with self._lock:
            self._advance()
            state = self._state()
            days = list(self._days)
        # Each day's records delivered by the clock, the day it is in cut at
        # the clock.
        visible = [
            day.count
            if (index + 1) * DAY_S <= state.time_s
            else bisect_right(day.delivered_s, state.time_s)
            for index, day in enumerate(days)
        ]
        total = sum(visible)
        until = min(total, after + limit)
        records: list[Observation] = []
        first = 0
        for index, count in enumerate(visible):
            if first >= until:
                break
            if first + count > after:
                held = self._day_records(index, days[index])
                records.extend(held[max(0, after - first) : min(count, until - first)])
            first += count
        return RecordsAfter(
            records=tuple(records), next=max(after, until), has_more=until < total, state=state
        )

    def _day_records(self, index: int, day: _Day) -> list[Observation]:
        """A day's records, read back, the latest few kept so."""
        with self._lock:
            held = self._read_back.get(index)
            if held is not None:
                self._read_back.move_to_end(index)
                return held
        held = _RECORDS.validate_json(gzip.decompress(day.packed))
        with self._lock:
            self._read_back[index] = held
            while len(self._read_back) > DAYS_READ_BACK:
                self._read_back.popitem(last=False)
        return held


def _check_pace(seconds_per_day: float) -> None:
    if not (math.isfinite(seconds_per_day) and seconds_per_day > 0):
        raise InvalidRequest("a day takes some time to play: seconds_per_day is above 0")


_playbacks: dict[str, Playback] = {}
_playbacks_lock = threading.Lock()


def start(scenario_id: str, seconds_per_day: float | None = None) -> PlaybackState:
    """The scenario's playback, started and playing, at `seconds_per_day` if
    given: the one already started, or a new one from the run's start."""
    with _playbacks_lock:
        found = _playbacks.get(scenario_id)
        if found is None:
            found = Playback(
                scenario_id, seconds_per_day=seconds_per_day or DEFAULT_SECONDS_PER_DAY
            )
            found.begin()
            _playbacks[scenario_id] = found
    if seconds_per_day is not None:
        found.set_pace(seconds_per_day)
    return found.command(PlaybackCommand.PLAY)


def playback(scenario_id: str) -> Playback:
    """The scenario's playback, if one was started."""
    with _playbacks_lock:
        found = _playbacks.get(scenario_id)
    if found is None:
        raise NotFound(f"no playback of {scenario_id!r} was started")
    return found


def state(scenario_id: str) -> PlaybackState:
    return playback(scenario_id).state()


def command(scenario_id: str, command: PlaybackCommand) -> PlaybackState:
    return playback(scenario_id).command(command)


def set_pace(scenario_id: str, seconds_per_day: float) -> PlaybackState:
    return playback(scenario_id).set_pace(seconds_per_day)


def forget_playbacks() -> None:
    """Stops and forgets every playback, for tests."""
    with _playbacks_lock:
        for found in _playbacks.values():
            found.stop()
        _playbacks.clear()
