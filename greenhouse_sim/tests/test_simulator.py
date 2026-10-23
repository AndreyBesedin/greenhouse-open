"""A simulator's state, in one object (decision 0048): its scenarios and
its live runs, closed with it; made by the server, or given to it."""

import ast
import threading
import time
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.api.server import create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.services import playback
from greenhouse_sim.services.live import LiveRun
from greenhouse_sim.services.simulator import Simulator

CONFIG = SCENARIO_REGISTRY["climate_box"]
# Quick enough for a run to step while a test looks.
QUICK_SECONDS_PER_DAY = 0.01
# How long a test waits for a thread it expects to finish.
WAIT_S = 5.0
# How long a test gives a thread it expects to be still waiting.
STILL_WAITING_S = 0.3


def _pacing() -> list[str]:
    """The live runs being paced by a thread, in this process."""
    return [thread.name for thread in threading.enumerate() if thread.name.startswith("live run")]


def test_a_simulator_knows_the_packaged_scenarios_and_its_own() -> None:
    with Simulator() as simulator, Simulator() as other:
        simulator.catalogue.register(CONFIG.model_copy(update={"greenhouse_id": "drafted_box"}))

        assert simulator.catalogue.ids() == [*PACKAGED.ids(), "drafted_box"]
        assert other.catalogue.ids() == PACKAGED.ids()


def test_a_simulator_can_be_given_its_catalogue() -> None:
    catalogue = Catalogue()

    with Simulator(catalogue) as simulator:
        assert simulator.catalogue is catalogue


def test_closing_a_simulator_stops_its_live_runs_and_waits_for_them() -> None:
    simulator = Simulator(seconds_per_day=QUICK_SECONDS_PER_DAY)
    run = simulator.live.run_for(CONFIG)
    assert "live run of climate_box" in _pacing()

    simulator.close()
    simulator.close()

    assert simulator.closed and run.stopped
    assert _pacing() == []
    with pytest.raises(RuntimeError, match="closed"):
        simulator.live.run_for(CONFIG)


def test_a_simulator_used_as_a_context_is_closed_after_it() -> None:
    with Simulator(seconds_per_day=QUICK_SECONDS_PER_DAY) as simulator:
        simulator.live.run_for(CONFIG)

    assert simulator.closed and _pacing() == []


def test_a_server_closes_the_simulator_it_made() -> None:
    server = create_server(port=0, seconds_per_day=QUICK_SECONDS_PER_DAY)
    server.simulator.live.run_for(CONFIG)

    server.server_close()

    assert server.simulator.closed and _pacing() == []


def test_a_server_leaves_a_simulator_it_was_given_to_its_giver() -> None:
    with Simulator(seconds_per_day=QUICK_SECONDS_PER_DAY) as simulator:
        server = create_server(port=0, simulator=simulator)
        run = simulator.live.run_for(CONFIG)

        server.server_close()

        assert server.simulator is simulator
        assert not simulator.closed and not run.stopped
    assert run.stopped and _pacing() == []


def test_a_second_close_waits_for_the_first(
    held_in_a_day: Callable[[LiveRun, threading.Event], threading.Event],
) -> None:
    simulator = Simulator(seconds_per_day=QUICK_SECONDS_PER_DAY)
    run = simulator.live.run_for(CONFIG)
    release = threading.Event()
    begun = held_in_a_day(run, release)
    first = threading.Thread(target=simulator.close)
    second = threading.Thread(target=simulator.close)
    try:
        assert begun.wait(WAIT_S)
        first.start()
        deadline = time.monotonic() + WAIT_S
        while not run.stopped and time.monotonic() < deadline:
            time.sleep(0.01)
        second.start()
        second.join(STILL_WAITING_S)

        assert second.is_alive()
    finally:
        release.set()
    first.join(WAIT_S)
    second.join(WAIT_S)
    assert simulator.closed and _pacing() == []


def test_closing_a_simulator_stops_its_playbacks_and_starts_none_after() -> None:
    simulator = Simulator()
    playback.start(simulator, "climate_box", 600.0)

    simulator.close()

    assert simulator.playbacks.all() == []
    assert not any(thread.name.startswith("playback of") for thread in threading.enumerate())
    with pytest.raises(RuntimeError, match="closed"):
        playback.start(simulator, "climate_box", 600.0)


def test_each_simulator_plays_its_own_runs_back() -> None:
    with Simulator() as simulator, Simulator() as other:
        playback.start(simulator, "climate_box", 600.0, hold=True)

        assert [found.scenario_id for found in simulator.playbacks.all()] == ["climate_box"]
        assert other.playbacks.all() == []
        assert simulator.cursors is not other.cursors


def test_a_scenario_registered_with_a_simulator_is_answered_by_it_alone() -> None:
    drafted = CONFIG.model_copy(update={"greenhouse_id": "drafted_box"})
    with Simulator() as simulator, Simulator() as other:
        simulator.catalogue.register(drafted)

        listed = respond(simulator, "GET", "/api/scenarios").body
        assert isinstance(listed, list)
        assert [summary["id"] for summary in listed if isinstance(summary, dict)][-1] == (
            "drafted_box"
        )
        assert respond(simulator, "GET", "/api/scenarios/drafted_box/climate/house?t=0").status == (
            HTTPStatus.OK
        )
        assert respond(other, "GET", "/api/scenarios/drafted_box/climate/house?t=0").status == (
            HTTPStatus.NOT_FOUND
        )


# What would hold state for the whole process, made as a module is
# imported: a store, a threading primitive, or what keeps a simulator's.
PROCESS_STATE = frozenset(
    {
        "Store",
        "Lock",
        "RLock",
        "Condition",
        "Event",
        "Semaphore",
        "Thread",
        "Playbacks",
        "Cursors",
        "LiveRuns",
        "Catalogue",
    }
)
# Where a simulator's state is its own (decision 0048).
OWN_STATE_PACKAGES = ("services", "scenarios", "core")
PACKAGE = Path(__file__).resolve().parents[1] / "greenhouse_sim"


def test_no_module_keeps_state_for_the_whole_process() -> None:
    made = []
    for package in OWN_STATE_PACKAGES:
        for path in sorted((PACKAGE / package).rglob("*.py")):
            for node in ast.parse(path.read_text()).body:
                value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
                if not isinstance(value, ast.Call):
                    continue
                called = value.func
                name = (
                    called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
                )
                if name in PROCESS_STATE:
                    made.append(f"{path.relative_to(PACKAGE)}:{node.lineno} {name}")
    assert made == []
