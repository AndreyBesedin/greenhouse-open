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

The run is the scenario's own: its weather and daily commands, as the
viewer draws it when nothing is changed, and its own layout, or one of its
layouts rearranged, its equipment and sensors moved (`world.moves`, #271).
A playback started over with another layout plays that layout's run from
its start: a new run, with an identity of its own, counting its own epochs.
There is one playback a scenario, whose run a viewer following it can
rearrange. A command given in the viewer makes another run, which the
playback does not follow.

Its run's targets, such as the heating setpoint by day, can be changed
while it plays (#274, decision 0043): from the clock's next minute on, in
the same run and epoch, its records from then on worked out again under
them while the clock waits at that minute. A record delivered is never
rewritten, since the run is the same until the change. The changes are part
of its state, so that a viewer following it draws the same run, and a
restart, a new epoch of the scenario's own run, makes none. Started over
with its equipment moved, the run keeps them, each at its moment: the same
run, rearranged (decision 0049).
"""

import gzip
import logging
import math
import os
import threading
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Final

from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict, TypeAdapter

from greenhouse_sim.climate.commands import TARGET_EVERY_S
from greenhouse_sim.core.clock import DAY_S, run_day
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError
from greenhouse_sim.services.fields import air_through_a_run, run_schedule
from greenhouse_sim.services.heat_log import heat_records
from greenhouse_sim.services.runs import Commanded, RunRequest
from greenhouse_sim.services.scenarios import layout_name, scenario
from greenhouse_sim.services.sensors import Stopped, delivered_between, run_start
from greenhouse_sim.services.stores import Store

if TYPE_CHECKING:
    # Typed only: the simulator owns the playbacks, and imports this module.
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)

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
# How long stopping waits for playbacks, in all: one stops at the moment it
# is working out, which takes far less.
STOP_WAIT_S: Final = 10.0

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
    """Where a playback stands: the run it plays, its layout and its epoch,
    its clock, both as the instant it has reached and as seconds into the
    run, as the viewer asks for a moment; whether it plays and how fast; and
    how far ahead of it the run's records are worked out."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    run_id: str
    # The layout its run has, by the name a run knows it by
    # (`scenarios.layout_name`): its scenario's own, or one rearranged.
    layout: str
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
    # The target changes its epoch's run has (#274, decision 0043): those it
    # made, and those of a run it was started over from with moves (decision
    # 0049), each its moment in seconds, its target and its value in °C, as
    # a run's `&targets=` writes them.
    targets: list[tuple[float, str, float]] = []


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
        # Each day read back, with the packed day it was read from: a day
        # worked out again under changed targets is another, read afresh.
        self._read_back: OrderedDict[int, tuple[_Packed, list[R]]] = OrderedDict()

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
            if held is not None and held[0] is day:
                self._read_back.move_to_end(index)
                return held[1]
        records: list[R] = self._adapter.validate_json(gzip.decompress(day.packed))
        with self._lock:
            self._read_back[index] = (day, records)
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
    """One scenario's own run, with its own layout or `layout`, and the
    target changes `targets` from their moments on, worked out ahead of a
    clock that plays over it; see the module. A layout the scenario does
    not have is not found, and moves that do not fit it are refused, as are
    target changes, as a climate run's are."""

    def __init__(
        self,
        scenario_id: str,
        *,
        layout: str | None = None,
        targets: Sequence[Commanded] = (),
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
        self.layout = layout_name(layout or DEFAULT_LAYOUT)
        _, self.run_id = air_through_a_run(RunRequest(scenario_id, layout=self.layout))
        if targets:
            # Checked as a run's target changes are; refused, nothing starts.
            run_schedule(RunRequest(scenario_id, layout=self.layout, targets=tuple(targets)))
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
        # The target changes its epoch has made, in the order made, after
        # those it started with; while one is worked into the run, the
        # moment from which its records are worked again, which the clock
        # does not pass meanwhile; and how many changes there have been, so
        # that a day worked out under the targets before is not published.
        self._targets: tuple[Commanded, ...] = tuple(targets)
        self._again_from: float | None = None
        self._changes = 0
        self._changed = threading.Event()
        self._stopped = threading.Event()
        self._failure: Exception | None = None
        # The playback made to take its place, once one has taken its target
        # changes (`rearranged`): every change asked of it from then on is
        # that one's, so that none it acknowledges is lost.
        self._successor: Playback | None = None
        self._worker = threading.Thread(
            target=self._work, name=f"playback of {self.run_id}", daemon=True
        )

    def begin(self) -> None:
        """Starts working the run's days out, ahead of the clock."""
        self._worker.start()

    def plays(self, layout: str | None) -> bool:
        """Whether it plays the run of `layout`: its own, when None."""
        return layout is None or layout_name(layout) == self.layout

    def rearranged(self, layout: str) -> Playback:
        """A playback of the same scenario with `layout`, at the same pace and
        cadence, on the same clock, with the same target changes, counting the
        epochs of its own run where this one counts its: not begun. From then
        on this one hands it every change asked of it, such as a target
        changed by a request already under way, so that the run played next
        has it. A layout refused makes none, and this one goes on as it was."""
        with self._lock:
            replacing = Playback(
                self.scenario_id,
                layout=layout,
                targets=self._targets,
                seconds_per_day=self._seconds_per_day,
                every_s=self.every_s,
                clock=self._clock,
                epochs=self._epochs,
            )
            self._successor = replacing
        return replacing

    def stop(self, *, wait: bool = True) -> None:
        """Stops working days out, the one under way left at its next moment:
        it returns when the worker has, `STOP_WAIT_S` at most, unless told
        not to wait, so that nothing of the run goes on being worked out
        beside whatever comes next, such as another run of the same crop."""
        self.tell_to_stop()
        if wait:
            self.finish(monotonic() + STOP_WAIT_S)

    def tell_to_stop(self) -> None:
        """Works no other moment out."""
        self._stopped.set()

    @property
    def working(self) -> bool:
        """Whether its worker is still working days out."""
        return self._worker.is_alive()

    def finish(self, deadline: float) -> None:
        """Waits for the worker to end, until `deadline` (`time.monotonic`)
        at most, logged past it."""
        worker = self._worker
        if not worker.is_alive() or worker is threading.current_thread():
            return
        worker.join(max(0.0, deadline - monotonic()))
        if worker.is_alive():
            logger.warning("%s did not stop within %g s", worker.name, STOP_WAIT_S)

    def wait_for(self, days: int, timeout_s: float | None = None) -> bool:
        """Whether `days` days are worked out, waiting up to `timeout_s`."""
        deadline = None if timeout_s is None else monotonic() + timeout_s
        while True:
            with self._lock:
                if self._worked_out_s() >= days * DAY_S or self._failure is not None:
                    return self._worked_out_s() >= days * DAY_S
            if self._stopped.is_set() or (deadline is not None and monotonic() > deadline):
                return False
            self._stopped.wait(WAIT_STEP_S)

    def _run(self) -> RunRequest:
        """The run it plays: its scenario's own, with its layout and its
        epoch's target changes."""
        return RunRequest(self.scenario_id, layout=self.layout, targets=self._targets)

    def _next_day(self) -> int:
        """The day to work out next: the day a target change is worked into,
        if one is, or the day after the last worked out."""
        if self._again_from is not None:
            return min(len(self._worked), int(self._again_from // DAY_S))
        return len(self._worked)

    def _work(self) -> None:
        days = round(self.end_s / DAY_S)
        while not self._stopped.is_set():
            with self._lock:
                day, run, changes = self._next_day(), self._run(), self._changes
                self._changed.clear()
            if day >= days:
                # Every day worked out, until a change has some worked again.
                self._changed.wait(WAIT_STEP_S)
                continue
            if not self._work_day(day, run, changes):
                return

    def work_day(self, day: int) -> bool:
        """Works the run's day `day` out and publishes its records, the day
        after the last published: its sensors' readings, its crop's walk and
        harvests, and the heat its heaters gave. Whether it could, any
        failure kept and said by `state` rather than lost with the worker."""
        with self._lock:
            run, changes = self._run(), self._changes
        return self._work_day(day, run, changes)

    def _work_day(self, day: int, run: RunRequest, changes: int) -> bool:
        """Works day `day` of `run` out, as `work_day` does, and publishes
        it unless the targets changed meanwhile: in place of the day and those
        after it, if they were worked out under the targets before."""
        try:
            readings, run_id = delivered_between(
                run,
                None if day == 0 else day * DAY_S,
                (day + 1) * DAY_S,
                self.every_s,
                named=self.run_id if run.targets else None,
                stop=self._stopped,
            )
            if self._stopped.is_set():
                return False
            walked, harvests = crop_records(run, day, self.start, self.run_id)
            if self._stopped.is_set():
                return False
            heated = heat_records(run, day, self.start, self.run_id)
            if self._stopped.is_set():
                return False
        except Stopped:
            return False
        except Exception as error:
            with self._lock:
                self._failure = error
            return False
        if not run.targets and run_id != self.run_id:
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
            if changes != self._changes:
                # Worked out under targets changed since: worked again.
                return True
            # The clock moved as far as it could before this day: from now
            # on it moves into it. Time it spent waiting is not banked,
            # however often anyone asked meanwhile.
            self._advance()
            del self._worked[day:]
            self._worked.append(worked)
            self._again_from = None
        return True

    def _advance(self) -> None:
        """Moves the clock on by the real time since it last moved, at its
        pace, as far as the records are worked out and the run lasts."""
        now = self._clock()
        if self._playing:
            moved = self._time_s + (now - self._since) * DAY_S / self._seconds_per_day
            self._time_s = max(self._time_s, min(moved, self._worked_out_s(), self.end_s))
            if self._time_s >= self.end_s:
                self._playing = False
        self._since = now

    def _worked_out_s(self) -> float:
        """How far its records are worked out under its targets as they are:
        its days, but none past a target change still being worked in."""
        worked_out = len(self._worked) * DAY_S
        return worked_out if self._again_from is None else min(worked_out, self._again_from)

    def _state(self) -> PlaybackState:
        if self._failure is not None:
            if isinstance(self._failure, ServiceError):
                raise self._failure
            raise PlaybackFailed(self.run_id) from self._failure
        return PlaybackState(
            scenario_id=self.scenario_id,
            run_id=self.run_id,
            layout=self.layout,
            epoch=self._epoch,
            greenhouse_id=self.greenhouse_id,
            started_at=self.start,
            simulated_now=self.start + timedelta(seconds=self._time_s),
            time_s=self._time_s,
            day=run_day(self._time_s),
            playing=self._playing,
            seconds_per_day=self._seconds_per_day,
            worked_out_s=self._worked_out_s(),
            every_s=self.every_s,
            targets=list(self._targets),
        )

    def state(self) -> PlaybackState:
        with self._lock:
            self._advance()
            return self._state()

    def command(self, command: PlaybackCommand) -> PlaybackState:
        """Plays on, holds the clock, or starts the run over as a new epoch,
        playing; answers with the new state. Once replaced, the one in its
        place does."""
        with self._lock:
            successor = self._successor
            if successor is None:
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
                        # The scenario's own run again, without the changes.
                        if self._targets:
                            self._work_again_from(self._targets[0][0])
                            self._targets = ()
                return self._state()
        return successor.command(command)

    def set_targets(self, targets: Mapping[str, float]) -> PlaybackState:
        """Changes its run's targets from the clock's next minute on, in the
        same run and epoch (decision 0043): its records from then on are
        worked out again under them, the clock waiting at that minute until
        they are. Refused as a run's target changes are, or once the run has
        ended. Once replaced, the one in its place changes them."""
        if not targets:
            raise InvalidRequest("targets wants target:celsius pairs, and none was given")
        with self._lock:
            successor = self._successor
            if successor is None:
                self._advance()
                moment = (math.floor(self._time_s / TARGET_EVERY_S) + 1) * TARGET_EVERY_S
                if moment > self.end_s:
                    raise InvalidRequest("the run has ended: its targets change no more")
                changed = (
                    *self._targets,
                    *((moment, name, value) for name, value in targets.items()),
                )
                # Checked as a run's target changes are; refused, nothing changes.
                run_schedule(replace(self._run(), targets=changed))
                self._targets = changed
                self._work_again_from(moment)
                return self._state()
        return successor.set_targets(targets)

    def _work_again_from(self, moment_s: float) -> None:
        """Has its records from `moment_s` on worked out again, the clock
        waiting there meanwhile."""
        self._changes += 1
        self._again_from = moment_s if self._again_from is None else min(self._again_from, moment_s)
        self._changed.set()

    def set_pace(self, seconds_per_day: float) -> PlaybackState:
        """Plays a simulated day in `seconds_per_day` real seconds; once
        replaced, the one in its place does."""
        _check_pace(seconds_per_day)
        with self._lock:
            successor = self._successor
            if successor is None:
                self._advance()
                self._seconds_per_day = seconds_per_day
                return self._state()
        return successor.set_pace(seconds_per_day)

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


class Playbacks:
    """A simulator's playbacks (decision 0048): one a scenario, by its
    identifier; one let go is stopped, at the moment it is working out. One
    rearranged into another is stopped without being waited for, so that
    the new run starts at once, and is waited for as they all are, when
    they are stopped or closed. Once closed, it starts none."""

    def __init__(self) -> None:
        self._store: Store[str, Playback] = Store("playbacks", on_drop=self._let_go, label=str)
        # Held while a playback is added, or put in another's place, so that
        # two requests starting a scenario's playback over with a layout make
        # one, and none is added once they are closed.
        self.rearranging = threading.Lock()
        # Those replaced still working, waited for when they all stop.
        self._replaced: list[Playback] = []
        # While they all stop: when, for every one let go meanwhile.
        self._stopping_by: float | None = None
        self._closed = False

    def _let_go(self, _: str, found: Playback) -> None:
        """Stops a playback let go: by the deadline of all of them, while
        they all stop, or its own."""
        deadline = self._stopping_by
        found.stop(wait=False)
        found.finish(monotonic() + STOP_WAIT_S if deadline is None else deadline)

    def refuse_if_closed(self) -> None:
        """Under `rearranging`: a playback is added to none closed."""
        if self._closed:
            raise RuntimeError("the playbacks are closed")

    def made_once(self, scenario_id: str, begun: Callable[[object], Playback]) -> Playback:
        with self.rearranging:
            self.refuse_if_closed()
            return self._store.made_once(scenario_id, begun)

    def get(self, scenario_id: str) -> Playback | None:
        return self._store.get(scenario_id)

    def all(self) -> list[Playback]:
        """Every playback started, in the order they were."""
        return [found for _, found in self._store.values()]

    def replace(self, scenario_id: str, replacing: Playback, replaced: Playback) -> None:
        """Keeps `replacing` in `replaced`'s place, under `rearranging`; those
        replaced before that have stopped are let go."""
        self._store.keep(scenario_id, replacing)
        self._replaced = [found for found in self._replaced if found.working]
        self._replaced.append(replaced)

    def stop(self) -> None:
        """Stops and forgets every playback: each is told before any is
        waited for, and all are waited for `STOP_WAIT_S` at most."""
        with self.rearranging:
            stopping = [*self.all(), *self._replaced]
            self._replaced.clear()
            deadline = monotonic() + STOP_WAIT_S
            for found in stopping:
                found.tell_to_stop()
            self._stopping_by = deadline
            try:
                self._store.forget()
            finally:
                self._stopping_by = None
        for found in stopping:
            found.finish(deadline)

    def close(self) -> None:
        """Stops every playback, and starts none after."""
        with self.rearranging:
            self._closed = True
        self.stop()


def start(
    simulator: Simulator,
    scenario_id: str,
    seconds_per_day: float | None = None,
    *,
    layout: str | None = None,
    hold: bool = False,
    clock: Callable[[], float] = monotonic,
    epochs: Epochs | None = None,
) -> PlaybackState:
    """The scenario's playback, started, at `seconds_per_day` if given: the
    one already started, or a new one from the run's start, on `clock`, of
    its own layout or `layout`; playing, unless `hold`, when its clock waits
    for a play command while the run is worked out ahead of it. One started
    with another layout than `layout` starts over with it, as a restart
    with a layout does (`command`). A pace or a layout refused starts
    nothing."""
    if seconds_per_day is not None:
        _check_pace(seconds_per_day)

    def begun(_: object) -> Playback:
        found = Playback(
            scenario_id,
            layout=layout,
            seconds_per_day=DEFAULT_SECONDS_PER_DAY if seconds_per_day is None else seconds_per_day,
            clock=clock,
            epochs=epochs,
        )
        found.begin()
        return found

    found = simulator.playbacks.made_once(scenario_id, begun)
    if not found.plays(layout):
        found = _rearranged(simulator, found, layout or DEFAULT_LAYOUT)
    if seconds_per_day is not None:
        found.set_pace(seconds_per_day)
    return found.state() if hold else found.command(PlaybackCommand.PLAY)


def _rearranged(simulator: Simulator, found: Playback, layout: str) -> Playback:
    """The scenario's playback with `layout` in place of the one it has, as
    `found` was: begun, and the one it replaces stopped, without waiting for
    the day it is working out, so that the new run starts at once. One put
    in its place meanwhile with `layout` is kept; a layout refused leaves the
    playback as it was."""
    playbacks = simulator.playbacks
    with playbacks.rearranging:
        playbacks.refuse_if_closed()
        current = playbacks.get(found.scenario_id) or found
        if current.plays(layout):
            return current
        replacing = current.rearranged(layout)
        replacing.begin()
        playbacks.replace(found.scenario_id, replacing, current)
    current.stop(wait=False)
    return replacing


def playback(simulator: Simulator, scenario_id: str) -> Playback:
    """The scenario's playback, if one was started."""
    found = simulator.playbacks.get(scenario_id)
    if found is None:
        raise NotFound(f"no playback of {scenario_id!r} was started")
    return found


def state(simulator: Simulator, scenario_id: str) -> PlaybackState:
    return playback(simulator, scenario_id).state()


def command(
    simulator: Simulator, scenario_id: str, command: PlaybackCommand, layout: str | None = None
) -> PlaybackState:
    """Tells the scenario's playback to play, pause or start over. Started
    over with a layout it does not play, it plays that layout's run from its
    start, a new run, as the epoch its own count gives it, with the target
    changes the run had: so a viewer that follows it rearranges the run
    played back (#271, decision 0049). Started over with its own layout, it
    is the scenario's own run again, without them. Only a restart takes a
    layout."""
    found = playback(simulator, scenario_id)
    if layout is not None and command != PlaybackCommand.RESTART:
        raise InvalidRequest(f"only a restart takes a layout, not {command.value}")
    if not found.plays(layout):
        replacing = _rearranged(simulator, found, layout or DEFAULT_LAYOUT)
        return replacing.command(PlaybackCommand.PLAY)
    return found.command(command)


def set_pace(simulator: Simulator, scenario_id: str, seconds_per_day: float) -> PlaybackState:
    return playback(simulator, scenario_id).set_pace(seconds_per_day)


def set_targets(
    simulator: Simulator, scenario_id: str, targets: Mapping[str, float]
) -> PlaybackState:
    """Changes the targets of the run the scenario's playback plays, from
    its clock's next minute on (#274, decision 0043)."""
    return playback(simulator, scenario_id).set_targets(targets)


def stop_playbacks(simulator: Simulator) -> None:
    """Stops and forgets every playback of the simulator's."""
    simulator.playbacks.stop()
