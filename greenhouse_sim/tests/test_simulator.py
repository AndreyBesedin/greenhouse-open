"""A simulator's state, in one object (decision 0048): its scenarios and
its live runs, closed with it; made by the server, or given to it."""

import threading

import pytest

from greenhouse_sim.api.server import create_server
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.services.simulator import Simulator

CONFIG = SCENARIO_REGISTRY["climate_box"]
# Quick enough for a run to step while a test looks.
QUICK_SECONDS_PER_DAY = 0.01


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
