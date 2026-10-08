"""Scenarios played live for the viewer, and their Server-Sent Events stream."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import control
from greenhouse_sim.api.server import SimulatorServer, create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.live import SPEEDS, LiveFrame, LiveRun, LiveRuns

CONFIG = SCENARIO_REGISTRY["climate_box"]
NOON_ON_DAY_ZERO = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


# Fast enough that a playing run moves on many times while a test waits.
QUICK_SECONDS_PER_DAY = 0.01
# How long a test waits to see that a paused run does not move.
QUIET_SECONDS = 0.2


def _run() -> LiveRun:
    """A run that is never started, so the test steps it by hand."""
    return LiveRun(CONFIG, seconds_per_day=60.0)


@pytest.fixture
def playing() -> Iterator[LiveRun]:
    """A run that is started and plays quickly."""
    run = LiveRun(CONFIG, seconds_per_day=QUICK_SECONDS_PER_DAY)
    run.start()
    yield run
    run.stop()


def _without_sequence(frame: LiveFrame) -> dict[str, object]:
    return frame.model_dump(exclude={"sequence"})


def test_a_run_starts_before_day_one() -> None:
    frame = _run().latest()

    assert (frame.sequence, frame.day, frame.timestamp) == (0, 0, NOON_ON_DAY_ZERO)
    assert frame.snapshot.simulated_day == 0


def test_each_step_is_a_new_frame_one_simulated_day_later() -> None:
    run = _run()

    frames = [run.advance() for _ in range(3)]

    assert [frame.sequence for frame in frames] == [1, 2, 3]
    assert [frame.day for frame in frames] == [1, 2, 3]
    assert [frame.snapshot.simulated_day for frame in frames] == [1, 2, 3]
    assert frames[-1].timestamp == NOON_ON_DAY_ZERO + timedelta(days=3)


def test_a_run_starts_over_after_its_last_day() -> None:
    run = _run()
    first_pass = [run.advance() for _ in range(CONFIG.duration_days)]

    restarted = run.advance()

    assert first_pass[-1].day == CONFIG.duration_days
    assert restarted.day == 0
    assert restarted.sequence == CONFIG.duration_days + 1
    assert restarted.snapshot == _run().latest().snapshot


def test_the_same_day_always_looks_the_same() -> None:
    first, second = _run(), _run()

    for _ in range(5):
        a, b = first.advance(), second.advance()
        assert a == b


def test_a_run_starts_playing_at_the_servers_pace() -> None:
    frame = _run().latest()
    assert (frame.playing, frame.speed) == (True, 1.0)


def test_a_paused_run_holds_its_day(playing: LiveRun) -> None:
    assert playing.frame_after(0, timeout=5) is not None

    paused = playing.pause()

    assert not paused.playing
    assert playing.frame_after(paused.sequence, timeout=QUIET_SECONDS) is None
    assert playing.latest() == paused


def test_playing_again_moves_on_from_the_same_day(playing: LiveRun) -> None:
    paused = playing.pause()

    resumed = playing.play()
    later = playing.frame_after(resumed.sequence, timeout=5)

    assert resumed.playing and resumed.day == paused.day
    assert later is not None and later.day != paused.day


def test_a_step_advances_exactly_one_day(playing: LiveRun) -> None:
    paused = playing.pause()

    stepped = playing.advance()

    assert stepped.sequence == paused.sequence + 1
    assert stepped.day == paused.day + 1 or (paused.day, stepped.day) == (CONFIG.duration_days, 0)
    assert not stepped.playing
    assert playing.frame_after(stepped.sequence, timeout=QUIET_SECONDS) is None


def test_a_reset_returns_to_the_state_before_day_one() -> None:
    fresh, run = _run(), _run()
    first_days = [run.advance() for _ in range(5)]

    reset = run.reset()
    second_days = [run.advance() for _ in range(5)]

    assert reset.day == 0 and reset.sequence == len(first_days) + 1
    assert _without_sequence(reset) == _without_sequence(fresh.latest())
    assert [_without_sequence(day) for day in second_days] == [
        _without_sequence(day) for day in first_days
    ]


def test_a_reset_keeps_a_paused_run_paused() -> None:
    run = _run()
    run.pause()

    assert not run.reset().playing


def test_a_run_plays_at_any_speed_it_offers() -> None:
    run = _run()

    assert [run.set_speed(speed).speed for speed in SPEEDS] == list(SPEEDS)
    with pytest.raises(ValueError, match="speed must be one of"):
        run.set_speed(3.0)


def test_a_faster_run_moves_on_sooner() -> None:
    run = LiveRun(CONFIG, seconds_per_day=1.0)
    run.start()
    try:
        faster = run.set_speed(max(SPEEDS))
        # At the server's own pace the next day is a second away.
        later = run.frame_after(faster.sequence, timeout=0.6)
    finally:
        run.stop()

    assert later is not None and later.day == faster.day + 1


def test_every_command_is_a_new_frame_for_every_viewer() -> None:
    run = _run()

    frames = [run.pause(), run.advance(), run.set_speed(2.0), run.reset(), run.play()]

    assert [frame.sequence for frame in frames] == [1, 2, 3, 4, 5]
    assert [(frame.day, frame.playing, frame.speed) for frame in frames] == [
        (0, False, 1.0),
        (1, False, 1.0),
        (1, False, 2.0),
        (0, False, 2.0),
        (0, True, 2.0),
    ]


def test_waiting_returns_the_next_frame_or_nothing() -> None:
    run = _run()

    assert run.frame_after(None, timeout=0) == run.latest()
    assert run.frame_after(0, timeout=0.01) is None

    threading.Timer(0.05, run.advance).start()
    frame = run.frame_after(0, timeout=5)

    assert frame is not None and frame.day == 1


def test_a_stopped_run_wakes_its_waiters() -> None:
    run = _run()
    threading.Timer(0.05, run.stop).start()

    assert run.frame_after(0, timeout=5) is None
    assert run.stopped


@pytest.fixture
def server() -> Iterator[SimulatorServer]:
    server = create_server(port=0, seconds_per_day=0.05)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _frames(lines: Iterator[bytes], count: int) -> list[LiveFrame]:
    frames = []
    event = None
    for raw in lines:
        line = raw.decode().rstrip("\n")
        if line.startswith("event: "):
            event = line.removeprefix("event: ")
        elif line.startswith("data: ") and event == "frame":
            frames.append(LiveFrame.model_validate_json(line.removeprefix("data: ")))
            if len(frames) == count:
                return frames
    raise AssertionError(f"the stream ended after {len(frames)} frames")


def test_a_live_scenario_streams_a_frame_per_simulated_day(server: SimulatorServer) -> None:
    host, port = server.server_address[:2]
    url = f"http://{host!s}:{port}/api/scenarios/climate_box/live"

    with urllib.request.urlopen(url, timeout=5) as stream:
        assert stream.headers["Content-Type"] == "text/event-stream"
        assert stream.readline() == b"retry: 1000\n"
        frames = _frames(iter(stream.readline, b""), count=3)

    sequences = [frame.sequence for frame in frames]
    assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
    assert all(frame.snapshot.greenhouse_id == "climate_box" for frame in frames)


def test_an_unknown_scenario_has_no_live_stream(server: SimulatorServer) -> None:
    host, port = server.server_address[:2]

    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(f"http://{host!s}:{port}/api/scenarios/nope/live", timeout=5)

    assert refused.value.code == HTTPStatus.NOT_FOUND
    assert json.load(refused.value)["error"]


@pytest.fixture
def runs() -> Iterator[LiveRuns]:
    runs = LiveRuns(seconds_per_day=60.0)
    yield runs
    runs.stop()


@pytest.mark.parametrize(
    ("command", "day", "playing", "speed"),
    [
        ("pause", 0, False, 1.0),
        ("play", 0, True, 1.0),
        ("step", 1, True, 1.0),
        ("reset", 0, True, 1.0),
        ("speed?multiplier=2", 0, True, 2.0),
        ("speed?multiplier=0.25", 0, True, 0.25),
    ],
)
def test_a_command_answers_with_the_runs_new_state(
    runs: LiveRuns, command: str, day: int, playing: bool, speed: float
) -> None:
    response = control(f"/api/scenarios/climate_box/live/{command}", runs)

    assert response is not None and response.status == HTTPStatus.OK
    assert isinstance(response.body, dict)
    assert (response.body["day"], response.body["playing"], response.body["speed"]) == (
        day,
        playing,
        speed,
    )
    assert "snapshot" not in response.body


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/scenarios/nope/live/pause", HTTPStatus.NOT_FOUND),
        ("/api/scenarios/climate_box/live/rewind", HTTPStatus.NOT_FOUND),
        ("/api/scenarios/climate_box/live/speed", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/climate_box/live/speed?multiplier=3", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/climate_box/live/speed?multiplier=fast", HTTPStatus.BAD_REQUEST),
        ("/api/scenarios/climate_box/live/speed?multiplier=1&multiplier=2", HTTPStatus.BAD_REQUEST),
    ],
)
def test_a_command_that_cannot_be_applied_is_refused_with_a_reason(
    runs: LiveRuns, path: str, status: HTTPStatus
) -> None:
    response = control(path, runs)

    assert response is not None and response.status == status
    assert isinstance(response.body, dict) and response.body["error"]


def test_other_paths_are_not_commands(runs: LiveRuns) -> None:
    assert control("/api/scenarios/climate_box/live", runs) is None
    assert control("/api/health", runs) is None


def test_a_command_over_http_reaches_the_stream(server: SimulatorServer) -> None:
    host, port = server.server_address[:2]
    live = f"http://{host!s}:{port}/api/scenarios/climate_box/live"

    pause = urllib.request.Request(f"{live}/pause", method="POST")
    with urllib.request.urlopen(pause, timeout=5) as answer:
        state = json.load(answer)
    with urllib.request.urlopen(live, timeout=5) as stream:
        stream.readline()
        [frame] = _frames(iter(stream.readline, b""), count=1)

    assert state["playing"] is False
    assert (frame.sequence, frame.day, frame.playing) == (
        state["sequence"],
        state["day"],
        False,
    )


def test_closing_the_server_stops_its_live_runs() -> None:
    server = create_server(port=0, seconds_per_day=0.05)
    run = server.live.run_for(CONFIG)

    server.server_close()

    assert run.stopped
