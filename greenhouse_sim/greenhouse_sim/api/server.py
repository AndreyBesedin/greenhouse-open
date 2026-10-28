"""Serving the local API over HTTP, on this machine only.

    python -m greenhouse_sim.api [--port PORT] [--play SCENARIO]

The browser viewer's development server forwards `/api` here, so the API
needs no cross-origin headers. It binds to the loopback interface: it is a
tool for a developer's own machine, not a service.

The consumer interface's routes (`/consumer/v1`, `consumer`) answer before
the viewer's, `GET` only, and then the gateway's (`/actuation/v1`,
`actuation`), which give, steer and read a played-back run's plans as the
local operator (P13.7). `--play SCENARIO` plays a scenario's own run back
from its start (`services.playback`), for the viewer and a consumer.

A run's checkpoints are saved or uploaded as POST requests, with a JSON
body.
A request the simulator fails on unexpectedly is answered 500, with the
failure in the server's log. Every answer says how long the simulator took
to give it, as a `Server-Timing` header's `sim` metric, in milliseconds
(P09.8), which the viewer's HUD shows for the latest request.
"""

import argparse
import faulthandler
import json
import logging
import signal
import sys
import time
import traceback
from collections.abc import Callable, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final, cast

from greenhouse_sim.api.actuation import actuation_respond, is_actuation
from greenhouse_sim.api.consumer import consumer_respond
from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes import respond
from greenhouse_sim.services import checkpoints, playback
from greenhouse_sim.services.drafts import DraftStore, store_at
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.gateway import (
    LOCAL_AUTHORISATION,
    AuthorisationConfig,
    authorisation_file,
)
from greenhouse_sim.services.simulator import Simulator

LOOPBACK: Final = "127.0.0.1"
# What a client is told when the simulator fails on its request unexpectedly.
UNEXPECTED_FAILURE: Final = "the simulator failed to answer; its log says why"
DEFAULT_PORT: Final = 8765
# Where, under the user's home, the installations' drafts are kept unless
# the command line says otherwise (decision 0051): beside no repository.
DEFAULT_DRAFTS: Final = Path(".greenhouse-sim") / "drafts.sqlite3"
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
# The simulator's own log, beside each request's line on stderr: when, from
# which module, and what it says.
LOG_FORMAT: Final = "%(asctime)s %(name)s: %(message)s"


class SimulatorServer(ThreadingHTTPServer):
    """The API's server, answering from its simulator (decision 0048): one it
    makes, and closes as it closes, or one it is given, which its giver
    closes."""

    daemon_threads = True
    request_queue_size = PENDING_CONNECTIONS

    def __init__(
        self,
        port: int,
        simulator: Simulator | None = None,
        *,
        drafts: DraftStore | None = None,
        authorisation: AuthorisationConfig = LOCAL_AUTHORISATION,
    ) -> None:
        # Before binding: a server that fails to bind closes itself, which
        # closes a simulator it made, and then raises the bind's own error.
        # Nothing has started yet.
        self._makes_simulator = simulator is None
        self.simulator = (
            Simulator(drafts=drafts, authorisation=authorisation)
            if simulator is None
            else simulator
        )
        super().__init__((LOOPBACK, port), _Handler)
        # The scenarios' kept opening days, so that their runs' later days
        # need not be worked out from their starts.
        for refused in checkpoints.load_openings(self.simulator):
            print(f"not kept: {refused}", file=sys.stderr)

    def server_close(self) -> None:
        # It accepts no request once its socket is closed; then the simulator
        # goes with the server that made it, its playbacks stopped.
        super().server_close()
        if self._makes_simulator:
            self.simulator.close()


