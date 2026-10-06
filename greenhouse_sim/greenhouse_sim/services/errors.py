"""What can go wrong in a service, in the client's terms.

Each error carries a message for the client, saying what went wrong and,
where it helps, what would be accepted instead. An interface turns each kind
into its own answer, such as an HTTP status; a service never chooses one.
"""


class ServiceError(Exception):
    """A request a service could not carry out, and why."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    """Something the request names does not exist."""


class InvalidRequest(ServiceError):
    """The request cannot be met as it stands."""
