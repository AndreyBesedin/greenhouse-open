"""Serving the local API over HTTP, on this machine only.

    python -m greenhouse_sim.api [--port PORT] [--seconds-per-day SECONDS] [--play SCENARIO]

The browser viewer's development server forwards `/api` here, so the API
needs no cross-origin headers. It binds to the loopback interface: it is a
tool for a developer's own machine, not a service.

The consumer interface's routes (`/consumer/v1`, `consumer`) answer before
the viewer's, `GET` only. `--play SCENARIO` plays a scenario's own run back
from its start (`services.playback`), for the viewer and a consumer.

Live scenarios stream as Server-Sent Events (decision 0012): a `frame` event
per simulated day, and a comment now and then to keep the connection open.
Commands for a live run (play, pause, step, reset, speed) are POST requests,
and so are a run's checkpoints, saved or uploaded as a JSON body.
A request the simulator fails on unexpectedly is answered 500, with the
failure in the server's log. Every answer says how long the simulator took
to give it, as a `Server-Timing` header's `sim` metric, in milliseconds
(P09.8), which the viewer's HUD shows for the latest request.
"""

import argparse
import json
import sys
import time
import traceback
from collections.abc import Callable, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, cast

from greenhouse_sim.api.consumer import consumer_respond
from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes import control, live_stream, respond
from greenhouse_sim.services import checkpoints, playback
from greenhouse_sim.services.live import DEFAULT_SECONDS_PER_DAY, LiveRun, LiveRuns

LOOPBACK: Final = "127.0.0.1"
# What a client is told when the simulator fails on its request unexpectedly.
UNEXPECTED_FAILURE: Final = "the simulator failed to answer; its log says why"
DEFAULT_PORT: Final = 8765
# How long a quiet stream waits before sending a keep-alive comment.
KEEPALIVE_SECONDS: Final = 15.0
# How soon a viewer's browser should try again after losing the stream.
RECONNECT_AFTER_MS: Final = 1000
# The `Server-Timing` metric that says how long the simulator took to answer.
SIMULATOR_METRIC: Final = "sim"
MS_PER_S: Final = 1000

# The largest request body the API reads, in bytes: a season's checkpoint,
# the largest body a viewer sends, is a megabyte or two.
MAX_BODY_BYTES: Final = 64 * 1024 * 1024
# How long the API waits on a client that has not sent what it said it
# would, in seconds, before it answers and closes the connection.
READ_TIMEOUT_S: Final = 30.0

# How many connections may wait to be accepted. A viewer asks for a scene,
# its fields and its CFD boundaries at once, and its browser tests open
# several viewers together; past this, macOS refuses a connection outright.
PENDING_CONNECTIONS: Final = 64


class SimulatorServer(ThreadingHTTPServer):
    """The API's server, holding the scenarios being played live."""

    daemon_threads = True
    request_queue_size = PENDING_CONNECTIONS

    def __init__(self, port: int, *, seconds_per_day: float) -> None:
        # Before binding: a server that fails to bind closes itself, which
        # stops its live runs, and then raises the bind's own error. None has
        # started yet.
        self.live = LiveRuns(seconds_per_day=seconds_per_day)
        super().__init__((LOOPBACK, port), _Handler)
        # The scenarios' kept opening days, so that their runs' later days
        # need not be worked out from their starts.
        for refused in checkpoints.load_openings():
            print(f"not kept: {refused}", file=sys.stderr)

    def server_close(self) -> None:
        self.live.stop()
        super().server_close()


