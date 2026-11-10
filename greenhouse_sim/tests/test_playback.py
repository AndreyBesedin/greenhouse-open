"""A scenario's own run played back against one clock (P10.2, decision
0041): the viewer and a consumer follow the same run, and the clock never
passes what is worked out."""

import math
import sys
import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from greenhouse_protocol.enums import ObservationType

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import heat_log, playback, run_state, sensors
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.playback import Playback, PlaybackCommand, PlaybackFailed
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

import short_runs

# What a server with no scenarios of its own plays.
PACKAGED = "climate_box"
SCENARIO = "climate_box_short"
TENDED = "climate_box_tended"
DAYS = 14
# Every other of the sensors' samples (`short_runs.READS_EVERY_S`), which is what a
# consumer following at it is given and no others.
EVERY_S = 2 * short_runs.READS_EVERY_S
# A page of a consumer's records, less than a day and a half holds.
PAGE = 10
# Every record there is, in one batch.
ALL = 10**6


class Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(scope="module")
def simulator(simulator: Simulator) -> Simulator:
    simulator.catalogue.register(short_runs.one_plant_box(SCENARIO, DAYS))
    simulator.catalogue.register(short_runs.tended_box(TENDED, DAYS))
    return simulator


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def played(simulator: Simulator, clock: Clock) -> Iterator[Playback]:
    """The box's run, its first two days worked out and no more, a day played in
    10 real seconds."""
    run = Playback(simulator, SCENARIO, seconds_per_day=10.0, every_s=EVERY_S, clock=clock)
    run.begin()
    assert run.wait_for(2, timeout_s=120)
    run.stop()
    yield run
    run.stop()


def test_the_clock_plays_over_the_days_worked_out_and_waits_at_the_last(
    played: Playback, clock: Clock
) -> None:
    assert played.state().time_s == 0
    played.command(PlaybackCommand.PLAY)

    clock.now += 5.0
    halfway = played.state()
    assert halfway.time_s == DAY_S / 2
    assert halfway.simulated_now == halfway.started_at + timedelta(seconds=DAY_S / 2)
    assert halfway.day == 0

    # Far past what is worked out, it waits there, still playing.
    clock.now += 1_000.0
    waiting = played.state()
    assert waiting.time_s == waiting.worked_out_s < played.end_s
    assert waiting.playing


def test_a_consumer_reads_the_records_delivered_by_the_clock_once_each_in_order(
    played: Playback, clock: Clock
) -> None:
    played.command(PlaybackCommand.PLAY)
    clock.now += 15.0  # a day and a half
    cut = played.records_after(0, ALL)
    now = cut.state.simulated_now

    delivered = [r.delivered_at or r.timestamp for r in cut.records]
    assert cut.records and max(delivered) <= now
    assert delivered == sorted(delivered)
    assert len({r.observation_id for r in cut.records}) == len(cut.records) == cut.next
    assert not cut.has_more
    # The sensors' own samples, every other one.
    readings = [r for r in cut.records if r.sensor_id]
    assert readings and all(
        (r.timestamp - cut.state.started_at).total_seconds() % EVERY_S == 0 for r in readings
    )
    # Nothing new until the clock moves; a repoll gives the same, and pages
    # of a batch make it whole.
    assert played.records_after(cut.next, ALL).records == ()
    assert played.records_after(0, ALL).records == cut.records
    first = played.records_after(0, PAGE)
    rest = played.records_after(first.next, ALL)
    assert first.has_more and first.next == PAGE
    assert first.records + rest.records == cut.records


def test_each_reading_is_the_one_the_viewers_sensor_log_has_then(
    simulator: Simulator, played: Playback, clock: Clock
) -> None:
    played.command(PlaybackCommand.PLAY)
    clock.now += 12.0
    cut = played.records_after(0, ALL)
    later = [r for r in cut.records if r.sensor_id][-1]
    moment = (later.timestamp - cut.state.started_at).total_seconds()

    # The viewer's log of that day, each sample, as the sensor panel asks for it.
    viewers = sensors.observations(simulator, RunRequest(SCENARIO), until_s=cut.state.time_s)
    same = [o for o in viewers.observations if o.observation_id == later.observation_id]
    assert viewers.run_id == played.run_id
    assert same == [later]
    assert moment % EVERY_S == 0


