"""A run's plan: actions, each with its timing, what it waits for, what to
do if it is late, and who asked for it (decision 0046).

A plan belongs to one run and is given in one of its epochs; a gateway
holds it and its revisions, and decides (`greenhouse_protocol.contracts`).
What a plan can say is checked here, when it is made: a malformed plan is
refused whole, before any gateway takes it. Whether its actions can be
carried out, by whom and when, is the gateway's to decide.

The timing is any instant: the format bakes in no resolution, and each
executor says which instants it honours. A window or an as-soon-as-possible
action starts at the earliest such instant, so the same plan starts each
action at the same instant, run after run.
"""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from greenhouse_protocol.actions import Action, ActionId, ActionRef, Identifier
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.run import RunEpoch

type Name = Annotated[str, StringConstraints(min_length=1)]


class PrincipalKind(StrEnum):
    PERSON = "person"
    POLICY = "policy"
    SCHEDULE = "schedule"
    SCENARIO = "scenario"
    PLATFORM = "platform"


class Principal(BaseModel):
    """Who asks for an action, by identity: a person, a control policy, a
    schedule, a scenario's own plan, a platform."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: PrincipalKind
    id: Name


class ExecutorKind(StrEnum):
    SIMULATED_RUN = "simulated_run"
    PERSON = "person"
    ROBOT = "robot"
    CLIMATE_COMPUTER = "climate_computer"


class ExecutorRef(BaseModel):
    """Who carries an action out: a kind of executor, and which one, or any
    of the kind when `id` is None."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ExecutorKind
    id: Name | None = None


class At(BaseModel):
    """Due at an instant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["at"] = "at"
    at: Instant


class Window(BaseModel):
    """Due between two instants: it starts at the earliest one in them an
    executor can honour and is free to take."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["window"] = "window"
    not_before: Instant
    not_after: Instant

    @model_validator(mode="after")
    def _opens_before_it_closes(self) -> Self:
        if self.not_after < self.not_before:
            raise ValueError("a window closes no earlier than it opens")
        return self


class Asap(BaseModel):
    """As soon as what it waits for is done, before its deadline if it has
    one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["asap"] = "asap"
    deadline: Instant | None = None


type Timing = Annotated[At | Window | Asap, Field(discriminator="kind")]


class Recurrence(BaseModel):
    """Every `period`, `count` times or until an instant: occurrence `n`,
    from 0, is the planned action's timing moved by `n` periods. The timing
    is its one anchor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    period: timedelta
    count: Annotated[int, Field(ge=1)] | None = None
    until: Instant | None = None

    @model_validator(mode="after")
    def _positive_and_bounded(self) -> Self:
        if self.period <= timedelta(0):
            raise ValueError(f"a recurrence's period is positive, not {self.period}")
        if (self.count is None) == (self.until is None):
            raise ValueError("a recurrence ends after a count or at an instant: exactly one")
        return self


class OnLate(StrEnum):
    """What a gateway does with an action that cannot start by its due
    instant and tolerance."""

    RUN_LATE = "run_late"  # carry it out as soon as it can: `late`
    SKIP = "skip"  # nothing: `missed`, its dependents as their plan says
    CRITICAL = "critical"  # nothing: `missed`, and everything that waits for it cancelled
    FALLBACK = "fallback"  # carry out its fallback instead: `missed`, naming the fallback
    ABORT_PLAN = "abort_plan"  # nothing, nor anything else of its plan: all `cancelled`


