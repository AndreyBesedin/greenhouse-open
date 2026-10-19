"""An answer to a request, as an interface gives it: a status and a JSON
body. Shared by the viewer's routes (`routes`) and the consumer's
(`consumer`), which import nothing else of each other."""

from dataclasses import dataclass
from http import HTTPStatus

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None


@dataclass(frozen=True)
class Response:
    status: HTTPStatus
    body: JsonValue
