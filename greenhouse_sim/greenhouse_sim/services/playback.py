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
reads. Beside them, the crop's walk and harvests (`crop_log`) and the heat
its heaters gave each day (`heat_log`). A day's records are kept as
compressed JSON, read back as asked for.

The run is the scenario's own: its layout, weather and daily commands, as
the viewer draws it when nothing is changed. A command given in the viewer
makes another run, which the playback does not follow.
"""

import gzip
import math
import os
import threading
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import Final

from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict, TypeAdapter

from greenhouse_sim.core.clock import DAY_S, run_day
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.heat_log import heat_records
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.sensors import delivered_between, run_start
from greenhouse_sim.services.stores import Store

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

_OBSERVATIONS: Final = TypeAdapter(list[Observation])
_EVENTS: Final = TypeAdapter(list[Event])


class Epochs:
    """The epochs of runs played back, kept in `folder` across the
    producer's restarts, a file per run holding the last one started: so
    that a consumer reconnecting after a restart sees a new epoch of the
    run, never its first again, and starts it afresh (decision 0040)."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def _file(self, run_id: str) -> Path:
        return self.folder / f"{run_id}.epoch"

    def next(self, run_id: str) -> int:
        """The epoch a run starts now: the one after the last kept, or the
        first; kept in turn."""
        try:
            last = int(self._file(run_id).read_text())
        except FileNotFoundError, ValueError:
            epoch = FIRST_EPOCH
        else:
            epoch = last + 1
        self.started(run_id, epoch)
        return epoch

    def started(self, run_id: str, epoch: int) -> None:
        """Keeps `epoch` as the run's last started."""
        self.folder.mkdir(parents=True, exist_ok=True)
        self._file(run_id).write_text(f"{epoch}\n")


def default_epochs() -> Epochs:
    """Where a played-back run's epochs are kept on this machine: the user's
    state folder (`XDG_STATE_HOME`, or ~/.local/state), under
    greenhouse-sim."""
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Epochs(Path(state) / "greenhouse-sim" / "playback-epochs")


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
class RecordsAfter[R: (Observation, Event)]:
    """The records of one log delivered after a position in it, up to the
    clock, in delivery order; the position after the last of them; whether
    more had been delivered than were given; and the state they were cut at."""

    records: tuple[R, ...]
    next: int
    has_more: bool
    state: PlaybackState


@dataclass(frozen=True)
class _Packed:
    """One day of a log: how many records, when each was delivered, in
    seconds from the run's start, in order, and the records, compressed."""

    count: int
    delivered_s: tuple[float, ...]
    packed: bytes


class _Log[R: (Observation, Event)]:
    """One kind of a run's records, day by day, in delivery order, kept
    compressed, and the latest few days read back."""

    def __init__(self, adapter: TypeAdapter[list[R]], start: datetime) -> None:
        self._adapter: TypeAdapter[list[R]] = adapter
        self._start = start
        self._lock = threading.Lock()
        self.days: list[_Packed] = []
        self._read_back: OrderedDict[int, list[R]] = OrderedDict()

    def packed(self, records: Sequence[R]) -> _Packed:
        return _Packed(
            count=len(records),
            delivered_s=tuple((delivered(r) - self._start).total_seconds() for r in records),
            packed=gzip.compress(self._adapter.dump_json(list(records))),
        )

    def after(
        self, days: Sequence[_Packed], after: int, limit: int, time_s: float
    ) -> tuple[tuple[R, ...], int, bool]:
        """The records after position `after` delivered by `time_s`, at most
        `limit`; the position after them; and whether more were left."""
        visible = [
            day.count if (index + 1) * DAY_S <= time_s else bisect_right(day.delivered_s, time_s)
            for index, day in enumerate(days)
        ]
        total = sum(visible)
        until = min(total, after + limit)
        records: list[R] = []
        first = 0
        for index, count in enumerate(visible):
            if first >= until:
                break
            if first + count > after:
                held = self._day(index, days[index])
                records.extend(held[max(0, after - first) : min(count, until - first)])
            first += count
        return tuple(records), max(after, until), until < total

    def _day(self, index: int, day: _Packed) -> list[R]:
        """A day's records, read back, the latest few kept so."""
        with self._lock:
            held = self._read_back.get(index)
            if held is not None:
                self._read_back.move_to_end(index)
                return held
        records: list[R] = self._adapter.validate_json(gzip.decompress(day.packed))
        with self._lock:
            self._read_back[index] = records
            while len(self._read_back) > DAYS_READ_BACK:
                self._read_back.popitem(last=False)
        return records