class Lateness(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # How late still counts as on time.
    tolerance_s: Annotated[float, Field(ge=0.0)] = 0.0
    on_late: OnLate = OnLate.RUN_LATE
    # Carried out instead, as `ActionRef(action_id, fallback=True)`, when
    # `on_late` is `fallback`; given only then.
    fallback: Action | None = None

    @model_validator(mode="after")
    def _fallback_with_its_choice(self) -> Self:
        if (self.on_late == OnLate.FALLBACK) != (self.fallback is not None):
            raise ValueError("a fallback is given exactly when on_late is fallback")
        return self


class IfPrerequisiteFails(StrEnum):
    CANCEL = "cancel"
    PROCEED = "proceed"


class PlannedAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action_id: ActionId
    action: Action
    timing: Timing
    every: Recurrence | None = None
    # The planned actions that must be done first, by their ids in the plan.
    after: tuple[ActionId, ...] = ()
    if_prerequisite_fails: IfPrerequisiteFails = IfPrerequisiteFails.CANCEL
    lateness: Lateness = Lateness()
    # What the planner expects it to take; the executor reports what it took.
    expected_duration_s: Annotated[float, Field(ge=0.0)] | None = None
    # Who may carry it out; anyone, if None.
    executed_by: tuple[ExecutorRef, ...] | None = None
    proposed_by: Principal

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if len(set(self.after)) != len(self.after):
            raise ValueError(f"{self.action_id} waits for an action more than once")
        if self.action_id in self.after:
            raise ValueError(f"{self.action_id} waits for itself")
        if self.every is not None:
            anchor = self.anchor()
            if anchor is None:
                raise ValueError(
                    f"{self.action_id} recurs as soon as possible with no deadline to move"
                )
            if self.every.until is not None and self.every.until < anchor:
                raise ValueError(f"{self.action_id} recurs until before its first occurrence")
        return self

    def anchor(self) -> datetime | None:
        """The instant its timing is anchored at: its `At`, its window's
        opening, its deadline; None for an as-soon-as-possible action with
        no deadline."""
        match self.timing:
            case At(at=at):
                return at
            case Window(not_before=not_before):
                return not_before
            case Asap(deadline=deadline):
                return deadline


class Plan(BaseModel):
    """The actions a run is to carry out, given in one of its epochs as one
    revision of a plan. A revision replaces, from an instant on, the actions
    of the one before that have not started (the gateway's rule).

    Checked as made: action ids unique, every prerequisite in the plan, no
    cycle. Edges between recurring actions pair their occurrences, so two
    recurring actions may wait for one another only if they recur alike,
    occurrence `n` for occurrence `n`; a recurring action may wait for a
    one-off one, each occurrence for it; a one-off action may not wait for a
    recurring one, since which occurrence is meant is not said. With those
    edges the plan, expanded occurrence by occurrence, has a cycle only if it
    has one as given, so it is checked as given."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: Identifier
    run_id: Name
    # The epoch it is given in: a write naming an epoch that has ended is stale.
    epoch: Annotated[int, Field(ge=0)]
    revision: Annotated[int, Field(ge=1)]
    actions: tuple[PlannedAction, ...]

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        by_id: dict[str, PlannedAction] = {}
        for planned in self.actions:
            if planned.action_id in by_id:
                raise ValueError(f"the plan names {planned.action_id} more than once")
            by_id[planned.action_id] = planned
        for planned in self.actions:
            for prerequisite_id in planned.after:
                prerequisite = by_id.get(prerequisite_id)
                if prerequisite is None:
                    raise ValueError(
                        f"{planned.action_id} waits for {prerequisite_id}, not in the plan"
                    )
                _check_edge(planned, prerequisite)
        cycle = _cycle(by_id)
        if cycle:
            raise ValueError(f"the plan's actions wait for each other: {' -> '.join(cycle)}")
        return self


def _check_edge(planned: PlannedAction, prerequisite: PlannedAction) -> None:
    """One action waiting for another, as recurrences allow it."""
    if prerequisite.every is None:
        return
    if planned.every is None:
        raise ValueError(
            f"{planned.action_id} waits for {prerequisite.action_id}, which recurs: "
            "which occurrence is not said"
        )
    if planned.every != prerequisite.every:
        raise ValueError(
            f"{planned.action_id} and {prerequisite.action_id} recur differently, so their "
            "occurrences do not pair"
        )


def _cycle(by_id: dict[str, PlannedAction]) -> list[str]:
    """A cycle among the actions' prerequisites, as the ids along it, or
    none. Iterative, so that a long chain is checked, not a deep stack."""
    done: set[str] = set()
    for start in by_id:
        if start in done:
            continue
        path: list[str] = [start]
        on_path = {start}
        pending = [iter(by_id[start].after)]
        while pending:
            prerequisite_id = next(pending[-1], None)
            if prerequisite_id is None:
                pending.pop()
                finished = path.pop()
                on_path.discard(finished)
                done.add(finished)
                continue
            if prerequisite_id in on_path:
                return [*path[path.index(prerequisite_id) :], prerequisite_id]
            if prerequisite_id not in done:
                path.append(prerequisite_id)
                on_path.add(prerequisite_id)
                pending.append(iter(by_id[prerequisite_id].after))
    return []


class ActionKey(BaseModel):
    """An action as a caller saw it, to cancel it: in a plan, a revision and
    an epoch. A key whose action a later revision replaced, or whose epoch
    has ended, is stale: refused, and nothing cancelled. An occurrence of
    None, for a recurring action, means every occurrence still to come."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: Identifier
    epoch: Annotated[int, Field(ge=0)]
    revision: Annotated[int, Field(ge=1)]
    ref: ActionRef


class ActionStateKind(StrEnum):
    WAITING = "waiting"  # for its time, or for what it waits for
    DUE = "due"
    ASSIGNED = "assigned"  # sent to an executor
    STARTED = "started"


class ActionState(BaseModel):
    """An action not yet resolved, as it stands: what a gateway lists. Once
    resolved, it is an outcome in the outcome log, not a state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    ref: ActionRef
    action: Action
    timing: Timing
    # When it falls due, where that is known yet: an instant, or a window.
    due: Instant | Window | None = None
    principal: Principal
    state: ActionStateKind
    waiting_for: tuple[ActionRef, ...] = ()
    waited_on_by: tuple[ActionRef, ...] = ()
    # The run and epoch it was carried from, if it was.
    carried_from: RunEpoch | None = None
