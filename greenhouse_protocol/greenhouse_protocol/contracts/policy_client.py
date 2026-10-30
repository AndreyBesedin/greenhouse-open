"""A policy's port over HTTP, as a policy in a process of its own reaches it
(decision 0061): the contract's calls (`contracts.policy.PolicyPort`),
each a request to the port's routes with the policy's bearer token, made
with the standard library alone, so that a policy outside depends on the
protocol only.

    port = HttpPolicyPort("http://127.0.0.1:8770", token)
    context = port.context()
    receipt = port.submit(plan)

A plan the policy does not own is none, as the contract has it. Any other
request the server refuses raises `PortRefused`, with its status and the
server's reason; a receipt that says a write was refused is not a refusal
of the request.
"""

import json
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Final
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel

from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
    RunDescriptor,
)
from greenhouse_protocol.contracts.gateway import PlanState, Receipt
from greenhouse_protocol.contracts.policy import POLICY_PREFIX
from greenhouse_protocol.plan import ActionKey, Plan

# How long a request waits for its answer, in seconds.
DEFAULT_TIMEOUT_S: Final = 30.0


class PortRefused(Exception):
    """A request the port's server refused: its status and why."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class HttpPolicyPort:
    """A policy's port at `url`, the server's root, reached with `token`:
    see the module."""

    def __init__(self, url: str, token: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._root = url.rstrip("/") + POLICY_PREFIX
        self._token = token
        self._timeout_s = timeout_s

    def run(self) -> RunDescriptor:
        return RunDescriptor.model_validate_json(self._request("GET", "run"))

    def context(self) -> CapabilityContext:
        return CapabilityContext.model_validate_json(self._request("GET", "context"))

    def budget(self) -> InformationBudget:
        return InformationBudget.model_validate_json(self._request("GET", "budget"))

    def observations(self, after: int = 0, limit: int | None = None) -> ObservationBatch:
        return ObservationBatch.model_validate_json(self._log("observations", after, limit))

    def events(self, after: int = 0, limit: int | None = None) -> EventBatch:
        return EventBatch.model_validate_json(self._log("events", after, limit))

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch:
        return OutcomeBatch.model_validate_json(self._log("outcomes", after, limit))

    def forecasts(self, after: int = 0, limit: int | None = None) -> ForecastBatch:
        return ForecastBatch.model_validate_json(self._log("forecasts", after, limit))

    def plan(self, plan_id: str) -> PlanState | None:
        try:
            return PlanState.model_validate_json(
                self._request("GET", f"plans/{quote(plan_id, safe='')}")
            )
        except PortRefused as refused:
            if refused.status == HTTPStatus.NOT_FOUND:
                return None
            raise

    def submit(self, plan: Plan) -> Receipt:
        return Receipt.model_validate_json(self._request("POST", "plans", _body(plan)))

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int) -> Receipt:
        return Receipt.model_validate_json(
            self._request(
                "POST",
                f"plans/{quote(plan_id, safe='')}/cancel",
                b"",
                {"revision": revision, "epoch": epoch},
            )
        )

    def cancel(self, keys: Sequence[ActionKey]) -> Receipt:
        body = json.dumps([key.model_dump(mode="json") for key in keys]).encode()
        return Receipt.model_validate_json(self._request("POST", "actions/cancel", body))

    def _log(self, name: str, after: int, limit: int | None) -> bytes:
        query: dict[str, int] = {"after": after}
        if limit is not None:
            query["limit"] = limit
        return self._request("GET", name, None, query)

    def _request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        query: Mapping[str, int] | None = None,
    ) -> bytes:
        url = f"{self._root}/{path}"
        if query:
            url += f"?{urlencode(query)}"
        request = Request(
            url,
            data=body,
            method=method,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self._timeout_s) as answer:
                read: bytes = answer.read()
                return read
        except HTTPError as refused:
            raise PortRefused(refused.code, _detail(refused.read())) from None


def _body(record: BaseModel) -> bytes:
    return record.model_dump_json().encode()


def _detail(body: bytes) -> str:
    """The server's reason, as its answer's `detail` says it, or its body."""
    try:
        said = json.loads(body)
    except ValueError:
        return body.decode(errors="replace")
    if isinstance(said, dict) and isinstance(said.get("detail"), str):
        return str(said["detail"])
    return body.decode(errors="replace")