def delivered(record: Observation | Event) -> datetime:
    """When a record reached the producer: an observation's delivery, or the
    moment a record was taken, if it was delivered as it was taken."""
    if isinstance(record, Observation) and record.delivered_at is not None:
        return record.delivered_at
    return record.timestamp


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
        epochs: Epochs | None = None,
    ) -> None:
        config = scenario(scenario_id)
        _check_pace(seconds_per_day)
        self.scenario_id = scenario_id
        self.greenhouse_id = config.greenhouse_id
        self.start = run_start(scenario_id)
        self.end_s = config.duration_days * DAY_S
        self.every_s = every_s
        _, self.run_id = air_through_a_run(RunRequest(scenario_id))
        self._clock = clock
        self._lock = threading.Lock()
        self._observations = _Log(_OBSERVATIONS, self.start)
        self._events = _Log(_EVENTS, self.start)
        # The days worked out of both logs, appended together.
        self._worked: list[tuple[_Packed, _Packed]] = []
        # Counted on from the run's last epoch, if they are kept: a producer
        # started again is a new epoch of its run, never its first again.
        self._epochs = epochs
        self._epoch = FIRST_EPOCH if epochs is None else epochs.next(self.run_id)
        self._time_s = 0.0
        self._playing = False
        self._seconds_per_day = seconds_per_day
        self._since = clock()
        self._stopped = threading.Event()
        self._failure: Exception | None = None
        self._worker = threading.Thread(
            target=self._work, name=f"playback of {self.run_id}", daemon=True
        )

    def begin(self) -> None:
        """Starts working the run's days out, ahead of the clock."""
        self._worker.start()

    def stop(self) -> None:
        """Stops working days out, once the one under way is: it returns when
        the worker has, so that nothing of the run goes on being worked out
        beside whatever comes next, such as another run of the same crop."""
        self._stopped.set()
        if self._worker.is_alive() and self._worker is not threading.current_thread():
            self._worker.join()

    def wait_for(self, days: int, timeout_s: float | None = None) -> bool:
        """Whether `days` days are worked out, waiting up to `timeout_s`."""
        deadline = None if timeout_s is None else monotonic() + timeout_s
        while True:
            with self._lock:
                if len(self._worked) >= days or self._failure is not None:
                    return len(self._worked) >= days
            if self._stopped.is_set() or (deadline is not None and monotonic() > deadline):
                return False
            self._stopped.wait(WAIT_STEP_S)

    def _work(self) -> None:
        for day in range(round(self.end_s / DAY_S)):
            if self._stopped.is_set() or not self.work_day(day):
                return

    def work_day(self, day: int) -> bool:
        """Works the run's day `day` out and publishes its records, the day
        after the last published: its sensors' readings, its crop's walk and
        harvests, and the heat its heaters gave. Whether it could, any
        failure kept and said by `state` rather than lost with the worker."""
        try:
            readings, run_id = delivered_between(
                self.scenario_id,
                None if day == 0 else day * DAY_S,
                (day + 1) * DAY_S,
                self.every_s,
            )
            walked, harvests = crop_records(self.scenario_id, day, self.start, self.run_id)
            heated = heat_records(self.scenario_id, day, self.start, self.run_id)
        except Exception as error:
            with self._lock:
                self._failure = error
            return False
        if run_id != self.run_id:
            with self._lock:
                self._failure = RuntimeError(f"its run is another now: {run_id}")
            return False
        observations = sorted(
            [*readings, *walked, *heated],
            key=lambda r: (delivered(r), r.sensor_id or r.plant_id or ""),
        )
        events = sorted(harvests, key=lambda e: (e.timestamp, e.plant_id or ""))
        worked = (self._observations.packed(observations), self._events.packed(events))
        with self._lock:
            # The clock moved as far as it could before this day: from now
            # on it moves into it. Time it spent waiting is not banked,
            # however often anyone asked meanwhile.
            self._advance()
            self._worked.append(worked)
        return True

    def _advance(self) -> None:
        """Moves the clock on by the real time since it last moved, at its
        pace, as far as the records are worked out and the run lasts."""
        now = self._clock()
        if self._playing:
            worked_out = len(self._worked) * DAY_S
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
            worked_out_s=len(self._worked) * DAY_S,
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
                    if self._epochs is not None:
                        self._epochs.started(self.run_id, self._epoch)
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

    def _cut(self, after: int, limit: int) -> tuple[PlaybackState, list[tuple[_Packed, _Packed]]]:
        if after < 0 or limit < 1:
            raise InvalidRequest("a position is 0 or more, and a limit 1 or more")
        with self._lock:
            self._advance()
            return self._state(), list(self._worked)

    def records_after(self, after: int, limit: int) -> RecordsAfter[Observation]:
        """The observations delivered after position `after` of the run's
        log of them and by the clock, at most `limit` of them."""
        state, worked = self._cut(after, limit)
        records, next_, more = self._observations.after(
            [observations for observations, _ in worked], after, limit, state.time_s
        )
        return RecordsAfter(records=records, next=next_, has_more=more, state=state)

    def events_after(self, after: int, limit: int) -> RecordsAfter[Event]:
        """The events delivered after position `after` of the run's log of
        them and by the clock, at most `limit` of them."""
        state, worked = self._cut(after, limit)
        records, next_, more = self._events.after(
            [events for _, events in worked], after, limit, state.time_s
        )
        return RecordsAfter(records=records, next=next_, has_more=more, state=state)


