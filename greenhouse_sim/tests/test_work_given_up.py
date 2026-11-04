"""A request whose client has gone stops costing: its thread gives its long
work up at the next step, what it worked out stays, and the air at a moment is
the same whatever was asked and given up before."""

import socket
import struct
import threading
import time
from collections.abc import Callable, Iterator
from http.server import ThreadingHTTPServer

import numpy as np
import pytest

from greenhouse_sim.api.server import create_server
from greenhouse_sim.core import wanted
from greenhouse_sim.core.wanted import NoLongerWanted, give_up_if_unwanted, wanted_while
from greenhouse_sim.services.climate_runs import climate_day
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.stores import Store

BOX = ("climate_box", "default", "default", (("heater", 1.0),), (), (), ())
HOUR_S = 3600.0
DAY_S = 86_400.0
# Far longer than a request takes to notice its client has gone, and far
# shorter than working out the air of a far moment takes.
WAIT_S = 30.0
POLL_S = 0.01


@pytest.fixture
def always_look(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wanted, "LOOK_EVERY_S", 0.0)


def _wanted_for(looks: int) -> Callable[[], bool]:
    """What says the work is wanted for so many looks, and then not."""
    left = iter(range(looks))
    return lambda: next(left, None) is not None


def test_work_nothing_says_is_wanted_is_never_given_up() -> None:
    give_up_if_unwanted()
    with wanted_while(lambda: False), wanted_while(None):
        give_up_if_unwanted()


def test_a_thread_looks_at_most_every_so_often() -> None:
    looks = 0

    def still_wanted() -> bool:
        nonlocal looks
        looks += 1
        return True

    with wanted_while(still_wanted):
        for _ in range(100):
            give_up_if_unwanted()

    assert looks < 100


def test_what_a_thread_is_wanted_by_is_its_own() -> None:
    other_gave_up: list[bool] = []

    def other() -> None:
        try:
            give_up_if_unwanted()
            other_gave_up.append(False)
        except NoLongerWanted:
            other_gave_up.append(True)

    with wanted_while(lambda: False):
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()

    assert other_gave_up == [False]


@pytest.mark.usefixtures("always_look")
def test_a_house_given_up_keeps_its_steps_and_gives_the_same_air() -> None:
    moment = 6 * HOUR_S
    given_up = climate_day(Simulator(), BOX).house
    worked_whole = climate_day(Simulator(), BOX).house

    with wanted_while(_wanted_for(looks=30)), pytest.raises(NoLongerWanted):
        given_up.air_at(moment)

    # What it worked out stays: its steps up to where it gave up, no further.
    assert 0 < given_up._moments[-1] < moment
    assert given_up._stretch is None
    assert given_up.air_at(moment) == worked_whole.air_at(moment)


@pytest.mark.usefixtures("always_look")
def test_a_grid_run_given_up_keeps_its_steps_and_gives_the_same_air() -> None:
    moment = 0.5 * HOUR_S
    given_up = climate_day(Simulator(), BOX).run
    worked_whole = climate_day(Simulator(), BOX).run

    # A look for each step of its own, and for each of the house it follows.
    with wanted_while(_wanted_for(looks=10)), pytest.raises(NoLongerWanted):
        given_up.air_at(moment)

    assert given_up._stretch is None
    assert 0.0 < max(given_up._kept) < moment
    air, whole = given_up.air_at(moment), worked_whole.air_at(moment)
    assert np.array_equal(air.temperature, whole.temperature)
    assert np.array_equal(air.humidity, whole.humidity)
    assert np.array_equal(air.co2, whole.co2)


def test_a_checkpoint_given_does_not_wait_for_a_request_working_the_house_on() -> None:
    house = climate_day(Simulator(), BOX).house
    moment, air = 6 * HOUR_S, climate_day(Simulator(), BOX).house.air_at(6 * HOUR_S)
    # A request working the house's air on holds this lock throughout, while
    # a seek gives the house its checkpoint.
    with house._working:
        seeded = threading.Thread(target=house.seed, args=(moment, air))
        seeded.start()
        seeded.join(WAIT_S)
        held_up = seeded.is_alive()

    assert not held_up
    assert house.air_at(moment) == air
    assert house._moments == [0.0, moment]


def test_a_value_others_may_wait_for_is_made_whoever_asked_it_leaves() -> None:
    store: Store[str, str] = Store("values")

    def make(_: list[tuple[str, str]]) -> str:
        give_up_if_unwanted()
        return "made"

    with wanted_while(lambda: False):
        assert store.made_once("key", make) == "made"


@pytest.fixture
def server() -> Iterator[ThreadingHTTPServer]:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _latest_step(server: ThreadingHTTPServer) -> float:
    """How far its kept climate runs' houses have been worked."""
    kept = server.simulator.climate_runs.values()  # type: ignore[attr-defined]
    return max((day.house._moments[-1] for _, day in kept), default=0.0)


def test_a_request_whose_client_left_stops_working(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    let_go = threading.Event()

    def closed(request: socket.socket) -> None:
        ThreadingHTTPServer.shutdown_request(server, request)
        let_go.set()

    monkeypatch.setattr(server, "shutdown_request", closed)
    host, port = server.server_address[:2]
    far = 115 * DAY_S
    begun = _latest_step(server)

    with socket.create_connection((str(host), port), timeout=WAIT_S) as client:
        client.sendall(
            f"GET /api/scenarios/reference_greenhouse/climate/house?t={far:.0f} HTTP/1.1\r\n"
            "Host: localhost\r\n\r\n".encode()
        )
        deadline = time.monotonic() + WAIT_S
        while _latest_step(server) <= begun and time.monotonic() < deadline:
            time.sleep(POLL_S)
        assert _latest_step(server) > begun
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))

    assert let_go.wait(WAIT_S)
    assert _latest_step(server) < far
    log = capsys.readouterr().err
    assert "Traceback" not in log
