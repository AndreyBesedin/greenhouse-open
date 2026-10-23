"""What every area's routes share: a request's path, query and body read
into the values a service takes, and a service's result, or its refusal,
answered."""

import json
import math
from collections.abc import Callable, Sequence
from http import HTTPStatus
from typing import Final
from urllib.parse import urlsplit

from pydantic import BaseModel

from greenhouse_sim.api.responses import JsonValue, Response
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, ServiceError

type Query = dict[str, list[str]]

# How each kind of service error is answered; the first that matches.
REFUSALS: Final = (
    (NotFound, HTTPStatus.NOT_FOUND),
    (InvalidRequest, HTTPStatus.BAD_REQUEST),
    (Conflict, HTTPStatus.CONFLICT),
)


def answer(
    call: Callable[[], BaseModel | Sequence[BaseModel] | dict[str, JsonValue]],
) -> Response:
    """The service's result as a response, or its error as a refusal."""
    try:
        result = call()
    except ServiceError as refused:
        return refusal(refused)
    body: JsonValue
    if isinstance(result, BaseModel):
        body = result.model_dump(mode="json")
    elif isinstance(result, dict):
        body = result
    else:
        body = [item.model_dump(mode="json") for item in result]
    return Response(HTTPStatus.OK, body)


def refusal(refused: ServiceError) -> Response:
    """A service's error as the status that says what went wrong, and, for
    a request refused for its fields, each of them."""
    status = next(status for kind, status in REFUSALS if isinstance(refused, kind))
    if isinstance(refused, InvalidRequest) and refused.problems:
        problems: list[JsonValue] = [
            {"field": field, "message": message} for field, message in refused.problems
        ]
        return Response(status, {"error": refused.message, "problems": problems})
    return error(status, refused.message)


def error(status: HTTPStatus, message: str) -> Response:
    return Response(status, {"error": message})


def segments_of(path: str) -> list[str]:
    """A path's segments, without its query."""
    return [segment for segment in urlsplit(path).path.split("/") if segment]


def json_body(body: bytes) -> JsonValue:
    """A request's body, read as JSON: standard JSON, whose numbers are all
    finite, not Python's, which reads `NaN` and `Infinity` too."""
    try:
        parsed: JsonValue = json.loads(body, parse_constant=_not_a_number, parse_float=_finite)
    except ValueError:
        raise InvalidRequest("the body is not JSON") from None
    except RecursionError:
        raise InvalidRequest("the body is JSON nested too deeply to read") from None
    return parsed


def _finite(written: str) -> float:
    """A number as JSON writes it, refused if Python reads it as infinite,
    as it reads `1e999`."""
    number = float(written)
    if not math.isfinite(number):
        raise InvalidRequest(f"the body holds {written}, too large a number")
    return number


def _not_a_number(name: str) -> JsonValue:
    raise InvalidRequest(f"the body holds {name}, which JSON has no number for")


def text_body(body: bytes) -> str:
    """A request's body, as the UTF-8 text it is sent in."""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidRequest("the body is not UTF-8 text") from None


def last(query: Query, name: str) -> str | None:
    """A parameter's last value in a query, if it has one."""
    values = query.get(name)
    return values[-1] if values else None


def seconds(query: Query, name: str = "t") -> float:
    """The moment a query asks for, `t`, in seconds: the start if none."""
    text = last(query, name)
    if text is None:
        return 0.0
    try:
        return float(text)
    except ValueError:
        raise InvalidRequest(f"{name} wants seconds, not {text!r}") from None


def since(query: Query) -> float | None:
    """Where a series a query asks for begins, `from`, in seconds; None if
    it does not say, for the service's own default."""
    return None if last(query, "from") is None else seconds(query, "from")


def whole(query: Query, name: str, default: int) -> int:
    """A parameter as a whole number, or `default` if the query has none."""
    value = last(query, name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise InvalidRequest(f"{name} wants a whole number, not {value!r}") from None


def pairs(requests: list[str], name: str) -> dict[str, float]:
    """`name=key:number,key:number` as numbers by key."""
    found: dict[str, float] = {}
    for request in ",".join(requests).split(","):
        if not request:
            continue
        key, _, number = request.partition(":")
        try:
            found[key] = float(number)
        except ValueError:
            raise InvalidRequest(f"{name} wants key:number pairs, not {request!r}") from None
    return found
