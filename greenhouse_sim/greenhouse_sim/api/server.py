"""Serving the local API over HTTP, on this machine only.

    python -m greenhouse_sim.api [--port PORT] [--seconds-per-day SECONDS]

The browser viewer's development server forwards `/api` here, so the API
needs no cross-origin headers. It binds to the loopback interface: it is a
tool for a developer's own machine, not a service.

Live scenarios stream as Server-Sent Events (decision 0012): a `frame` event
per simulated day, and a comment now and then to keep the connection open.
"""

import argparse
import json
from collections.abc import Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, cast

from greenhouse_sim.api.live import DEFAULT_SECONDS_PER_DAY, LiveRun, LiveRuns
from greenhouse_sim.api.routes import Response, live_scenario, respond

LOOPBACK: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8765
# How long a quiet stream waits before sending a keep-alive comment.
KEEPALIVE_SECONDS: Final = 15.0
# How soon a viewer's browser should try again after losing the stream.
RECONNECT_AFTER_MS: Final = 1000


class SimulatorServer(ThreadingHTTPServer):
    """The API's server, holding the scenarios being played live."""

    daemon_threads = True

    def __init__(self, port: int, *, seconds_per_day: float) -> None:
        super().__init__((LOOPBACK, port), _Handler)
        self.live = LiveRuns(seconds_per_day=seconds_per_day)

    def server_close(self) -> None:
        self.live.stop()
        super().server_close()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        config = live_scenario(self.path)
        if config is not None:
            self._stream(cast(SimulatorServer, self.server).live.run_for(config))
            return
        self._send(respond("GET", self.path))

    def do_POST(self) -> None:
        self._send(respond("POST", self.path))

    def _send(self, response: Response) -> None:
        body = json.dumps(response.body).encode()
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, run: LiveRun) -> None:
        """Sends the run's frames as Server-Sent Events until either side stops."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        sequence: int | None = None
        try:
            self.wfile.write(f"retry: {RECONNECT_AFTER_MS}\n\n".encode())
            while not run.stopped:
                frame = run.frame_after(sequence, KEEPALIVE_SECONDS)
                if frame is None:
                    self.wfile.write(b": keep-alive\n\n")
                else:
                    self.wfile.write(f"event: frame\ndata: {frame.model_dump_json()}\n\n".encode())
                    sequence = frame.sequence
                self.wfile.flush()
        except BrokenPipeError, ConnectionResetError:
            pass


def create_server(
    port: int = DEFAULT_PORT, *, seconds_per_day: float = DEFAULT_SECONDS_PER_DAY
) -> SimulatorServer:
    """A server on the loopback interface; port 0 picks a free port."""
    return SimulatorServer(port, seconds_per_day=seconds_per_day)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the simulator's local API.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--seconds-per-day",
        type=float,
        default=DEFAULT_SECONDS_PER_DAY,
        help="how fast live scenarios play",
    )
    args = parser.parse_args(argv)

    server = create_server(args.port, seconds_per_day=args.seconds_per_day)
    host, port = server.server_address[:2]
    print(f"greenhouse-sim API on http://{host!s}:{port}/api", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