class _Handler(BaseHTTPRequestHandler):
    timeout = READ_TIMEOUT_S

    def do_GET(self) -> None:
        started = time.perf_counter()
        consumers = self._safely(lambda: consumer_respond("GET", self.path))
        if consumers is not None:
            self._send(consumers, started)
            return
        stream = self._safely(lambda: live_stream(self.path, self._live))
        if isinstance(stream, LiveRun):
            self._stream(stream)
        elif stream is not None:
            self._send(stream, started)
        else:
            self._send(self._safely(lambda: respond("GET", self.path)), started)

    def do_POST(self) -> None:
        started = time.perf_counter()
        consumers = self._safely(lambda: consumer_respond("POST", self.path))
        if consumers is not None:
            self._send(consumers, started)
            return
        response = self._safely(lambda: control(self.path, self._live))
        if response is None:
            body = self._body()
            if isinstance(body, Response):
                response = body
            else:
                response = self._safely(lambda: respond("POST", self.path, body))
        self._send(response, started)

    def do_PUT(self) -> None:
        self._send(_refused_method(self.command), time.perf_counter())

    do_PATCH = do_DELETE = do_PUT

    def _body(self) -> bytes | Response:
        """The request's body, as long as its `Content-Length` says, or the
        refusal if that is not a length, is more than the API reads, or is
        more than the client sends."""
        declared = self.headers.get("Content-Length") or "0"
        if not declared.isdigit():
            return Response(
                HTTPStatus.BAD_REQUEST, {"error": f"Content-Length {declared!r} is not a length"}
            )
        length = int(declared)
        if length > MAX_BODY_BYTES:
            return Response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"a body of {length:,} bytes; the API reads {MAX_BODY_BYTES:,} at most"},
            )
        try:
            body = self.rfile.read(length)
        except TimeoutError:
            body = b""
        if len(body) < length:
            self.close_connection = True
            return Response(
                HTTPStatus.REQUEST_TIMEOUT,
                {"error": f"the body stopped short of the {length:,} bytes announced"},
            )
        return body

    @property
    def _live(self) -> LiveRuns:
        return cast(SimulatorServer, self.server).live

    def _safely[T](self, answer: Callable[[], T]) -> T | Response:
        """The route's answer, or a 500 if the simulator failed unexpectedly."""
        try:
            return answer()
        except Exception:  # every failure is answered, and logged
            self.log_error("failed to answer %s %s", self.command, self.path)
            traceback.print_exc()
            return Response(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": UNEXPECTED_FAILURE})

    def _send(self, response: Response, started: float) -> None:
        """Sends the answer, saying how long the simulator took to give it,
        from `started`, its JSON written. A client gone by then, as a viewer
        goes from a request it no longer wants, is let go."""
        body = json.dumps(response.body).encode()
        took_ms = (time.perf_counter() - started) * MS_PER_S
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Server-Timing", f"{SIMULATOR_METRIC};dur={took_ms:.1f}")
        try:
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError, ConnectionResetError:
            self.close_connection = True
            self.log_message('"%s": the client left before its answer', self.requestline)

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


def _refused_method(method: str) -> Response:
    return Response(
        HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"the API answers GET and POST, not {method}"}
    )


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
    parser.add_argument(
        "--play",
        action="append",
        default=[],
        metavar="SCENARIO",
        help="play a scenario's own run back from its start, for the viewer and a consumer",
    )
    parser.add_argument(
        "--hold",
        action="store_true",
        help="hold a played-back run's clock until it is told to play, its days worked out ahead",
    )
    parser.add_argument(
        "--play-seconds-per-day",
        type=float,
        default=playback.DEFAULT_SECONDS_PER_DAY,
        help="how fast a played-back run's clock plays a simulated day",
    )
    args = parser.parse_args(argv)

    server = create_server(args.port, seconds_per_day=args.seconds_per_day)
    host, port = server.server_address[:2]
    print(f"greenhouse-sim API on http://{host!s}:{port}/api", flush=True)
    for scenario_id in args.play:
        played = playback.start(scenario_id, args.play_seconds_per_day, hold=args.hold)
        held = f" (held: POST /api/scenarios/{scenario_id}/playback/play)" if args.hold else ""
        print(
            f"playing {played.run_id}{held}, read at http://{host!s}:{port}/consumer/v1",
            flush=True,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
