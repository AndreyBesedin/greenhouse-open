"""A policy's port, served over HTTP (P15.5, decision 0061): a server of its
own, apart from the local API, for one run, serving a policy's port's
routes (`policy`) and nothing else.

    python -m greenhouse_sim.api.policy_server --scenario SCENARIO --credentials FILE \\
        [--authorisation FILE] [--host HOST] [--port PORT] [--seconds-per-day S] [--hold]
    python -m greenhouse_sim.api.policy_server --new-credential KIND:ID

It plays a scenario's own run back from its start, as the local API's
`--play` does, and serves its port; the local API is not started. Each
request carries a bearer token that the credentials file holds by its
SHA-256 (`services.credentials`), and is answered as from that policy.
Plans are checked against the authorisation file, as the local API's are
(decision 0052), or else the local operator's, which grants a policy
nothing.

It binds the loopback interface unless told another host. The local API
authenticates no one, and anything on the machine that reaches loopback
reaches it, so a benchmark serves the port alone. A policy that is not
trusted runs where loopback does not reach, such as a container given
only the port's address: that is the deployment's choice.

`--new-credential KIND:ID` makes a token for a principal and prints it,
once, with the credential to add to the credentials file.
"""

import argparse
import sys
import time
from collections.abc import Sequence
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Final, cast

from greenhouse_sim.api.policy import policy_respond
from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.server import LOOPBACK, PENDING_CONNECTIONS, JsonHandler
from greenhouse_sim.services import checkpoints, playback
from greenhouse_sim.services.credentials import credentials_file, new_credential_for
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.forecasts import PERSISTENCE_ID
from greenhouse_sim.services.gateway import LOCAL_AUTHORISATION, authorisation_file
from greenhouse_sim.services.policy_requests import ServedPorts, served_budget
from greenhouse_sim.services.simulator import Simulator

DEFAULT_PORT: Final = 8770


class PolicyPortServer(ThreadingHTTPServer):
    """A server of a policy's port on one run, for the policies its
    credentials name: see the module."""

    daemon_threads = True
    request_queue_size = PENDING_CONNECTIONS

    def __init__(self, ports: ServedPorts, *, host: str = LOOPBACK, port: int = 0) -> None:
        self.ports = ports
        super().__init__((host, port), _PortHandler)


class _PortHandler(JsonHandler):
    def do_GET(self) -> None:
        started = time.perf_counter()
        self._send(self._safely(lambda: self._answer("GET", b"")), started)

    def do_POST(self) -> None:
        started = time.perf_counter()
        body = self._body()
        if isinstance(body, Response):
            self._send(body, started)
            return
        self._send(self._safely(lambda: self._answer("POST", body)), started)

    def do_PUT(self) -> None:
        refused = Response(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"detail": f"a policy's port answers GET and POST, not {self.command}"},
        )
        self._send(refused, time.perf_counter())

    do_PATCH = do_DELETE = do_PUT

    def _answer(self, method: str, body: bytes) -> Response:
        ports = cast(PolicyPortServer, self.server).ports
        return policy_respond(ports, method, self.path, self.headers.get("Authorization"), body)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve a policy's port on a scenario's run.")
    parser.add_argument("--scenario", help="the scenario whose own run is played and served")
    parser.add_argument("--credentials", type=Path, help="the JSON file of the policies' tokens")
    parser.add_argument(
        "--authorisation",
        type=Path,
        default=None,
        help="a JSON file of who may do what on the run; by default the local operator's",
    )
    parser.add_argument("--host", default=LOOPBACK, help="the interface to bind: loopback")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--seconds-per-day",
        type=float,
        default=playback.DEFAULT_SECONDS_PER_DAY,
        help="how fast the run's clock plays a simulated day",
    )
    parser.add_argument("--hold", action="store_true", help="hold the run's clock at its start")
    parser.add_argument(
        "--forecasts",
        choices=(PERSISTENCE_ID,),
        default=None,
        help="give the policies this forecast provider's forecasts; by default none",
    )
    parser.add_argument(
        "--new-credential",
        metavar="KIND:ID",
        help="make a token for a principal, print it and its credential, and stop",
    )
    args = parser.parse_args(argv)
    try:
        if args.new_credential is not None:
            token, credential = new_credential_for(args.new_credential)
            print(f"token, for its holder alone: {token}")
            print(f"its credential, for the file: {credential.model_dump_json()}")
            return 0
        if args.scenario is None or args.credentials is None:
            parser.error("give --scenario and --credentials, or --new-credential")
        credentials = credentials_file(args.credentials)
        authorisation = (
            LOCAL_AUTHORISATION
            if args.authorisation is None
            else authorisation_file(args.authorisation)
        )
    except InvalidRequest as error:
        parser.error(error.message)
    simulator = Simulator(authorisation=authorisation)
    for refused in checkpoints.load_openings(simulator):
        print(f"not kept: {refused}", file=sys.stderr)
    state = playback.start(
        simulator,
        args.scenario,
        args.seconds_per_day,
        hold=args.hold,
        epochs=playback.default_epochs(),
    )
    played = playback.playback(simulator, args.scenario)
    try:
        budget = served_budget(played, args.forecasts)
    except InvalidRequest as error:
        parser.error(error.message)
    server = PolicyPortServer(
        ServedPorts(played, credentials, budget=budget), host=args.host, port=args.port
    )
    host, port = server.server_address[:2]
    print(
        f"a policy's port on {state.run_id}, epoch {state.epoch}, at http://{host!s}:{port}"
        f"/policy/v1",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        simulator.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
