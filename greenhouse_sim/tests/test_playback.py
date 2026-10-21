"""A scenario's own run played back against one clock (P10.2, decision
0041): the viewer and a consumer follow the same run, and the clock never
passes what is worked out."""

from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from greenhouse_protocol.enums import ObservationType

from greenhouse_sim.api.routes import respond
from greenhouse_sim.api.server import create_server
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import playback, run_state, sensors
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.playback import Playback, PlaybackCommand, PlaybackFailed
from greenhouse_sim.services.runs import RunRequest

SCENARIO = "climate_box"
EVERY_S = 300.0
# Every record there is, in one batch.
ALL = 10**6


class Clock:
    """A clock a test moves by hand, in real seconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def played(clock: Clock) -> Iterator[Playback]:
    """The climate box's run, its first two days worked out and no more, a
    day played in 10 real seconds."""
    run = Playback(SCENARIO, seconds_per_day=10.0, every_s=EVERY_S, clock=clock)
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
    # The sensors' own samples, every fifth minute of their minute-by-minute
    # ones.
    assert all(
        (r.timestamp - cut.state.started_at).total_seconds() % EVERY_S == 0 for r in cut.records
    )
    # Nothing new until the clock moves; a repoll gives the same, and pages
    # of a batch make it whole.
    assert played.records_after(cut.next, ALL).records == ()
    assert played.records_after(0, ALL).records == cut.records
    first = played.records_after(0, 100)
    rest = played.records_after(first.next, ALL)
    assert first.has_more and first.next == 100
    assert first.records + rest.records == cut.records


def test_each_reading_is_the_one_the_viewers_sensor_log_has_then(
    played: Playback, clock: Clock
) -> None:
    played.command(PlaybackCommand.PLAY)
    clock.now += 12.0
    cut = played.records_after(0, ALL)
    later = cut.records[-1]
    moment = (later.timestamp - cut.state.started_at).total_seconds()

    # The viewer's log of that day, minute by minute, as the sensor panel
    # asks for it.
    viewers = sensors.observations(RunRequest(SCENARIO), until_s=cut.state.time_s)
    same = [o for o in viewers.observations if o.observation_id == later.observation_id]
    assert viewers.run_id == played.run_id
    assert same == [later]
    assert moment % EVERY_S == 0


def test_the_viewers_frame_and_the_consumers_records_name_one_run_and_one_instant(
    played: Playback, clock: Clock
) -> None:
    played.command(PlaybackCommand.PLAY)
    clock.now += 13.0  # into the run's second day
    cut = played.records_after(0, ALL)
    now = cut.state

    # The viewer draws the run at the clock's moment, as it asks the API.
    frame = respond("GET", f"/api/scenarios/{SCENARIO}/climate/state?t={now.time_s}")
    assert frame.status == 200 and isinstance(frame.body, dict)
    assert frame.body["run_id"] == now.run_id
    assert frame.body["at"] == now.simulated_now.isoformat().replace("+00:00", "Z")
    assert run_state.run_state(RunRequest(SCENARIO), until_s=now.time_s).day == now.day == 1
    assert {r.source.source_id for r in cut.records} == {now.run_id}


def test_a_restart_is_a_new_epoch_of_the_same_run_from_its_start(
    played: Playback, clock: Clock
) -> None:
    played.command(PlaybackCommand.PLAY)
    clock.now += 8.0
    before = played.records_after(0, ALL)

    restarted = played.command(PlaybackCommand.RESTART)
    assert (restarted.epoch, restarted.time_s, restarted.playing) == (1, 0.0, True)
    # At its start again: only what was delivered at its first instant.
    anew = played.records_after(0, ALL)
    assert {r.delivered_at or r.timestamp for r in anew.records} == {restarted.started_at}
    assert anew.records == before.records[: len(anew.records)]
    clock.now += 8.0
    again = played.records_after(0, ALL)
    assert again.state.epoch == 1
    assert again.records == before.records


def test_a_playback_stopped_works_out_nothing_more(clock: Clock) -> None:
    run = Playback(SCENARIO, seconds_per_day=10.0, every_s=EVERY_S, clock=clock)
    run.begin()
    assert run.wait_for(1, timeout_s=120)

    # Stopped while it works out its next day.
    run.stop()

    # Its worker has ended, the day it had under way with it: nothing of
    # the run is worked out beside what a test or the API does next.
    assert not run._worker.is_alive()
    assert run._worker.name == f"playback of {run.run_id}"


def test_a_run_played_to_its_end_stops_there(clock: Clock) -> None:
    run = Playback(SCENARIO, seconds_per_day=1.0, every_s=DAY_S, clock=clock)
    run.begin()
    try:
        assert run.wait_for(14, timeout_s=300)
        run.command(PlaybackCommand.PLAY)
        clock.now += 1_000.0
        ended = run.state()
        assert ended.time_s == run.end_s
        assert not ended.playing
        assert run.command(PlaybackCommand.PLAY).playing is False
    finally:
        run.stop()


def test_the_api_starts_a_playback_and_commands_it(no_playbacks: Callable[[], None]) -> None:
    assert respond("GET", f"/api/scenarios/{SCENARIO}/playback").status == 404
    started = respond("POST", f"/api/scenarios/{SCENARIO}/playback/start?seconds_per_day=600")
    assert started.status == 200 and isinstance(started.body, dict)
    assert started.body["playing"] is True
    assert started.body["epoch"] == 0
    assert str(started.body["run_id"]).startswith(f"{SCENARIO}-climate-")

    paused = respond("POST", f"/api/scenarios/{SCENARIO}/playback/pause")
    assert isinstance(paused.body, dict) and paused.body["playing"] is False
    paced = respond("POST", f"/api/scenarios/{SCENARIO}/playback/pace?seconds_per_day=5")
    assert isinstance(paced.body, dict) and paced.body["seconds_per_day"] == 5
    assert respond("POST", f"/api/scenarios/{SCENARIO}/playback/rewind").status == 404
    assert (
        respond("POST", f"/api/scenarios/{SCENARIO}/playback/pace?seconds_per_day=0").status == 400
    )
    assert (
        respond("POST", f"/api/scenarios/{SCENARIO}/playback/pace?seconds_per_day=x").status == 400
    )
    assert respond("POST", "/api/scenarios/nowhere/playback/start").status == 404


@pytest.mark.slow
def test_the_reference_greenhouse_s_second_day_is_one_run_for_the_viewer_and_a_consumer(
    clock: Clock,
) -> None:
    # The demo's scenario, by its own schedule and weather: a day on, at
    # noon, the viewer's frame and the consumer's latest record agree.
    run = Playback("reference_greenhouse", seconds_per_day=10.0, clock=clock)
    run.begin()
    try:
        assert run.wait_for(2, timeout_s=300)
        run.command(PlaybackCommand.PLAY)
        clock.now += 15.0
        cut = run.records_after(0, ALL)
        now = cut.state
        frame = respond("GET", f"/api/scenarios/reference_greenhouse/climate/state?t={now.time_s}")
        assert isinstance(frame.body, dict)
        assert (frame.body["run_id"], frame.body["day"]) == (now.run_id, now.day) == (run.run_id, 1)
        assert frame.body["at"] == now.simulated_now.isoformat().replace("+00:00", "Z")
        latest = cut.records[-1]
        assert latest.source.source_id == now.run_id
        assert (
            now.simulated_now - timedelta(seconds=EVERY_S) < latest.timestamp <= now.simulated_now
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


def test_time_spent_waiting_for_a_day_is_not_banked(clock: Clock) -> None:
    # Days published by hand, at moments the test chooses.
    run = Playback(SCENARIO, seconds_per_day=10.0, clock=clock)
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


def test_a_pace_is_a_finite_number_of_seconds(no_playbacks: Callable[[], None]) -> None:
    assert respond("POST", f"/api/scenarios/{SCENARIO}/playback/start").status == 200
    for pace in ("1e309", "inf", "nan", "-1"):
        refused = respond("POST", f"/api/scenarios/{SCENARIO}/playback/pace?seconds_per_day={pace}")
        assert refused.status == 400, pace


def test_a_start_at_a_pace_refused_starts_nothing(no_playbacks: Callable[[], None]) -> None:
    for pace in ("0", "-1", "nan"):
        refused = respond(
            "POST", f"/api/scenarios/{SCENARIO}/playback/start?seconds_per_day={pace}"
        )
        assert refused.status == 400, pace
    assert playback.playbacks() == []
    assert respond("GET", f"/api/scenarios/{SCENARIO}/playback").status == 404


def test_a_run_that_cannot_be_worked_out_is_the_simulator_s_failure(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> None:
        raise ArithmeticError("a numerical failure")

    monkeypatch.setattr("greenhouse_sim.services.playback.delivered_between", broken)
    run = Playback(SCENARIO, clock=clock)
    assert not run.work_day(0)
    with pytest.raises(PlaybackFailed):
        run.state()

    def refused(*_: object) -> None:
        raise NotFound("no such run")

    monkeypatch.setattr("greenhouse_sim.services.playback.delivered_between", refused)
    other = Playback(SCENARIO, clock=clock)
    assert not other.work_day(0)
    with pytest.raises(NotFound):
        other.state()


def test_the_runs_played_back_go_with_the_server_that_played_them(
    no_playbacks: Callable[[], None],
) -> None:
    server = create_server(0)
    playback.start(SCENARIO, 600.0)
    assert playback.state(SCENARIO).playing
    server.server_close()
    with pytest.raises(NotFound):
        playback.state(SCENARIO)