class _Handler(BaseHTTPRequestHandler):
    timeout = READ_TIMEOUT_S

    def do_GET(self) -> None:
        started = time.perf_counter()
        consumers = self._safely(lambda: consumer_respond(self._simulator, "GET", self.path))
        if consumers is not None:
            self._send(consumers, started)
            return
        acts = self._safely(lambda: actuation_respond(self._simulator, "GET", self.path))
        if acts is not None:
            self._send(acts, started)
            return
        self._send(self._safely(lambda: respond(self._simulator, "GET", self.path)), started)

    def do_POST(self) -> None:
        started = time.perf_counter()
        consumers = self._safely(lambda: consumer_respond(self._simulator, "POST", self.path))
        if consumers is not None:
            self._send(consumers, started)
            return
        if is_actuation(self.path):
            given = self._body()
            if isinstance(given, Response):
                self._send(given, started)
                return
            answered = self._safely(
                lambda: actuation_respond(self._simulator, "POST", self.path, given)
            )
            self._send(answered or Response(HTTPStatus.NOT_FOUND, {"detail": "no route"}), started)
            return
        body = self._body()
        if isinstance(body, Response):
            self._send(body, started)
            return
        self._send(self._safely(lambda: respond(self._simulator, "POST", self.path, body)), started)

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
    def _simulator(self) -> Simulator:
        return cast(SimulatorServer, self.server).simulator

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


def _refused_method(method: str) -> Response:
    return Response(
        HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"the API answers GET and POST, not {method}"}
    )


def create_server(
    port: int = DEFAULT_PORT,
    *,
    simulator: Simulator | None = None,
    drafts: DraftStore | None = None,
    authorisation: AuthorisationConfig = LOCAL_AUTHORISATION,
) -> SimulatorServer:
    """A server on the loopback interface; port 0 picks a free port. It makes
    its own simulator, keeping drafts in `drafts` if given, its runs acted on
    as `authorisation` lets (decision 0052), unless it is given a simulator."""
    return SimulatorServer(port, simulator, drafts=drafts, authorisation=authorisation)


def _authorisation(given: Path | None, parser: argparse.ArgumentParser) -> AuthorisationConfig:
    """The authorisation the command line names, the API refusing to start
    without it; or else the local operator's (decision 0052)."""
    if given is None:
        return LOCAL_AUTHORISATION
    try:
        return authorisation_file(given)
    except InvalidRequest as error:
        parser.error(error.message)


def _drafts(given: Path | None, parser: argparse.ArgumentParser) -> DraftStore | None:
    """The store of drafts the command line names, the API refusing to start
    without it; or else the default one, without which it starts all the
    same, keeping no drafts, as where its user has no home it may write to."""
    if given is not None:
        try:
            return store_at(given)
        except InvalidRequest as error:
            parser.error(error.message)
    try:
        return store_at(Path.home() / DEFAULT_DRAFTS)
    except (InvalidRequest, RuntimeError) as error:
        reason = error.message if isinstance(error, InvalidRequest) else str(error)
        print(f"keeping no drafts: {reason}", file=sys.stderr)
        return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the simulator's local API.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
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
    parser.add_argument(
        "--drafts",
        type=Path,
        default=None,
        help=(
            "the SQLite file the installations' drafts are kept in, made if missing; "
            f"by default ~/{DEFAULT_DRAFTS}"
        ),
    )
    parser.add_argument(
        "--authorisation",
        type=Path,
        default=None,
        help=(
            "a JSON file of who may do what on the simulator's runs, as the protocol "
            "writes an authorisation; by default the local operator, everything"
        ),
    )
    args = parser.parse_args(argv)
    drafts = _drafts(args.drafts, parser)
    authorisation = _authorisation(args.authorisation, parser)
    # What the simulator's services make, keep, take over and let go, at
    # INFO (AUDIT.14); other libraries' warnings only.
    logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT, stream=sys.stderr)
    logging.getLogger("greenhouse_sim").setLevel(logging.INFO)
    # `kill -USR1 <pid>` prints every thread's stack to stderr and leaves
    # the server running, to see where a busy or stuck one is.
    faulthandler.register(signal.SIGUSR1, all_threads=True)

    server = create_server(args.port, drafts=drafts, authorisation=authorisation)
    host, port = server.server_address[:2]
    print(f"greenhouse-sim API on http://{host!s}:{port}/api", flush=True)
    for scenario_id in args.play:
        played = playback.start(
            server.simulator,
            scenario_id,
            args.play_seconds_per_day,
            hold=args.hold,
            epochs=playback.default_epochs(),
        )
        held = f" (held: POST /api/scenarios/{scenario_id}/playback/play)" if args.hold else ""
        print(
            f"playing {played.run_id}, epoch {played.epoch}{held}, "
            f"read at http://{host!s}:{port}/consumer/v1",
            flush=True,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
