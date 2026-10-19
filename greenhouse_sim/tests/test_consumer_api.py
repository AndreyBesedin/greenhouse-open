"""The consumer interface served from a running scenario (P10.4): the
protocol's routes and payloads (decision 0040), answered from a run played
back against a clock (decision 0041), with observed records only."""

import ast
import json
import threading
import time
import urllib.request
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ObservationBatch,
    RunDescriptor,
    RunList,
    check_batch,
    check_polls,
    check_run,
)
from greenhouse_protocol.greenhouse import GreenhouseDescription

from greenhouse_sim.api.consumer import consumer_respond
from greenhouse_sim.api.server import create_server
from greenhouse_sim.services import playback
from greenhouse_sim.services.playback import PlaybackCommand

SCENARIO = "climate_box"
PACKAGE = Path(__file__).resolve().parents[1] / "greenhouse_sim"
PREFIX = "/consumer/v1"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _get(path: str) -> Mapping[str, object]:
    answer = consumer_respond("GET", path)
    assert answer is not None and answer.status == 200, answer
    assert isinstance(answer.body, dict)
    return answer.body


@pytest.fixture
def clock() -> Iterator[Clock]:
    """The climate box played back on a clock a test moves, its first two
    days worked out, a day played in 10 real seconds."""
    playback.forget_playbacks()
    moved = Clock()
    playback.start(SCENARIO, 10.0, clock=moved)
    played = playback.playback(SCENARIO)
    assert played.wait_for(2, timeout_s=120)
    played.stop()
    yield moved
    playback.forget_playbacks()


def _run_id() -> str:
    return playback.state(SCENARIO).run_id


def test_a_consumer_finds_the_run_its_greenhouse_and_its_clock(clock: Clock) -> None:
    runs = RunList.model_validate(_get(f"{PREFIX}/runs"))
    (run,) = runs.runs
    assert run == RunDescriptor.model_validate(_get(f"{PREFIX}/runs/{run.run_id}"))
    assert check_run(run) == []
    assert (run.run_id, run.epoch, run.scenario) == (_run_id(), 0, SCENARIO)
    assert run.clock.playing and run.clock.day == 0

    house = GreenhouseDescription.model_validate(_get(f"{PREFIX}/runs/{run.run_id}/greenhouse"))
    assert house.greenhouse_id == run.greenhouse_id == "climate_box"
    assert (house.layout.rows, house.layout.columns, len(house.plants)) == (2, 16, 32)
    assert house.plants[16].plant_id == "climate_box_plant_017"
    assert (house.plants[16].row, house.plants[16].position_in_row) == (2, 1)


def test_polls_follow_the_clock_densely_and_never_twice(clock: Clock) -> None:
    run_id = _run_id()
    polls: list[ObservationBatch] = []

    def poll(after: int, limit: int | None = None) -> ObservationBatch:
        query = f"?after={after}" + ("" if limit is None else f"&limit={limit}")
        batch = ObservationBatch.model_validate(_get(f"{PREFIX}/runs/{run_id}/observations{query}"))
        polls.append(batch)
        return batch

    clock.now += 5.0  # half a day
    first = poll(0)
    assert first.records and first.next == len(first.records)
    assert poll(0).records == first.records  # a repoll repeats, rewrites nothing
    assert poll(first.next).records == ()  # nothing new until the clock moves
    clock.now += 5.0
    second = poll(first.next)
    assert second.records and second.simulated_now > first.simulated_now
    assert all(check_batch(batch) == [] for batch in polls)
    assert check_polls(polls) == []

    # Another client, ten at a time: a cut batch says so, and the next poll
    # goes on from it.
    polls.clear()
    cut = poll(0, limit=10)
    assert (cut.next, cut.has_more) == (10, True)
    assert poll(cut.next, limit=10).records == (first.records + second.records)[10:20]
    assert check_polls(polls) == []


