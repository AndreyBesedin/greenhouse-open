"""A simulator's state, in one object (decision 0048): its scenarios and
the runs it plays back, closed with it; made by the server, or given to it."""

import ast
import errno
import threading
from http import HTTPStatus
from pathlib import Path

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.api.server import create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.services import playback
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

CONFIG = SCENARIO_REGISTRY["climate_box"]
# A pace slow enough that a playback is still working its days out when the
# test closes it.
SECONDS_PER_DAY = 600.0
# How long a test waits for a thread it expects to finish.
WAIT_S = 5.0
# How long a test gives a thread it expects to be still waiting.
STILL_WAITING_S = 0.3


def _playing() -> list[str]:
    """The playbacks working days out on a thread, in this process."""
    return [
        thread.name for thread in threading.enumerate() if thread.name.startswith("playback of")
    ]


def test_a_simulator_knows_the_packaged_scenarios_and_its_own() -> None:
    with Simulator() as simulator, Simulator() as other:
        simulator.catalogue.register(CONFIG.model_copy(update={"greenhouse_id": "drafted_box"}))

        assert simulator.catalogue.ids() == [*PACKAGED.ids(), "drafted_box"]
        assert other.catalogue.ids() == PACKAGED.ids()


def test_a_simulator_can_be_given_its_catalogue() -> None:
    catalogue = Catalogue()

    with Simulator(catalogue) as simulator:
        assert simulator.catalogue is catalogue


def test_a_simulator_used_as_a_context_is_closed_after_it() -> None:
    with Simulator() as simulator:
        playback.start(simulator, CONFIG.greenhouse_id, SECONDS_PER_DAY)

    assert simulator.closed and _playing() == []


def test_a_server_closes_the_simulator_it_made() -> None:
    server = create_server(port=0)
    playback.start(server.simulator, CONFIG.greenhouse_id, SECONDS_PER_DAY)

    server.server_close()

    assert server.simulator.closed and _playing() == []


def test_a_server_leaves_a_simulator_it_was_given_to_its_giver() -> None:
    with Simulator() as simulator:
        server = create_server(port=0, simulator=simulator)
        playback.start(simulator, CONFIG.greenhouse_id, SECONDS_PER_DAY)

        server.server_close()

        assert server.simulator is simulator
        assert not simulator.closed and simulator.playbacks.all() != []
    assert _playing() == []


def test_a_second_close_waits_for_the_first(monkeypatch: pytest.MonkeyPatch) -> None:
    simulator = Simulator()
    release, begun = threading.Event(), threading.Event()
    stop = simulator.playbacks.close

    def held() -> None:
        # The first close is held while it stops the playbacks; a second
        # would not be, if it got this far.
        if not begun.is_set():
            begun.set()
            release.wait(WAIT_S)
        stop()

    monkeypatch.setattr(simulator.playbacks, "close", held)
    first = threading.Thread(target=simulator.close)
    second = threading.Thread(target=simulator.close)
    try:
        first.start()
        assert begun.wait(WAIT_S)
        second.start()
        second.join(STILL_WAITING_S)

        assert second.is_alive()
    finally:
        release.set()
    first.join(WAIT_S)
    second.join(WAIT_S)
    assert simulator.closed and not first.is_alive() and not second.is_alive()


def test_a_port_already_taken_is_reported_as_such() -> None:
    taken = create_server(port=0)
    try:
        with pytest.raises(OSError) as raised:
            create_server(port=taken.server_address[1])
    finally:
        taken.server_close()

    assert raised.value.errno == errno.EADDRINUSE


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


def test_two_simulators_registering_one_identifier_each_run_their_own() -> None:
    """Two simulators, each with a scenario of its own under one identifier
    (#318's review): each answers its own house's air, under its own run's
    identity, worked out in climate runs of its own; never the other's,
    kept."""
    warm = CONFIG.climate.model_copy(update={"start_temperature_c": 24.0})
    cold = CONFIG.climate.model_copy(update={"start_temperature_c": 8.0})
    house = "/api/scenarios/drafted_box/climate/house?t=0"
    with Simulator() as simulator, Simulator() as other:
        simulator.catalogue.register(
            CONFIG.model_copy(update={"greenhouse_id": "drafted_box", "climate": warm})
        )
        other.catalogue.register(
            CONFIG.model_copy(update={"greenhouse_id": "drafted_box", "climate": cold})
        )

        first = respond(simulator, "GET", house)
        second = respond(other, "GET", house)

        assert (first.status, second.status) == (HTTPStatus.OK, HTTPStatus.OK)
        assert _first_air(first.body) == pytest.approx(24.0)
        assert _first_air(second.body) == pytest.approx(8.0)
        run = RunRequest("drafted_box")
        assert air_through_a_run(simulator, run)[1] != air_through_a_run(other, run)[1]
        assert simulator.climate_runs is not other.climate_runs
        assert len(simulator.climate_runs.values()) == len(other.climate_runs.values()) >= 1


def _first_air(trace: object) -> float:
    """The house's air temperature at its first moment, as the API answers
    its trace."""
    assert isinstance(trace, dict)
    controlled = trace["controlled"]
    assert isinstance(controlled, dict)
    first = controlled["temperature_c"][0]
    assert isinstance(first, float)
    return first


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
