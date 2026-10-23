"""What passes between a run's gateway and an executor: an assignment, one
action to carry out at an instant, and the executor's report of it
(decision 0046).

An assignment carries no principal: authorisation is the gateway's, behind
it. An executor carries an assignment out at most once, whatever number of
times it receives it, and reports when it started and finished, and whether
it was done, failed, or refused because the greenhouse was not as the
action needed. The contract the two keep is
`greenhouse_protocol.contracts.execution`.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from greenhouse_protocol.actions import Action, ActionRef, Identifier
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.outcome import ActionEffect

type Name = Annotated[str, StringConstraints(min_length=1)]


class Assignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    assignment_id: Identifier
    run_id: Name
    ref: ActionRef
    action: Action
    # When to start it.
    at: Instant
    # When it may start at the latest, if it must start by then.
    deadline: Instant | None = None

    @model_validator(mode="after")
    def _deadline_after_its_start(self) -> Self:
        if self.deadline is not None and self.deadline < self.at:
            raise ValueError("an assignment's deadline is no earlier than its start")
        return self


class ReportStatus(StrEnum):
    DONE = "done"
    FAILED = "failed"  # attempted, and not done
    REFUSED = "refused"  # not attempted: the greenhouse was not as the action needed


class ExecutionReport(BaseModel):
    """An executor's report of an assignment: done, with its start and
    finish; failed, with why; or refused before it started, with why."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    assignment_id: Identifier
    status: ReportStatus
    started_at: Instant | None = None
    finished_at: Instant | None = None
    effect: ActionEffect | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _agrees_with_its_status(self) -> Self:
        if self.status == ReportStatus.DONE:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("a done report has its start and its finish")
        elif not (self.reason or "").strip():
            raise ValueError(f"a {self.status} report says why")
        if self.status == ReportStatus.REFUSED and self.started_at is not None:
            raise ValueError("a refused assignment never started")
        if self.status == ReportStatus.FAILED and self.started_at is None:
            raise ValueError("a failed assignment was attempted: it has its start")
        if self.finished_at is not None and self.started_at is None:
            raise ValueError(f"a {self.status} report that finished started")
        if self.effect is not None and self.status != ReportStatus.DONE:
            raise ValueError(f"a {self.status} report has no effect")
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("a report finishes no earlier than it starts")
        return self
