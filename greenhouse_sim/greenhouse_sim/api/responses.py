"""An answer to a request, as an interface gives it: a status and a JSON
body. Shared by the viewer's routes (`routes`) and the consumer's
(`consumer`), which import nothing else of each other; and how the
gateway's routes (`actuation`) and a policy's port's (`policy`) answer a
service's record or its refusal, and read a whole-number parameter."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http import HTTPStatus

from pydantic import BaseModel

from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound, ServiceError

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None


@dataclass(frozen=True)
class Response:
    status: HTTPStatus
    body: JsonValue


def whole(query: dict[str, list[str]], name: str) -> int | None:
    """A parameter's last value, a whole number, if the query gives it."""
    values = query.get(name)
    if not values:
        return None
    try:
        return int(values[-1])
    except ValueError:
        raise InvalidRequest(f"{name} is a whole number, not {values[-1]!r}") from None


def answer(call: Callable[[], BaseModel | Sequence[BaseModel]]) -> Response:
    try:
        found = call()
    except NotFound as error:
        return detail(HTTPStatus.NOT_FOUND, error.message)
    except Conflict as error:
        return detail(HTTPStatus.CONFLICT, error.message)
    except InvalidRequest as error:
        return detail(HTTPStatus.BAD_REQUEST, error.message, error.problems)
    except ServiceError as error:
        return detail(HTTPStatus.BAD_REQUEST, error.message)
    if isinstance(found, BaseModel):
        return Response(HTTPStatus.OK, found.model_dump(mode="json"))
    return Response(HTTPStatus.OK, [each.model_dump(mode="json") for each in found])


def detail(status: HTTPStatus, message: str, problems: Sequence[tuple[str, str]] = ()) -> Response:
    body: dict[str, JsonValue] = {"detail": message}
    if problems:
        body["problems"] = [{"field": field, "message": said} for field, said in problems]
    return Response(status, body)
