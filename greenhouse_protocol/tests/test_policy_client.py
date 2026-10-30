"""A policy's port over HTTP, as the protocol's client reaches it (decision
0061): its token on every request, each call its route, a plan not its own
as none, and a refusal as `PortRefused` with the server's reason. Against a
stand-in server; the simulator's tests hold the client to a port's server
by the conformance check."""

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

import pytest

from greenhouse_protocol.actions import ActionRef
from greenhouse_protocol.budget import OBSERVATIONS_ONLY
from greenhouse_protocol.contracts.consumer import ObservationBatch
from greenhouse_protocol.contracts.gateway import Receipt
from greenhouse_protocol.contracts.policy_client import HttpPolicyPort, PortRefused
from greenhouse_protocol.plan import ActionKey, Plan

TOKEN: Final = "a-token"
NOW: Final = datetime(2026, 3, 1, 6, tzinfo=UTC)
RECEIPT: Final = Receipt(accepted=True, plan_id="steer", revision=2, sequence=3)
BATCH: Final = ObservationBatch(
    run_id="run", epoch=0, after=3, next=3, simulated_now=NOW, observations=()
)
# What the stand-in answers each request, by its method and path.
ANSWERS: Final[dict[tuple[str, str], tuple[int, object]]] = {
    ("GET", "/policy/v1/budget"): (HTTPStatus.OK, OBSERVATIONS_ONLY.model_dump(mode="json")),
    ("GET", "/policy/v1/context"): (
        HTTPStatus.UNAUTHORIZED,
        {"detail": "no credential holds that token"},
    ),
    ("GET", "/policy/v1/observations?after=3&limit=2"): (
        HTTPStatus.OK,
        BATCH.model_dump(mode="json"),
    ),
    ("GET", "/policy/v1/plans/mine"): (HTTPStatus.NOT_FOUND, {"detail": "no plan 'mine'"}),
    ("GET", "/policy/v1/plans/broken"): (HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "failed"}),
    ("POST", "/policy/v1/plans"): (HTTPStatus.OK, RECEIPT.model_dump(mode="json")),
    ("POST", "/policy/v1/plans/steer/cancel?revision=2&epoch=0"): (
        HTTPStatus.OK,
        RECEIPT.model_dump(mode="json"),
    ),
    ("POST", "/policy/v1/actions/cancel"): (HTTPStatus.OK, RECEIPT.model_dump(mode="json")),
}


class _StandIn(BaseHTTPRequestHandler):
    """Answers as `ANSWERS` says, and keeps what it was asked."""

    asked: list[tuple[str, str, str | None, bytes]] = []  # noqa: RUF012 - the test's record

    def do_GET(self) -> None:
        self._answer()

    def do_POST(self) -> None:
        self._answer()

    def _answer(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.asked.append((self.command, self.path, self.headers.get("Authorization"), body))
        status, answer = ANSWERS.get((self.command, self.path), (HTTPStatus.NOT_FOUND, {}))
        sent = json.dumps(answer).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(sent)))
        self.end_headers()
        self.wfile.write(sent)

    def log_message(self, format: str, *args: object) -> None:
        """Nothing logged: the test reads what it was asked."""


@pytest.fixture
def port() -> Iterator[HttpPolicyPort]:
    _StandIn.asked = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StandIn)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, number = server.server_address[:2]
    try:
        yield HttpPolicyPort(f"http://{host!s}:{number}/", TOKEN)
    finally:
        server.shutdown()
        server.server_close()


def test_each_call_is_its_route_with_the_policys_token(port: HttpPolicyPort) -> None:
    plan = Plan(plan_id="steer", run_id="run", epoch=0, revision=2, actions=())
    key = ActionKey(plan_id="steer", epoch=0, revision=2, ref=ActionRef(action_id="open"))

    assert port.budget() == OBSERVATIONS_ONLY
    assert port.observations(3, 2) == BATCH
    assert port.submit(plan) == RECEIPT
    assert port.cancel_plan("steer", revision=2, epoch=0) == RECEIPT
    assert port.cancel([key]) == RECEIPT

    assert {authorization for _, _, authorization, _ in _StandIn.asked} == {f"Bearer {TOKEN}"}
    bodies = {path: body for _, path, _, body in _StandIn.asked}
    assert Plan.model_validate_json(bodies["/policy/v1/plans"]) == plan
    assert json.loads(bodies["/policy/v1/actions/cancel"]) == [key.model_dump(mode="json")]


def test_a_plan_not_its_own_is_none_and_a_refusal_says_why(port: HttpPolicyPort) -> None:
    assert port.plan("mine") is None
    with pytest.raises(PortRefused) as refused:
        port.context()
    assert (refused.value.status, refused.value.detail) == (
        HTTPStatus.UNAUTHORIZED,
        "no credential holds that token",
    )
    with pytest.raises(PortRefused) as failed:
        port.plan("broken")
    assert failed.value.status == HTTPStatus.INTERNAL_SERVER_ERROR
