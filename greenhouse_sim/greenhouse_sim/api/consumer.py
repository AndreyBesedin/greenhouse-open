"""The consumer interface's routes (P10.4, decision 0040): `GET` only, under
`/consumer/v1`, answered from the runs played back against a clock.

    GET /consumer/v1/runs                              -> RunList
    GET /consumer/v1/runs/{run_id}                     -> RunDescriptor
    GET /consumer/v1/runs/{run_id}/greenhouse          -> GreenhouseDescription
    GET /consumer/v1/runs/{run_id}/observations?after= -> ObservationBatch
    GET /consumer/v1/runs/{run_id}/events?after=       -> EventBatch

`limit=` caps a batch, which the simulator caps lower too. An unknown run
or path is `404`, a cursor or limit that is not a whole number `400`, and
any other method `405`, each with a `detail` saying why.

A surface of its own, apart from the viewer's API: it reaches the simulator
through `services.consumer` alone, and so reaches observed records only,
never a run's truth, its scene or QA mode's data. The server binds it, as
the viewer's API, to this machine's loopback interface.
"""

from collections.abc import Callable
from http import HTTPStatus
from typing import Final
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel

from greenhouse_sim.api.responses import Response
from greenhouse_sim.services import consumer
from greenhouse_sim.services.errors import InvalidRequest, NotFound, ServiceError

_PREFIX: Final = [segment for segment in consumer.ROUTES_PREFIX.split("/") if segment]


def consumer_respond(reads: consumer.Reads, method: str, path: str) -> Response | None:
    """The consumer interface's answer to a request, if `path` is one of
    its routes; None for any other path."""
    url = urlsplit(path)
    segments = [segment for segment in url.path.split("/") if segment]
    if segments[: len(_PREFIX)] != _PREFIX:
        return None
    if method != "GET":
        return _detail(
            HTTPStatus.METHOD_NOT_ALLOWED, f"the consumer interface answers GET, not {method}"
        )
    # Blank values kept, so that `after=` is refused rather than read as 0.
    query = parse_qs(url.query, keep_blank_values=True)
    match segments[len(_PREFIX) :]:
        case ["runs"]:
            return _answer(lambda: consumer.runs(reads))
        case ["runs", run_id]:
            return _answer(lambda: consumer.run(reads, run_id))
        case ["runs", run_id, "greenhouse"]:
            return _answer(lambda: consumer.greenhouse(reads, run_id))
        case ["runs", run_id, "observations"]:
            return _answer(
                lambda: consumer.observations(
                    reads, run_id, _whole(query, "after"), _whole(query, "limit")
                )
            )
        case ["runs", run_id, "events"]:
            return _answer(
                lambda: consumer.events(
                    reads, run_id, _whole(query, "after"), _whole(query, "limit")
                )
            )
        case _:
            return _detail(HTTPStatus.NOT_FOUND, f"no consumer route {url.path!r}")


def _whole(query: dict[str, list[str]], name: str) -> int | None:
    """A parameter's last value, a whole number, if the query gives it."""
    values = query.get(name)
    if not values:
        return None
    try:
        return int(values[-1])
    except ValueError:
        raise InvalidRequest(f"{name} is a whole number, not {values[-1]!r}") from None


def _answer(call: Callable[[], BaseModel]) -> Response:
    try:
        return Response(HTTPStatus.OK, call().model_dump(mode="json"))
    except NotFound as error:
        return _detail(HTTPStatus.NOT_FOUND, error.message)
    except ServiceError as error:
        return _detail(HTTPStatus.BAD_REQUEST, error.message)


def _detail(status: HTTPStatus, message: str) -> Response:
    return Response(status, {"detail": message})
