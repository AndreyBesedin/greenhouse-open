"""What a policy's port answers over the network (P15.5, decision 0061):
the protocol's contract (`greenhouse_protocol.contracts.policy`) served
for one run, each request from the policy its bearer token names.

A server serves the ports of one run (`ServedPorts`). Each policy its
credentials name has one port, opened at its first request and kept, so
that the cursors it gives hold from one request to the next
(`policy_port`). A request without a token, or with one no credential
holds, is refused as from no one the server knows; one from a credential
that is not a policy's, an operator's or an evaluator's, is refused as
not a policy's.

The rest is the port's: a plan given, cancelled or read as its principal,
and the run read as its principal reads it. A body or a parameter that is
not what a request takes is refused before it reaches the port, saying
why.
"""

import threading
from typing import Final

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
from greenhouse_protocol.plan import ActionKey, Plan, Principal
from pydantic import TypeAdapter

from greenhouse_sim.services.consumer import batch_cursor, batch_limit
from greenhouse_sim.services.credentials import Credentials, Role
from greenhouse_sim.services.errors import (
    Forbidden,
    InvalidRequest,
    NotFound,
    Unauthenticated,
    read_as,
)
from greenhouse_sim.services.policy_port import PlayedRun, RunPolicyPort

# Where a policy's port's routes live: `/policy/v1`.
ROUTES_PREFIX: Final = POLICY_PREFIX
# How a request names its token.
BEARER: Final = "Bearer "

_KEYS: Final = TypeAdapter(tuple[ActionKey, ...])


class ServedPorts:
    """The ports a server serves on one run: see the module."""

    def __init__(self, played: PlayedRun, credentials: Credentials) -> None:
        self._played = played
        self._credentials = credentials
        self._lock = threading.Lock()
        self._ports: dict[Principal, RunPolicyPort] = {}

    def port(self, authorization: str | None) -> RunPolicyPort:
        """The port of the policy whose token a request's `Authorization`
        header carries: refused for no token, one no credential holds, or
        one whose credential is not a policy's."""
        if authorization is None or not authorization.startswith(BEARER):
            raise Unauthenticated("a request carries its bearer token: Authorization: Bearer …")
        credential = self._credentials.holder(authorization.removeprefix(BEARER).strip())
        if credential is None:
            raise Unauthenticated("no credential holds that token")
        if credential.role != Role.POLICY:
            raise Forbidden(f"a policy's port serves policies, not the {credential.role}")
        with self._lock:
            found = self._ports.get(credential.principal)
            if found is None:
                found = self._ports[credential.principal] = RunPolicyPort(
                    self._played, credential.principal
                )
            return found


def run(port: RunPolicyPort) -> RunDescriptor:
    return port.run()


def context(port: RunPolicyPort) -> CapabilityContext:
    return port.context()


def budget(port: RunPolicyPort) -> InformationBudget:
    return port.budget()


def observations(port: RunPolicyPort, after: int | None, limit: int | None) -> ObservationBatch:
    return port.observations(batch_cursor(after), batch_limit(limit))


def events(port: RunPolicyPort, after: int | None, limit: int | None) -> EventBatch:
    return port.events(batch_cursor(after), batch_limit(limit))


def outcomes(port: RunPolicyPort, after: int | None, limit: int | None) -> OutcomeBatch:
    return port.outcomes(batch_cursor(after), batch_limit(limit))


def forecasts(port: RunPolicyPort, after: int | None, limit: int | None) -> ForecastBatch:
    return port.forecasts(batch_cursor(after), batch_limit(limit))


def plan(port: RunPolicyPort, plan_id: str) -> PlanState:
    """A plan of its principal's, in force; one of another's is not found,
    as one that does not exist."""
    found = port.plan(plan_id)
    if found is None:
        raise NotFound(f"no plan {plan_id!r} of {port.principal.id}'s")
    return found


def give(port: RunPolicyPort, body: bytes) -> Receipt:
    """A plan, or its next revision, as the body writes it (`Plan`)."""
    return port.submit(read_as("a plan", lambda: Plan.model_validate_json(body)))


def cancel_plan(
    port: RunPolicyPort, plan_id: str, *, revision: int | None, epoch: int | None
) -> Receipt:
    """A whole plan cancelled, as its `revision` in `epoch` stood."""
    if revision is None or epoch is None:
        raise InvalidRequest("a plan is cancelled as its revision and epoch stood: give both")
    if revision < 1 or epoch < 0:
        raise InvalidRequest("a revision is 1 or more, and an epoch 0 or more")
    return port.cancel_plan(plan_id, revision=revision, epoch=epoch)


def cancel(port: RunPolicyPort, body: bytes) -> Receipt:
    """Chosen actions cancelled, by the keys the body lists (`ActionKey`, in
    a JSON array)."""
    return port.cancel(read_as("a list of action keys", lambda: _KEYS.validate_json(body)))
