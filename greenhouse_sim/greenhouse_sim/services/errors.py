"""What can go wrong in a service, in the client's terms.

Each error carries a message for the client, saying what went wrong and,
where it helps, what would be accepted instead. An interface turns each kind
into its own answer, such as an HTTP status; a service never chooses one.
"""

from pydantic import ValidationError


class ServiceError(Exception):
    """A request a service could not carry out, and why."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    """Something the request names does not exist."""


class InvalidRequest(ServiceError):
    """The request cannot be met as it stands."""


class Conflict(ServiceError):
    """The request was made on what has changed since, or would make
    something already made otherwise."""


def first_reason(error: ValidationError) -> str:
    """Why a model refused what it was given, in a sentence: its first
    reason, by the field at fault, and how many more there are."""
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    more = f" (and {error.error_count() - 1} more)" if error.error_count() > 1 else ""
    return f"{where}: {first['msg']}{more}" if where else f"{first['msg']}{more}"
