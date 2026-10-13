"""The one command that starts the simulator and its viewer (P09.9): it
starts both, opens the reference scenario on its opening day, and stops
both, whichever way it is stopped."""

import json
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from scripts import demo

# A stand-in for either server: a static file server on a port.
STAND_IN = (sys.executable, "-m", "http.server", "--bind", demo.LOOPBACK)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((demo.LOOPBACK, 0))
        port: int = probe.getsockname()[1]
        return port


@pytest.fixture
def served(tmp_path: Path) -> Path:
    """A folder the stand-ins serve: the API's health and scenario list."""
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "health").write_text('{"status": "ok"}')
    listed = [{"id": "climate_box", "opening_day": None}, {"id": demo.REFERENCE, "opening_day": 80}]
    (tmp_path / "api" / "scenarios").write_text(json.dumps(listed))
    return tmp_path


@pytest.fixture
def ports() -> Iterator[tuple[int, int]]:
    yield _free_port(), _free_port()


def _stand_ins(served: Path, ports: Sequence[int]) -> demo.Servers:
    return demo.Servers([((*STAND_IN, str(port)), served, {}) for port in ports])


def test_both_start_answer_and_stop_together(served: Path, ports: tuple[int, int]) -> None:
    servers = _stand_ins(served, ports)
    urls = [f"http://{demo.LOOPBACK}:{port}/api/health" for port in ports]
    servers.wait_until_answering(urls, timeout_s=20)
    assert all(demo.answers(url) for url in urls)
    assert not any(demo.port_free(port) for port in ports)

    stop = threading.Event()
    threading.Timer(0.5, stop.set).start()
    assert servers.run_until(stop) == 0

    assert all(process.poll() is not None for process in servers.processes)
    assert all(demo.port_free(port) for port in ports)


def test_when_one_stops_the_other_is_stopped_too(served: Path, ports: tuple[int, int]) -> None:
    servers = demo.Servers(
        [
            (
                (sys.executable, "-c", "import time; time.sleep(0.5); raise SystemExit(3)"),
                served,
                {},
            ),
            ((*STAND_IN, str(ports[1])), served, {}),
        ]
    )

    assert servers.run_until(threading.Event()) == 3
    assert all(process.poll() is not None for process in servers.processes)
    assert demo.port_free(ports[1])


def test_a_server_that_stops_before_answering_is_said(served: Path) -> None:
    servers = demo.Servers([((sys.executable, "-c", "raise SystemExit(1)"), served, {})])

    with pytest.raises(demo.NotReady, match="stopped before it answered"):
        servers.wait_until_answering(["http://127.0.0.1:9/never"], timeout_s=20)
    servers.stop()


def test_it_opens_the_reference_greenhouse_at_noon_on_its_opening_day(
    served: Path, ports: tuple[int, int]
) -> None:
    servers = _stand_ins(served, ports[:1])
    api = f"http://{demo.LOOPBACK}:{ports[0]}"
    try:
        servers.wait_until_answering([f"{api}/api/health"], timeout_s=20)
        address = demo.opening_address(api, "http://localhost:5173")
    finally:
        servers.stop()

    noon_on_day_80 = 80 * 86_400 + 12 * 3_600
    assert address == (
        f"http://localhost:5173/?scenario=reference_greenhouse&field=climate&t={noon_on_day_80}"
    )


def test_a_port_in_use_is_said_with_what_to_do() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind((demo.LOOPBACK, 0))
        held.listen()
        port = held.getsockname()[1]
        found = demo.problems(api_port=port, viewer_port=_free_port())

    assert f"Port {port}, for the API, is in use: stop what holds it, or pass --api-port." in found


@pytest.mark.slow
@pytest.mark.skipif(
    not (demo.WEB / "node_modules").is_dir(), reason="the viewer's packages are not installed"
)
def test_the_command_starts_the_api_and_the_viewer_and_stops_both() -> None:
    api_port, viewer_port = _free_port(), _free_port()
    command = subprocess.Popen(
        [
            sys.executable,
            str(demo.ROOT / "scripts" / "demo.py"),
            "--no-browser",
            f"--api-port={api_port}",
            f"--viewer-port={viewer_port}",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert command.stdout is not None
        # The servers say what they say first, on the same output.
        said = next(line for line in command.stdout if line.startswith("The reference greenhouse"))
        assert said.startswith(f"The reference greenhouse: http://localhost:{viewer_port}/?")
        assert demo.answers(f"http://{demo.LOOPBACK}:{api_port}/api/health")
        assert demo.answers(f"http://localhost:{viewer_port}/")
    finally:
        command.send_signal(signal.SIGINT)
        assert command.wait(timeout=30) == 0
    time.sleep(0.5)
    assert demo.port_free(api_port) and demo.port_free(viewer_port)
