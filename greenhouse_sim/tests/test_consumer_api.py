"""The consumer interface served from a running scenario (P10.4): the
protocol's routes and payloads (decision 0040), answered from a run played
back against a clock (decision 0041), with observed records only."""

import ast
import json
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from datetime import datetime, timedelta
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
from greenhouse_protocol.enums import EventSource, EventType
from greenhouse_protocol.event import Event
from greenhouse_protocol.greenhouse import GreenhouseDescription
from greenhouse_protocol.observation import Observation

from greenhouse_sim.api.consumer import consumer_respond
from greenhouse_sim.api.server import create_server
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import playback
from greenhouse_sim.services.playback import Epochs, PlaybackCommand
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

SCENARIO = "climate_box"
PACKAGE = Path(__file__).resolve().parents[1] / "greenhouse_sim"
PREFIX = "/consumer/v1"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _get(simulator: Simulator, path: str) -> Mapping[str, object]:
    answer = consumer_respond(simulator, "GET", path)
    assert answer is not None and answer.status == 200, answer
    assert isinstance(answer.body, dict)
    return answer.body


@pytest.fixture
def clock(simulator: Simulator, no_playbacks: Callable[[], None]) -> Iterator[Clock]:
    """The climate box played back on a clock a test moves, its first two
    days worked out, a day played in 10 real seconds."""
    moved = Clock()
    playback.start(simulator, SCENARIO, 10.0, clock=moved)
    played = playback.playback(simulator, SCENARIO)
    assert played.wait_for(2, timeout_s=120)
    played.stop()
    yield moved


def _run_id(simulator: Simulator) -> str:
    return playback.state(simulator, SCENARIO).run_id


def test_a_consumer_finds_the_run_its_greenhouse_and_its_clock(
    simulator: Simulator, clock: Clock
) -> None:
    runs = RunList.model_validate(_get(simulator, f"{PREFIX}/runs"))
    (run,) = runs.runs
    assert run == RunDescriptor.model_validate(_get(simulator, f"{PREFIX}/runs/{run.run_id}"))
    assert check_run(run) == []
    assert (run.run_id, run.epoch, run.scenario) == (_run_id(simulator), 0, SCENARIO)
    assert run.clock.playing and run.clock.day == 0

    house = GreenhouseDescription.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run.run_id}/greenhouse")
    )
    assert house.greenhouse_id == run.greenhouse_id == "climate_box"
    assert (house.layout.rows, house.layout.columns, len(house.plants)) == (2, 16, 32)
    assert house.plants[16].plant_id == "climate_box_plant_017"
    assert (house.plants[16].row, house.plants[16].position_in_row) == (2, 1)


def test_polls_follow_the_clock_densely_and_never_twice(simulator: Simulator, clock: Clock) -> None:
    run_id = _run_id(simulator)
    polls: list[ObservationBatch] = []

    def poll(after: int, limit: int | None = None) -> ObservationBatch:
        query = f"?after={after}" + ("" if limit is None else f"&limit={limit}")
        batch = ObservationBatch.model_validate(
            _get(simulator, f"{PREFIX}/runs/{run_id}/observations{query}")
        )
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


def test_a_restart_is_a_new_epoch_and_a_stale_cursor_is_answered_empty(
    simulator: Simulator, clock: Clock
) -> None:
    run_id = _run_id(simulator)
    clock.now += 5.0
    before = ObservationBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run_id}/observations")
    )

    playback.command(simulator, SCENARIO, PlaybackCommand.RESTART)
    clock.now += 2.0
    stale = ObservationBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run_id}/observations?after={before.next}")
    )
    assert (stale.epoch, stale.after, stale.next, stale.observations) == (
        1,
        before.next,
        before.next,
        (),
    )
    again = ObservationBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run_id}/observations?after=0")
    )
    assert again.epoch == 1 and again.records == before.records[: len(again.records)]
    assert check_polls([before, stale, again]) == []


def test_a_playback_rearranged_is_a_new_run_a_consumer_reads_from_its_first_day(
    simulator: Simulator,
    clock: Clock,
) -> None:
    # The viewer following the run moves the heater and starts the run over
    # with it (#271): the consumer's run is gone, and the scenario's new run
    # is listed in its place, from its first day.
    first = _run_id(simulator)
    clock.now += 5.0
    before = ObservationBatch.model_validate(_get(simulator, f"{PREFIX}/runs/{first}/observations"))
    assert before.records

    playback.command(simulator, SCENARIO, PlaybackCommand.RESTART, "default~heater:-1:0.5")

    (run,) = RunList.model_validate(_get(simulator, f"{PREFIX}/runs")).runs
    assert run.run_id != first and run.scenario == SCENARIO
    assert (run.epoch, run.clock.day, run.clock.simulated_now) == (0, 0, run.started_at)
    gone = consumer_respond(
        simulator, "GET", f"{PREFIX}/runs/{first}/observations?after={before.next}"
    )
    assert gone is not None and gone.status == 404
    assert playback.playback(simulator, SCENARIO).wait_for(1, timeout_s=120)
    clock.now += 5.0
    batch = ObservationBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run.run_id}/observations")
    )
    assert batch.records and batch.epoch == 0
    assert {r.source.source_id for r in batch.records} == {run.run_id}
    assert min(r.delivered_at or r.timestamp for r in batch.records) == run.started_at
    assert check_batch(batch) == [] and check_polls([batch]) == []


def test_events_are_a_log_of_their_own(simulator: Simulator, clock: Clock) -> None:
    clock.now += 5.0
    events = EventBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{_run_id(simulator)}/events?after=0")
    )
    assert (events.after, events.next, events.events) == (0, 0, ())
    assert check_batch(events) == []


