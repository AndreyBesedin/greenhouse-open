"""What became of an action that was approved.

`ActionResult` in `greenhouse_protocol.action` answers "may this be done?". This answers
"what happened when it was done?". The two stay distinct, along with the
request itself and the observations that follow, because a proposal is
not proof that an action happened.

The outcome names its executor rather than the caller inferring one from a
simulation's configuration: who carried an action out is something the
executing side knows and the deciding side is told.
"""

from enum import StrEnum

from pydantic import BaseModel

from greenhouse_protocol.enums import ActionExecutorType


class ExecutionStatus(StrEnum):
    """No PENDING or FAILED member: execution is synchronous here and
    nothing can fail once validation has passed. Statuses are added when
    something produces them, not in anticipation."""

    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class ActionOutcome(BaseModel):
    status: ExecutionStatus
    # Who carried it out; absent when nothing was carried out.
    executor: ActionExecutorType | None = None
    # Why it was refused, when it was.
    reason: str | None = None

    @property
    def executed(self) -> bool:
        return self.status == ExecutionStatus.EXECUTED