def test_the_viewers_frame_and_the_consumers_records_name_one_run_and_one_instant(
    simulator: Simulator, played: Playback, clock: Clock
) -> None:
    played.command(PlaybackCommand.PLAY)
    clock.now += 13.0  # into the run's second day
    cut = played.records_after(0, ALL)
    now = cut.state

    # The viewer draws the run at the clock's moment, as it asks the API.
    frame = respond(simulator, "GET", f"/api/scenarios/{SCENARIO}/climate/state?t={now.time_s}")
    assert frame.status == 200 and isinstance(frame.body, dict)
    assert frame.body["run_id"] == now.run_id
    assert frame.body["at"] == now.simulated_now.isoformat().replace("+00:00", "Z")
    assert (
        run_state.run_state(simulator, RunRequest(SCENARIO), until_s=now.time_s).day == now.day == 1
    )
    assert {r.source.source_id for r in cut.records} == {now.run_id}


def test_a_playback_stopped_works_out_nothing_more(simulator: Simulator, clock: Clock) -> None:
    run = Playback(simulator, SCENARIO, seconds_per_day=10.0, every_s=EVERY_S, clock=clock)
    run.begin()
    assert run.wait_for(1, timeout_s=120)

    # Stopped while it works out its next day.
    run.stop()

    # Its worker has ended, the day it had under way with it: nothing of
    # the run is worked out beside what a test or the API does next.
    assert not run._worker.is_alive()
    assert run._worker.name == f"playback of {run.run_id}"


def test_a_run_played_to_its_end_stops_there(simulator: Simulator, clock: Clock) -> None:
    run = Playback(simulator, SCENARIO, seconds_per_day=1.0, every_s=DAY_S, clock=clock)
    run.begin()
    try:
        assert run.wait_for(DAYS, timeout_s=300)
        run.command(PlaybackCommand.PLAY)
        clock.now += 1_000.0
        ended = run.state()
        assert ended.time_s == run.end_s
        assert not ended.playing
        assert run.command(PlaybackCommand.PLAY).playing is False
    finally:
        run.stop()


def test_a_playback_plays_and_is_paused_and_paced(played: Playback) -> None:
    started = played.command(PlaybackCommand.PLAY)
    assert started.playing is True
    assert started.epoch == 0
    assert started.run_id.startswith(f"{SCENARIO}-climate-")

    assert played.command(PlaybackCommand.PAUSE).playing is False
    assert played.set_pace(5.0).seconds_per_day == 5
    with pytest.raises(NotFound):
        Playback(played._simulator, "nowhere")


@pytest.mark.slow
def test_the_reference_greenhouse_s_second_day_is_one_run_for_the_viewer_and_a_consumer(
    simulator: Simulator,
    clock: Clock,
) -> None:
    # The demo's scenario, by its own schedule and weather.
    _a_second_day_is_one_run_for_the_viewer_and_a_consumer(simulator, clock, "reference_greenhouse")


def test_a_second_day_is_one_run_for_the_viewer_and_a_consumer(
    simulator: Simulator,
    clock: Clock,
) -> None:
    _a_second_day_is_one_run_for_the_viewer_and_a_consumer(simulator, clock, TENDED)