def test_what_is_not_a_consumer_route_or_request_is_refused(
    simulator: Simulator, clock: Clock
) -> None:
    run_id = _run_id(simulator)
    cases = {
        ("GET", f"{PREFIX}/runs/unknown"): 404,
        ("GET", f"{PREFIX}/runs/unknown/observations"): 404,
        ("GET", f"{PREFIX}/runs/{run_id}/truth"): 404,
        ("GET", f"{PREFIX}/runs/{run_id}/scene"): 404,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?after=x"): 400,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?after=-1"): 400,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?limit=0"): 400,
        ("GET", f"{PREFIX}/runs/{run_id}/observations?after="): 400,
        ("GET", f"{PREFIX}/runs/{run_id}/events?limit="): 400,
        ("POST", f"{PREFIX}/runs"): 405,
    }
    for (method, path), status in cases.items():
        answer = consumer_respond(simulator, method, path)
        assert answer is not None and answer.status == status, (method, path)
        assert isinstance(answer.body, dict) and "detail" in answer.body
    assert consumer_respond(simulator, "GET", "/api/scenarios") is None


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


def test_a_consumer_follows_a_progressing_run_over_http(
    simulator: Simulator, no_playbacks: Callable[[], None]
) -> None:
    server = create_server(0, simulator=simulator)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    base = f"http://{host!s}:{port}{PREFIX}"
    try:
        playback.start(simulator, SCENARIO, 2.0)
        assert playback.playback(simulator, SCENARIO).wait_for(1, timeout_s=120)
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


def _fetch(url: str) -> Mapping[str, object]:
    with urllib.request.urlopen(url, timeout=30) as answer:  # noqa: S310 - the test's own loopback server
        body = json.loads(answer.read())
    assert isinstance(body, dict)
    return body


def test_a_held_playback_waits_for_a_play_command(
    simulator: Simulator, clock: Clock, no_playbacks: Callable[[], None]
) -> None:
    no_playbacks()
    held = playback.start(simulator, SCENARIO, 10.0, hold=True, clock=clock)
    assert held.playing is False
    clock.now += 50.0
    assert playback.state(simulator, SCENARIO).time_s == 0.0
    assert playback.command(simulator, SCENARIO, PlaybackCommand.PLAY).playing


def test_the_run_s_events_reach_a_consumer_by_the_clock(
    simulator: Simulator, monkeypatch: pytest.MonkeyPatch, no_playbacks: Callable[[], None]
) -> None:
    # A harvest an hour into each day after the first, as the crop's log
    # would give it, in place of the climate box's simple crop's none.
    def harvest(
        simulator: Simulator, run: RunRequest, day: int, start: datetime, run_id: str
    ) -> tuple[list[Observation], list[Event]]:
        scenario_id = run.scenario_id
        if day == 0:
            return [], []
        at = start + timedelta(seconds=day * DAY_S + 3600)
        return [], [
            Event(
                event_id=f"sim_{scenario_id}_plant_001_{day}_harvest",
                greenhouse_id=scenario_id,
                plant_id=f"{scenario_id}_plant_001",
                timestamp=at,
                event_type=EventType.HARVEST,
                source=EventSource.SIMULATION,
                parameters={"harvested_mass_g": 120.0, "harvested_fruit_count": 2},
            )
        ]

    monkeypatch.setattr("greenhouse_sim.services.playback.crop_records", harvest)
    moved = Clock()
    playback.start(simulator, SCENARIO, 10.0, clock=moved)
    assert playback.playback(simulator, SCENARIO).wait_for(3, timeout_s=120)
    run_id = _run_id(simulator)
    moved.now += 10.0  # the start of day 1: its harvest is an hour off
    early = EventBatch.model_validate(_get(simulator, f"{PREFIX}/runs/{run_id}/events?after=0"))
    assert early.events == ()
    moved.now += 10.0  # day 2's start: day 1's harvest is in
    later = EventBatch.model_validate(_get(simulator, f"{PREFIX}/runs/{run_id}/events?after=0"))
    assert [e.parameters["harvested_mass_g"] for e in later.events] == [120.0]
    assert later.next == 1 and check_polls([early, later]) == []


def test_a_producer_started_again_is_a_new_epoch_of_its_run(
    simulator: Simulator, clock: Clock, tmp_path: Path, no_playbacks: Callable[[], None]
) -> None:
    # The run's epochs kept across the producer's restarts, as the API keeps
    # them for the runs it plays back.
    no_playbacks()
    epochs = Epochs(tmp_path)
    playback.start(simulator, SCENARIO, 10.0, clock=clock, epochs=epochs)
    assert playback.playback(simulator, SCENARIO).wait_for(1, timeout_s=120)
    run_id = _run_id(simulator)
    clock.now += 5.0
    before = ObservationBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run_id}/observations")
    )
    assert before.epoch == 0 and before.records

    # The producer stops and starts again: the same run, a new epoch.
    no_playbacks()
    playback.start(simulator, SCENARIO, 10.0, clock=clock, epochs=epochs)
    assert playback.playback(simulator, SCENARIO).wait_for(1, timeout_s=120)
    clock.now += 8.0  # past where the client's cursor stood, in the new epoch
    run = RunDescriptor.model_validate(_get(simulator, f"{PREFIX}/runs/{run_id}"))
    assert run.epoch == 1
    stale = ObservationBatch.model_validate(
        _get(simulator, f"{PREFIX}/runs/{run_id}/observations?after={before.next}")
    )
    assert (stale.epoch, stale.next, stale.observations) == (1, before.next, ())
    # A restart of the playback itself counts on from there.
    assert playback.command(simulator, SCENARIO, PlaybackCommand.RESTART).epoch == 2
    assert Epochs(tmp_path).next(run_id) == 3
