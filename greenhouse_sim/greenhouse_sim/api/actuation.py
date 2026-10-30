"""The gateway's routes (P13.7, decision 0046): a run's plans given, steered,
cancelled and read, under `/actuation/v1`, for the runs played back against
a clock.

    POST /actuation/v1/runs/{run_id}/plans                  a Plan        -> Receipt
    POST /actuation/v1/runs/{run_id}/plans/{plan_id}/cancel?revision=&epoch=
                                                            a whole plan  -> Receipt
    GET  /actuation/v1/runs/{run_id}/plans/{plan_id}?revision=           -> PlanState
    GET  /actuation/v1/runs/{run_id}/actions?state=&kind=&target=&plan=
                                                     the actions as they stand
    POST /actuation/v1/runs/{run_id}/actions/cancel    a JSON array of ActionKey
                                                                          -> Receipt

Each filter of the actions repeats, or lists its values comma separated.
Every write is the local operator's (decision 0052). A receipt answers
`200`, whether or not the gateway accepted the write, and says which and
why. A body or a parameter that is not what the route takes is `400`, an
unknown run, plan or revision `404`, a write to a run that has finished
`409`, a route asked with another method `405`, and any other path `404`,
each with a `detail` saying why.

A surface of its own beside the consumer interface, which reads a run's
outcomes: it reaches the simulator through `services.actuation` alone. The
server binds it, as the viewer's API, to this machine's loopback interface.
"""

from http import HTTPStatus
from typing import Final
from urllib.parse import parse_qs, urlsplit

from greenhouse_sim.api.responses import Response, answer, detail, whole
from greenhouse_sim.services import actuation

_PREFIX: Final = [segment for segment in actuation.ROUTES_PREFIX.split("/") if segment]


def is_actuation(path: str) -> bool:
    """Whether a path is one of the gateway's: under `/actuation/v1`."""
    segments = [segment for segment in urlsplit(path).path.split("/") if segment]
    return segments[: len(_PREFIX)] == _PREFIX


def actuation_respond(
    acts: actuation.Acts, method: str, path: str, body: bytes = b""
) -> Response | None:
    """The gateway's answer to a request, if `path` is one of its routes;
    None for any other path."""
    if not is_actuation(path):
        return None
    url = urlsplit(path)
    segments = [segment for segment in url.path.split("/") if segment][len(_PREFIX) :]
    # Blank values kept, so that `revision=` is refused rather than unset.
    query = parse_qs(url.query, keep_blank_values=True)
    match method, segments:
        case "POST", ["runs", run_id, "plans"]:
            return answer(lambda: actuation.give(acts, run_id, body))
        case "POST", ["runs", run_id, "plans", plan_id, "cancel"]:
            return answer(
                lambda: actuation.cancel_plan(
                    acts,
                    run_id,
                    plan_id,
                    revision=whole(query, "revision"),
                    epoch=whole(query, "epoch"),
                )
            )
        case "GET", ["runs", run_id, "plans", plan_id]:
            return answer(lambda: actuation.plan(acts, run_id, plan_id, whole(query, "revision")))
        case "GET", ["runs", run_id, "actions"]:
            return answer(
                lambda: actuation.actions(
                    acts,
                    run_id,
                    states=_listed(query, "state"),
                    kinds=_listed(query, "kind"),
                    targets=_listed(query, "target"),
                    plan_id=_last(query, "plan"),
                )
            )
        case "POST", ["runs", run_id, "actions", "cancel"]:
            return answer(lambda: actuation.cancel(acts, run_id, body))
        case _, (
            ["runs", _, "plans"]
            | ["runs", _, "plans", _, "cancel"]
            | ["runs", _, "plans", _]
            | ["runs", _, "actions"]
            | ["runs", _, "actions", "cancel"]
        ):
            return detail(
                HTTPStatus.METHOD_NOT_ALLOWED, f"{url.path} answers another method than {method}"
            )
        case _:
            return detail(HTTPStatus.NOT_FOUND, f"no actuation route {url.path!r}")


def _last(query: dict[str, list[str]], name: str) -> str | None:
    """A parameter's last value, if the query gives it."""
    values = query.get(name)
    return values[-1] if values else None


def _listed(query: dict[str, list[str]], name: str) -> list[str]:
    """A filter's values: each it repeats, each comma separated."""
    return [value for given in query.get(name, []) for value in given.split(",") if value]