def test_a_restart_is_a_new_epoch_and_a_stale_cursor_is_answered_empty(clock: Clock) -> None:
    run_id = _run_id()
    clock.now += 5.0
    before = ObservationBatch.model_validate(_get(f"{PREFIX}/runs/{run_id}/observations"))

    playback.command(SCENARIO, PlaybackCommand.RESTART)
    clock.now += 2.0
    stale = ObservationBatch.model_validate(
        _get(f"{PREFIX}/runs/{run_id}/observations?after={before.next}")
    )
    assert (stale.epoch, stale.after, stale.next, stale.observations) == (
        1,
        before.next,
        before.next,
        (),
    )
    again = ObservationBatch.model_validate(_get(f"{PREFIX}/runs/{run_id}/observations?after=0"))
    assert again.epoch == 1 and again.records == before.records[: len(again.records)]
    assert check_polls([before, stale, again]) == []


def test_events_are_a_log_of_their_own(clock: Clock) -> None:
    clock.now += 5.0
    events = EventBatch.model_validate(_get(f"{PREFIX}/runs/{_run_id()}/events?after=0"))
    assert (events.after, events.next, events.events) == (0, 0, ())
    assert check_batch(events) == []


def test_what_is_not_a_consumer_route_or_request_is_refused(clock: Clock) -> None:
    run_id = _run_id()
    cases = {
        ("GET", f"{PREFIX}/runs/unknown"): 404,
        ("GET", f"{PREFIX}/runs/unknown/observations"): 404,
        ("GET", f"{PREFIX}/runs/{run_id}/truth"): 404,
        ("GET", f"{PREFIX}/runs/{run_id}/scene"): 404,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?after=x"): 400,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?after=-1"): 400,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?limit=0"): 400,
        ("POST", f"{PREFIX}/runs"): 405,
    }
    for (method, path), status in cases.items():
        answer = consumer_respond(method, path)
        assert answer is not None and answer.status == status, (method, path)
        assert isinstance(answer.body, dict) and "detail" in answer.body
    assert consumer_respond("GET", "/api/scenarios") is None


def test_the_consumer_reaches_the_simulator_through_its_service_alone() -> None:
    # What a consumer can reach is what these two modules import: never the
    # run's truth, an evaluator, a scene or QA mode's state.
    reached = {
        "api/consumer.py": {
            "greenhouse_sim.api.responses",
            "greenhouse_sim.services",
            "greenhouse_sim.services.errors",
        },
        "services/consumer.py": {
            "greenhouse_sim.services",
            "greenhouse_sim.services.errors",
            "greenhouse_sim.services.playback",
            "greenhouse_sim.services.scenarios",
        },
    }
    for module, allowed in reached.items():
        tree = ast.parse((PACKAGE / module).read_text())
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("greenhouse_sim")
        }
        assert imported <= allowed, (module, imported - allowed)


def test_a_consumer_follows_a_progressing_run_over_http() -> None:
    playback.forget_playbacks()
    server = create_server(0, seconds_per_day=1.0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    base = f"http://{host!s}:{port}{PREFIX}"
    try:
        playback.start(SCENARIO, 2.0)
        assert playback.playback(SCENARIO).wait_for(1, timeout_s=120)
        runs = RunList.model_validate(_fetch(f"{base}/runs"))
        run_id = runs.runs[0].run_id
        assert host == "127.0.0.1"
        polls: list[ObservationBatch] = []
        after = 0
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            batch = ObservationBatch.model_validate(
                _fetch(f"{base}/runs/{run_id}/observations?after={after}")
            )
            polls.append(batch)
            after = batch.next
            time.sleep(0.5)
        assert polls[-1].simulated_now > polls[0].simulated_now
        assert sum(len(batch.records) for batch in polls) == after > 0
        assert check_polls(polls) == []
    finally:
        server.shutdown()
        server.server_close()
        playback.forget_playbacks()


def _fetch(url: str) -> Mapping[str, object]:
    with urllib.request.urlopen(url, timeout=30) as answer:  # noqa: S310 - the test's own loopback server
        body = json.loads(answer.read())
    assert isinstance(body, dict)
    return body
