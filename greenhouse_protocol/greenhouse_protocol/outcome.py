"""What became of a planned action: one outcome record each (decision 0046).

Every planned action, every occurrence of a recurring one and every
fallback ends in exactly one outcome, which a run's gateway writes to an
outcome log of its own, beside the observations and events, with the
consumer interface's rules (`greenhouse_protocol.contracts.consumer`). An
outcome carries the action it is about as it was asked, so that a reader
who did not give the plan knows what was or was not done. A carried-out
action's effect is still the event it produced, which names its action.

This replaces `greenhouse_protocol.execution`, which stays, deprecated,
until the simulator carries this format out (P13).
"""

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from greenhouse_protocol.actions import Action, ActionKind, ActionRef, Identifier
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.plan import ExecutorRef, Principal, Timing, Window

type Name = Annotated[str, StringConstraints(min_length=1)]


class OutcomeStatus(StrEnum):
    EXECUTED = "executed"
    LATE = "late"  # carried out, past its tolerance
    MISSED = "missed"  # not carried out, being late
    REFUSED = "refused"  # not carried out: malformed for this run, not allowed, or not possible
    FAILED = "failed"  # attempted, and not done
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"  # dropped by a later revision before it started
    UNCONFIRMED = "unconfirmed"  # its executor never reported


# The outcomes of an action that ran, and those that never started.
RAN: Final = frozenset({OutcomeStatus.EXECUTED, OutcomeStatus.LATE})
NOT_STARTED: Final = frozenset(
    {
        OutcomeStatus.MISSED,
        OutcomeStatus.REFUSED,
        OutcomeStatus.CANCELLED,
        OutcomeStatus.SUPERSEDED,
    }
)


class LevelSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["level_set"] = "level_set"
    device_id: Name
    level: Annotated[float, Field(ge=0.0, le=1.0)] | Literal["auto"]


class TargetSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["target_set"] = "target_set"
    target: Name
    value_c: float


class Watered(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["watered"] = "watered"
    amount_ml: Annotated[float, Field(ge=0.0)]


class Harvested(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["harvested"] = "harvested"
    fruit_count: Annotated[int, Field(ge=0)]
    fresh_mass_g: Annotated[float, Field(ge=0.0)]


class Lowered(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["lowered"] = "lowered"
    by_cm: Annotated[float, Field(ge=0.0)]


class LeafRemoved(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["leaf_removed"] = "leaf_removed"
    leaf_id: Name


class Inspected(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["inspected"] = "inspected"


type ActionEffect = Annotated[
    LevelSet | TargetSet | Watered | Harvested | Lowered | LeafRemoved | Inspected,
    Field(discriminator="kind"),
]

# The effect each kind of action has, when it is carried out.
EFFECT_OF: Final = {
    ActionKind.SET_LEVEL: "level_set",
    ActionKind.SET_TARGET: "target_set",
    ActionKind.WATER: "watered",
    ActionKind.HARVEST: "harvested",
    ActionKind.LOWER: "lowered",
    ActionKind.REMOVE_LEAF: "leaf_removed",
    ActionKind.INSPECT: "inspected",
}


class ActionOutcome(BaseModel):
    """One planned action's end. Its fields agree with its status: an action
    that ran has its times and its executor; one that never started has
    neither, and says why; only a cancelled or superseded one names who did
    it, only a missed one its fallback, only one that ran its effect, which
    is its action's kind's. `resolved_at`, when the outcome was decided, is
    always set and orders the log; `due` is None only for an
    as-soon-as-possible action dropped before it could start."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome_id: Identifier
    greenhouse_id: Name
    run_id: Name
    epoch: Annotated[int, Field(ge=0)]
    plan_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    ref: ActionRef
    action: Action
    timing: Timing
    principal: Principal
    status: OutcomeStatus
    due: Instant | Window | None
    started_at: Instant | None = None
    finished_at: Instant | None = None
    resolved_at: Instant
    # When it reached the log, if later than it was resolved.
    delivered_at: Instant | None = None
    executor: ExecutorRef | None = None
    reason: str | None = None
    cancelled_by: Principal | None = None
    fallback: ActionRef | None = None
    effect: ActionEffect | None = None
    event_id: Name | None = None

    @model_validator(mode="after")
    def _agrees_with_its_status(self) -> Self:
        status = self.status
        if status in RAN:
            if self.started_at is None or self.finished_at is None or self.executor is None:
                raise ValueError(f"a {status} outcome has its start, its finish and its executor")
        elif not (self.reason or "").strip():
            raise ValueError(f"a {status} outcome says why")
        if status in NOT_STARTED and (self.started_at is not None or self.executor is not None):
            raise ValueError(f"a {status} outcome never started, and has no executor")
        if self.cancelled_by is not None and status not in {
            OutcomeStatus.CANCELLED,
            OutcomeStatus.SUPERSEDED,
        }:
            raise ValueError(f"a {status} outcome was not cancelled by anyone")
        if self.fallback is not None and status != OutcomeStatus.MISSED:
            raise ValueError(f"a {status} outcome had no fallback carried out instead")
        if self.effect is not None:
            if status not in RAN:
                raise ValueError(f"a {status} outcome has no effect")
            if self.effect.kind != EFFECT_OF[self.action.kind]:
                raise ValueError(
                    f"a {self.action.kind} action's effect is {EFFECT_OF[self.action.kind]}, "
                    f"not {self.effect.kind}"
                )
        if self.due is None and not (
            self.timing.kind == "asap"
            and status in {OutcomeStatus.REFUSED, OutcomeStatus.CANCELLED, OutcomeStatus.SUPERSEDED}
        ):
            raise ValueError(
                "only an as-soon-as-possible action dropped before it could start has no due"
            )
        _check_order(
            ("started", self.started_at),
            ("finished", self.finished_at),
            ("resolved", self.resolved_at),
            ("delivered", self.delivered_at),
        )
        return self


def _check_order(*moments: tuple[str, Instant | None]) -> None:
    """Instants that come in this order, those that are set."""
    known = [(name, at) for name, at in moments if at is not None]
    for (earlier, first), (later, second) in zip(known, known[1:], strict=False):
        if second < first:
            raise ValueError(f"an outcome is {later} no earlier than it is {earlier}")
