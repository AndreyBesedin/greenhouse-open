"""Scenarios played live for the viewer, and their Server-Sent Events stream."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest

from greenhouse_sim.api.live import LiveFrame, LiveRun
from greenhouse_sim.api.server import SimulatorServer, create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

CONFIG = SCENARIO_REGISTRY["gh_demo"]
NOON_ON_DAY_ZERO = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _run() -> LiveRun:
    """A run that is never started, so the test steps it by hand."""
    return LiveRun(CONFIG, seconds_per_day=60.0)


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
    url = f"http://{host!s}:{port}/api/scenarios/gh_demo/live"

    with urllib.request.urlopen(url, timeout=5) as stream:
        assert stream.headers["Content-Type"] == "text/event-stream"
        assert stream.readline() == b"retry: 1000\n"
        frames = _frames(iter(stream.readline, b""), count=3)

    sequences = [frame.sequence for frame in frames]
    assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
    assert all(frame.snapshot.greenhouse_id == "gh_demo" for frame in frames)


def test_an_unknown_scenario_has_no_live_stream(server: SimulatorServer) -> None:
    host, port = server.server_address[:2]

    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(f"http://{host!s}:{port}/api/scenarios/nope/live", timeout=5)

    assert refused.value.code == HTTPStatus.NOT_FOUND
    assert json.load(refused.value)["error"]


def test_closing_the_server_stops_its_live_runs() -> None:
    server = create_server(port=0, seconds_per_day=0.05)
    run = server.live.run_for(CONFIG)

    server.server_close()

    assert run.stopped