def _check_pace(seconds_per_day: float) -> None:
    if not (math.isfinite(seconds_per_day) and seconds_per_day > 0):
        raise InvalidRequest("a day takes some time to play: seconds_per_day is above 0")


# Every playback started, by scenario: one let go is stopped, once the day
# under way is worked out.
PLAYBACKS: Store[str, Playback] = Store("playbacks", on_drop=lambda _, found: found.stop())


def start(
    scenario_id: str,
    seconds_per_day: float | None = None,
    *,
    hold: bool = False,
    clock: Callable[[], float] = monotonic,
    epochs: Epochs | None = None,
) -> PlaybackState:
    """The scenario's playback, started, at `seconds_per_day` if given: the
    one already started, or a new one from the run's start, on `clock`;
    playing, unless `hold`, when its clock waits for a play command while
    the run is worked out ahead of it. A pace refused starts nothing."""
    if seconds_per_day is not None:
        _check_pace(seconds_per_day)

    def begun(_: object) -> Playback:
        found = Playback(
            scenario_id,
            seconds_per_day=DEFAULT_SECONDS_PER_DAY if seconds_per_day is None else seconds_per_day,
            clock=clock,
            epochs=epochs,
        )
        found.begin()
        return found

    found = PLAYBACKS.made_once(scenario_id, begun)
    if seconds_per_day is not None:
        found.set_pace(seconds_per_day)
    return found.state() if hold else found.command(PlaybackCommand.PLAY)


def playbacks() -> list[Playback]:
    """Every playback started, in the order they were."""
    return [found for _, found in PLAYBACKS.values()]


def playback(scenario_id: str) -> Playback:
    """The scenario's playback, if one was started."""
    found = PLAYBACKS.get(scenario_id)
    if found is None:
        raise NotFound(f"no playback of {scenario_id!r} was started")
    return found


def state(scenario_id: str) -> PlaybackState:
    return playback(scenario_id).state()


def command(scenario_id: str, command: PlaybackCommand) -> PlaybackState:
    return playback(scenario_id).command(command)


def set_pace(scenario_id: str, seconds_per_day: float) -> PlaybackState:
    return playback(scenario_id).set_pace(seconds_per_day)


def stop_playbacks() -> None:
    """Stops and forgets every playback, as the server that played them
    closes."""
    PLAYBACKS.forget()
