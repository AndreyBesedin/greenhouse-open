"""A policy's port's routes (P15.5, decision 0061), under `/policy/v1`, for
the one run a port's server serves, each request from the policy whose
bearer token it carries (`Authorization: Bearer <token>`).

    GET  /policy/v1/run                                     -> RunDescriptor
    GET  /policy/v1/context                                 -> CapabilityContext
    GET  /policy/v1/budget                                  -> InformationBudget
    GET  /policy/v1/observations?after=&limit=              -> ObservationBatch
    GET  /policy/v1/events?after=&limit=                    -> EventBatch
    GET  /policy/v1/outcomes?after=&limit=                  -> OutcomeBatch
    GET  /policy/v1/forecasts?after=&limit=                 -> ForecastBatch
    GET  /policy/v1/plans/{plan_id}                         -> PlanState
    POST /policy/v1/plans                    a plan, or a revision -> Receipt
    POST /policy/v1/plans/{plan_id}/cancel?revision=&epoch=        -> Receipt
    POST /policy/v1/actions/cancel           chosen actions, by key -> Receipt

A request with no token, or one the server's credentials do not hold, is
`401`, and one whose credential is not a policy's `403`. A body or a
parameter that is not what the route takes is `400`, a plan that is not
the policy's `404`, as one that does not exist, a write to a run that has
finished `409`, a route asked with another method `405`, and any other
path `404`, each with a `detail` saying why. A receipt answers `200`,
whether or not the gateway accepted the write.

The port's server serves these routes alone, none of the local API's: it
reaches the simulator through `services.policy_requests` alone.
"""

from http import HTTPStatus
from typing import Final
from urllib.parse import parse_qs, urlsplit

from greenhouse_sim.api.responses import Response, answer, detail, whole
from greenhouse_sim.services import policy_requests
from greenhouse_sim.services.errors import Forbidden, Unauthenticated

_PREFIX: Final = [segment for segment in policy_requests.ROUTES_PREFIX.split("/") if segment]
# The logs a port reads after a cursor.
_LOGS: Final = {
    "observations": policy_requests.observations,
    "events": policy_requests.events,
    "outcomes": policy_requests.outcomes,
    "forecasts": policy_requests.forecasts,
}
_READS: Final = {
    "run": policy_requests.run,
    "context": policy_requests.context,
    "budget": policy_requests.budget,
}


def policy_respond(
    ports: policy_requests.ServedPorts,
    method: str,
    path: str,
    authorization: str | None,
    body: bytes = b"",
) -> Response:
    """A policy's port's answer to a request: see the module."""
    url = urlsplit(path)
    segments = [segment for segment in url.path.split("/") if segment]
    if segments[: len(_PREFIX)] != _PREFIX:
        return detail(
            HTTPStatus.NOT_FOUND, f"no route {url.path!r}: a policy's port serves its own"
        )
    try:
        port = ports.port(authorization)
    except Unauthenticated as error:
        return detail(HTTPStatus.UNAUTHORIZED, error.message)
    except Forbidden as error:
        return detail(HTTPStatus.FORBIDDEN, error.message)
    query = parse_qs(url.query, keep_blank_values=True)
    match method, segments[len(_PREFIX) :]:
        case "GET", [read] if read in _READS:
            return answer(lambda: _READS[read](port))
        case "GET", [log] if log in _LOGS:
            return answer(lambda: _LOGS[log](port, whole(query, "after"), whole(query, "limit")))
        case "GET", ["plans", plan_id]:
            return answer(lambda: policy_requests.plan(port, plan_id))
        case "POST", ["plans"]:
            return answer(lambda: policy_requests.give(port, body))
        case "POST", ["plans", plan_id, "cancel"]:
            return answer(
                lambda: policy_requests.cancel_plan(
                    port, plan_id, revision=whole(query, "revision"), epoch=whole(query, "epoch")
                )
            )
        case "POST", ["actions", "cancel"]:
            return answer(lambda: policy_requests.cancel(port, body))
        case _, [read] if read in _READS or read in _LOGS:
            return detail(HTTPStatus.METHOD_NOT_ALLOWED, f"{url.path} answers GET, not {method}")
        case _, ["plans"] | ["plans", _, "cancel"] | ["actions", "cancel"]:
            return detail(HTTPStatus.METHOD_NOT_ALLOWED, f"{url.path} answers POST, not {method}")
        case _, ["plans", _]:
            return detail(HTTPStatus.METHOD_NOT_ALLOWED, f"{url.path} answers GET, not {method}")
        case _:
            return detail(HTTPStatus.NOT_FOUND, f"no route {url.path!r} of a policy's port")
