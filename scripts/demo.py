"""Start the simulator and its viewer, and open the reference scenario (P09.9).

    uv run demo                              # the API on 8765, the viewer on 5173
    uv run demo --no-browser                 # without opening a browser
    uv run demo --api-port 8770 --viewer-port 5180
    uv run start                             # open the viewer's start page instead

It runs the simulator's local API (`python -m greenhouse_sim.api`) and the
viewer's development server (`npm run dev` in `greenhouse_sim/web`) side by
side, waits until both answer, and opens the reference greenhouse on its
opening day, at noon. Ctrl+C stops both, and so does either one stopping.
`uv run demo` runs it with the workspace's Python once `uv run setup` has
installed the viewer's packages (`docs/demo.md`). Standard library only.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "greenhouse_sim" / "web"
DEFAULT_API_PORT = 8765
DEFAULT_VIEWER_PORT = 5173
LOOPBACK = "127.0.0.1"
# The Python the simulator needs (decision 0003), and the Node the viewer's
# `.nvmrc` names (decision 0008).
PYTHON_NEEDED = (3, 14)
NODE_NEEDED = int((WEB / ".nvmrc").read_text().strip())
REFERENCE = "reference_greenhouse"
DAY_S = 86_400
NOON_S = 12 * 3_600
# How long each server has to answer once started, and how often it is asked.
READY_TIMEOUT_S = 120.0
POLL_S = 0.25
# How long a server has to stop once asked, before it is killed.
STOP_TIMEOUT_S = 10.0
HTTP_TIMEOUT_S = 2.0


class NotReady(RuntimeError):
    """Something the demo needs is missing; the message says what to do."""


def problems(api_port: int, viewer_port: int) -> list[str]:
    """What stops the demo from starting here, each with what to do."""
    found = []
    if sys.version_info < PYTHON_NEEDED:
        wanted = ".".join(map(str, PYTHON_NEEDED))
        found.append(f"Python {wanted} or newer is needed; this is {sys.version.split()[0]}.")
    if importlib.util.find_spec("greenhouse_sim") is None:
        found.append(
            "greenhouse-sim is not installed for this Python: run the demo with `uv run demo`"
        )
    node = shutil.which("node")
    if node is None or shutil.which("npm") is None:
        found.append(f"Node {NODE_NEEDED} and npm are needed: https://nodejs.org")
    else:
        version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
        major = int(version.strip().lstrip("v").split(".")[0] or 0)
        if major < NODE_NEEDED:
            found.append(f"Node {NODE_NEEDED} or newer is needed; this is {version.strip()}.")
    if not (WEB / "node_modules").is_dir():
        found.append("The viewer's packages are not installed: uv run setup")
    for name, port, flag in (
        ("the API", api_port, "--api-port"),
        ("the viewer", viewer_port, "--viewer-port"),
    ):
        if not port_free(port):
            found.append(f"Port {port}, for {name}, is in use: stop what holds it, or pass {flag}.")
    return found


def port_free(port: int) -> bool:
    """Whether nothing listens on `port` on this machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((LOOPBACK, port))
        except OSError:
            return False
    return True


def answers(url: str) -> bool:
    """Whether a server answers `url`, whatever it says."""
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S):
            return True
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False


def opening_address(api_url: str, viewer_url: str) -> str:
    """Where the viewer opens the reference greenhouse: its climate at noon
    on its kept opening day, as the scenario list opens it, or its start."""
    with urllib.request.urlopen(f"{api_url}/api/scenarios", timeout=HTTP_TIMEOUT_S) as reply:
        listed = json.load(reply)
    day = next((s.get("opening_day") for s in listed if s.get("id") == REFERENCE), None)
    if day is None:
        return f"{viewer_url}/?scenario={REFERENCE}"
    return f"{viewer_url}/?scenario={REFERENCE}&field=climate&t={day * DAY_S + NOON_S}"


class Servers:
    """Processes started side by side, each in a process group of its own,
    so that stopping one stops whatever it started too."""

    def __init__(self, commands: Sequence[tuple[Sequence[str], Path, dict[str, str]]]) -> None:
        self.processes = [
            subprocess.Popen(list(command), cwd=cwd, env=env, start_new_session=True)
            for command, cwd, env in commands
        ]

    def wait_until_answering(self, urls: Sequence[str], timeout_s: float = READY_TIMEOUT_S) -> None:
        """Waits until every URL answers; refused if a server stops first or
        does not answer in time."""
        deadline = time.monotonic() + timeout_s
        waiting = list(urls)
        while waiting:
            if self.stopped() is not None:
                raise NotReady("a server stopped before it answered; its output says why")
            if time.monotonic() > deadline:
                raise NotReady(f"no answer from {', '.join(waiting)} in {timeout_s:.0f} s")
            waiting = [url for url in waiting if not answers(url)]
            if waiting:
                time.sleep(POLL_S)

    def stopped(self) -> int | None:
        """The exit code of the first server found stopped, if any is."""
        for process in self.processes:
            code = process.poll()
            if code is not None:
                return code
        return None

    def run_until(self, stop: threading.Event) -> int:
        """Keeps both running until `stop` is set or one stops; then stops
        both, and gives the code of the one that stopped, or 0."""
        code = 0
        while not stop.is_set():
            stopped = self.stopped()
            if stopped is not None:
                code = stopped
                break
            stop.wait(POLL_S)
        self.stop()
        return code

    def stop(self) -> None:
        """Asks each server's process group to stop, and kills a group that
        has not stopped in time."""
        for process in self.processes:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        for process in self.processes:
            try:
                process.wait(timeout=STOP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--viewer-port", type=int, default=DEFAULT_VIEWER_PORT)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument(
        "--start-page",
        action="store_true",
        help="open the viewer's start page rather than the reference greenhouse",
    )
    parsed = parser.parse_args(arguments)
    found = problems(parsed.api_port, parsed.viewer_port)
    if found:
        print("The demo cannot start yet:", *(f"  - {problem}" for problem in found), sep="\n")
        return 1

    api_url = f"http://{LOOPBACK}:{parsed.api_port}"
    viewer_url = f"http://localhost:{parsed.viewer_port}"
    npm = shutil.which("npm") or "npm"
    servers = Servers(
        [
            (
                [sys.executable, "-m", "greenhouse_sim.api", "--port", str(parsed.api_port)],
                ROOT,
                dict(os.environ),
            ),
            (
                [npm, "run", "dev", "--", "--port", str(parsed.viewer_port), "--strictPort"],
                WEB,
                dict(os.environ, SIMULATOR_API_PORT=str(parsed.api_port)),
            ),
        ]
    )
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        servers.wait_until_answering([f"{api_url}/api/health", viewer_url])
    except NotReady as reason:
        servers.stop()
        print(f"The demo did not start: {reason}.")
        return 1
    if parsed.start_page:
        address, shown = viewer_url, "The viewer"
    else:
        address, shown = opening_address(api_url, viewer_url), "The reference greenhouse"
    print(f"{shown}: {address}\nCtrl+C stops the API and the viewer.", flush=True)
    if not parsed.no_browser:
        webbrowser.open(address)
    return servers.run_until(stop)


if __name__ == "__main__":
    sys.exit(main())
