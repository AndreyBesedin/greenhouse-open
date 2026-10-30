"""What can go wrong in a service, in the client's terms.

Each error carries a message for the client, saying what went wrong and,
where it helps, what would be accepted instead. An interface turns each kind
into its own answer, such as an HTTP status; a service never chooses one.
"""

from collections.abc import Callable, Sequence

from pydantic import ValidationError


class ServiceError(Exception):
    """A request a service could not carry out, and why."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    """Something the request names does not exist."""


class InvalidRequest(ServiceError):
    """The request cannot be met as it stands. Refused for its fields, it
    names each in `problems`: the field's path, as the request writes it,
    and what is wrong with it, for a client to show by its control."""

    def __init__(self, message: str, problems: Sequence[tuple[str, str]] = ()) -> None:
        super().__init__(message)
        self.problems = tuple(problems)


class Conflict(ServiceError):
    """The request was made on what has changed since, or would make
    something already made otherwise."""


class Unauthenticated(ServiceError):
    """The request names no caller the service knows."""


class Forbidden(ServiceError):
    """The caller is known, and may not make the request."""


def first_reason(error: ValidationError) -> str:
    """Why a model refused what it was given, in a sentence: its first
    reason, by the field at fault, and how many more there are."""
    first = error.errors()[0]
    where = _field(first["loc"])
    more = f" (and {error.error_count() - 1} more)" if error.error_count() > 1 else ""
    return f"{where}: {first['msg']}{more}" if where else f"{first['msg']}{more}"


def every_reason(error: ValidationError) -> list[tuple[str, str]]:
    """Every reason a model refused what it was given, each by the field at
    fault, as `InvalidRequest.problems` holds them."""
    return [(_field(found["loc"]), found["msg"]) for found in error.errors()]


def _field(loc: Sequence[int | str]) -> str:
    return ".".join(str(part) for part in loc)


def read_as[T](what: str, read: Callable[[], T]) -> T:
    """A body read as the record it should be, or refused, saying why,
    before it reaches what takes it."""
    try:
        return read()
    except ValidationError as error:
        raise InvalidRequest(f"not {what}: {first_reason(error)}", every_reason(error)) from None