def _a_second_day_is_one_run_for_the_viewer_and_a_consumer(
    simulator: Simulator, clock: Clock, scenario_id: str
) -> None:
    """A day on, at noon, the viewer's frame and the consumer's latest record
    agree."""
    run = Playback(simulator, scenario_id, seconds_per_day=10.0, clock=clock)
    run.begin()
    try:
        assert run.wait_for(2, timeout_s=300)
        run.command(PlaybackCommand.PLAY)
        clock.now += 15.0
        cut = run.records_after(0, ALL)
        now = cut.state
        frame = respond(
            simulator, "GET", f"/api/scenarios/{scenario_id}/climate/state?t={now.time_s}"
        )
        assert isinstance(frame.body, dict)
        assert (frame.body["run_id"], frame.body["day"]) == (now.run_id, now.day) == (run.run_id, 1)
        assert frame.body["at"] == now.simulated_now.isoformat().replace("+00:00", "Z")
        latest = cut.records[-1]
        assert latest.source.source_id == now.run_id
        assert (
            now.simulated_now - timedelta(seconds=playback.CONSUMER_CADENCE_S)
            < latest.timestamp
            <= now.simulated_now
        )
        # The heat its heater gave, hour by hour, each delivered as its hour
        # ended, up to the clock (P10.3).
        heat = [
            r
            for r in cut.records
            if r.observation_type == ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2
        ]
        hours = int(now.time_s // 3600)
        assert [r.timestamp for r in heat] == [
            run.start + timedelta(hours=hour) for hour in range(1, hours + 1)
        ]
        assert sum(r.value for r in heat) > 0
    finally:
        run.stop()


def test_time_spent_waiting_for_a_day_is_not_banked(simulator: Simulator, clock: Clock) -> None:
    # Days published by hand, at moments the test chooses.
    run = Playback(simulator, SCENARIO, seconds_per_day=10.0, clock=clock)
    assert run.work_day(0)
    run.command(PlaybackCommand.PLAY)
    clock.now += 30.0
    assert run.state().time_s == DAY_S  # waiting at the first day's end
    clock.now += 100.0  # a long wait, nobody asking
    assert run.work_day(1)
    clock.now += 5.0
    # Half a day into the second, whatever the wait: the clock plays its
    # pace from the day's arrival.
    later = run.state()
    assert later.time_s == 1.5 * DAY_S
    # At a day's end, the day is the one it ends, as the run's clock says.
    clock.now += 100.0
    ended = run.state()
    assert (ended.time_s, ended.day) == (2 * DAY_S, 1)


def test_a_pace_is_a_finite_number_of_seconds(simulator: Simulator, played: Playback) -> None:
    for pace in (math.inf, math.nan, 0.0, -1.0):
        with pytest.raises(InvalidRequest):
            played.set_pace(pace)
        with pytest.raises(InvalidRequest):
            Playback(simulator, SCENARIO, seconds_per_day=pace)


def test_a_run_that_cannot_be_worked_out_is_the_simulator_s_failure(
    simulator: Simulator, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> None:
        raise ArithmeticError("a numerical failure")

    monkeypatch.setattr("greenhouse_sim.services.playback.delivered_between", broken)
    run = Playback(simulator, SCENARIO, clock=clock)
    assert not run.work_day(0)
    with pytest.raises(PlaybackFailed):
        run.state()

    def refused(*_: object, **__: object) -> None:
        raise NotFound("no such run")

    monkeypatch.setattr("greenhouse_sim.services.playback.delivered_between", refused)
    other = Playback(simulator, SCENARIO, clock=clock)
    assert not other.work_day(0)
    with pytest.raises(PlaybackFailed, match="no such run"):
        other.state()


def _working(scenario_id: str) -> bool:
    """Whether a playback of the scenario is still being worked out by a
    thread, in this process."""
    return any(
        thread.name.startswith(f"playback of {scenario_id}-") for thread in threading.enumerate()
    )


# How soon a playback stopped mid-day has stopped: its day of the reference
# greenhouse takes some ten seconds to work out, a moment of it a fraction.
STOPS_WITHIN_S = 2.0
# How far into its first day the playback is let get before it is stopped.
INTO_THE_DAY_S = 0.5


def test_a_playback_stopped_leaves_the_day_it_was_working_out(simulator: Simulator) -> None:
    found = Playback(simulator, "reference_greenhouse", seconds_per_day=600.0)
    found.begin()
    time.sleep(INTO_THE_DAY_S)
    assert not found.wait_for(1, timeout_s=0)

    stopping = time.monotonic()
    found.stop()

    assert time.monotonic() - stopping < STOPS_WITHIN_S
    assert not _working("reference_greenhouse")


# How long a test waits for a thread it expects to finish.
WAIT_S = 5.0
# A shorter bound on stopping, for the tests of it.
QUICK_STOP_WAIT_S = 0.3


def test_stopping_a_playback_stuck_in_a_moment_is_bounded(
    simulator: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(playback, "STOP_WAIT_S", QUICK_STOP_WAIT_S)
    release = threading.Event()
    reached = threading.Event()

    def stuck(*args: object, **kwargs: object) -> object:
        reached.set()
        release.wait(WAIT_S)
        raise RuntimeError("let go")

    monkeypatch.setattr(playback, "delivered_between", stuck)
    found = Playback(simulator, PACKAGED, seconds_per_day=600.0)
    found.begin()
    try:
        assert reached.wait(WAIT_S)
        stopping = time.monotonic()
        found.stop()
        took = time.monotonic() - stopping
    finally:
        release.set()

    assert took < 2 * QUICK_STOP_WAIT_S


def test_a_playback_stopped_while_its_heat_is_worked_out_publishes_no_day(
    simulator: Simulator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Its own scenario, which no other test here plays back.
    found = Playback(simulator, "airflow_box", seconds_per_day=600.0)

    def stopped_meanwhile(*args: object, **kwargs: object) -> object:
        # From its own worker's thread: told to stop, without waiting for itself.
        found.stop()
        return heat_log.heat_records(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(playback, "heat_records", stopped_meanwhile)
    found.begin()
    found.stop()

    assert found.state().worked_out_s == 0.0
