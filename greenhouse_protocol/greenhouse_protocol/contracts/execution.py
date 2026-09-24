"""How an approved action reaches whatever carries it out.

A decision system decides what should happen. Something else makes it
happen: a simulated world, or in a real deployment a task assigned to a
grower, a climate controller or a robot. Those are interchangeable behind
this one contract, so that decision logic does not know which it is talking
to. The contract belongs to neither side.

Not every environment can execute. Recorded history cannot change, so a
replay adapter refuses rather than pretending, and `ActionNotExecutable` is
how it says so: replay can never execute an action by accident.
"""

from datetime import datetime
from typing import Protocol

from greenhouse_protocol.action import RequestedAction
from greenhouse_protocol.execution import ActionOutcome


class ActionNotExecutable(Exception):
    """This environment cannot carry actions out at all."""

    def __init__(self, greenhouse_id: str, reason: str) -> None:
        super().__init__(reason)
        self.greenhouse_id = greenhouse_id
        self.reason = reason


class ActionExecutionAdapter(Protocol):
    def execute(
        self, greenhouse_id: str, actions: list[RequestedAction], *, at: datetime
    ) -> list[ActionOutcome]:
        """Validates and carries out each action, in order.

        Returns one outcome per action given, positionally, so a refused
        action keeps its place. Raises `ActionNotExecutable` if the
        environment cannot execute at all, which is a different thing from
        refusing a particular action.
        """
        ...
