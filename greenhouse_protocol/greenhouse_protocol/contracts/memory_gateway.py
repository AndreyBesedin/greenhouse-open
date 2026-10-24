"""An in-memory reference implementation of the actuation contracts
(decision 0046): a run's gateway on a clock that continues, and an executor
that may be told to lose messages. They keep every rule the contracts'
conformance checks hold an implementation to (`check_gateway`,
`check_executor`), so a gateway or an executor of one's own is developed
against them. The memory executor acts on nothing; the gateway acts
through whichever executor on its clock it is given (`ClockedExecutor`),
such as a simulator's run.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final, Protocol

from greenhouse_protocol.actions import (
    Action,
    ActionKind,
    ActionRef,
    ActionTargets,
    Harvest,
    Inspect,
    Lower,
    RemoveLeaf,
    SetLevel,
    SetTarget,
    Water,
    targets_of,
)
from greenhouse_protocol.assignment import Assignment, ExecutionReport, ReportStatus
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.contracts.consumer import OutcomeBatch, RunClock, RunDescriptor
from greenhouse_protocol.contracts.execution import (
    ActionNotExecutable,
    AssignmentStatus,
    ExecutorUnderTest,
    Revocation,
)
from greenhouse_protocol.contracts.gateway import (
    STARTED_OVER,
    AuthorisationChange,
    GatewayLimits,
    PlanState,
    Receipt,
    check_limits,
    occurrences,
)
from greenhouse_protocol.outcome import (
    ActionEffect,
    ActionOutcome,
    Harvested,
    Inspected,
    LeafRemoved,
    LevelSet,
    Lowered,
    OutcomeStatus,
    TargetSet,
    Watered,
)
from greenhouse_protocol.plan import (
    ActionKey,
    ActionState,
    ActionStateKind,
    Asap,
    At,
    ExecutorKind,
    ExecutorRef,
    IfPrerequisiteFails,
    OnLate,
    Plan,
    PlannedAction,
    Principal,
    Timing,
    Window,
)
from greenhouse_protocol.run import RunEpoch

EXECUTOR: Final = ExecutorRef(kind=ExecutorKind.ROBOT, id="memory")
# As many actions at once as anyone asks of the memory executor.
UNLIMITED: Final = 1_000_000
# A harvest the memory executor makes: one fruit, of this fresh mass.
FRUIT_G: Final = 50.0
CONTROLLER_TARGETS: Final = frozenset({"heating_day", "heating_night"})
NOT_STARTED: Final = frozenset({ActionStateKind.WAITING, ActionStateKind.DUE})


class ClockedExecutor(ExecutorUnderTest, Protocol):
    """An executor on the gateway's own clock: the gateway moves it as its
    clock moves, and wakes when each of its assignments will finish, as a
    gateway on a real clock hears the report."""

    def finishes(self) -> tuple[datetime, ...]: ...


def effect_of(action: Action) -> ActionEffect:
    """What the memory executor does when it carries an action out."""
    match action:
        case SetLevel(device_id=device, level=level):
            return LevelSet(device_id=device, level=level)
        case SetTarget(target=target, value_c=value):
            return TargetSet(target=target, value_c=value)
        case Water(amount_ml=amount):
            return Watered(amount_ml=amount)
        case Harvest():
            return Harvested(fruit_count=1, fresh_mass_g=FRUIT_G)
        case Lower(by_cm=by_cm):
            return Lowered(by_cm=by_cm or 0.0)
        case RemoveLeaf(leaf_id=leaf):
            return LeafRemoved(leaf_id=leaf)
        case Inspect():
            return Inspected()


@dataclass
class _Held:
    assignment: Assignment
    started: datetime | None = None
    finished: datetime | None = None
    revoked: bool = False


class MemoryExecutor:
    """Carries out every kind at any instant, `duration_s` after it starts.
    Two faults can be injected, to test a gateway against: it loses each
    assignment's first send if `loses_first_send`, and cannot be reached
    about the assignments of the actions in `unreachable`, carrying them
    out but never reporting them, and answering their status unknown."""

    def __init__(
        self,
        start: datetime,
        *,
        lead_s: float = 0.0,
        duration_s: float = 0.0,
        longest_s: float = 60.0,
        loses_first_send: bool = False,
        unreachable: frozenset[str] = frozenset(),
    ) -> None:
        self.now = start
        self._lead_s = lead_s
        self._duration = timedelta(seconds=duration_s)
        self._longest_s = longest_s
        self._loses_first_send = loses_first_send
        self._unreachable = unreachable
        self._held: dict[str, _Held] = {}
        self._lost: set[str] = set()
        self._reports: list[ExecutionReport] = []

    def kinds(self) -> frozenset[ActionKind]:
        return frozenset(ActionKind)

    def honours(self, kind: ActionKind, instant: datetime) -> bool:
        return True

    def capacity(self) -> int:
        return UNLIMITED

    def lead_time_s(self, kind: ActionKind) -> float:
        return self._lead_s

    def longest_duration_s(self, kind: ActionKind) -> float:
        return self._longest_s

    def perform(self, assignment: Assignment) -> None:
        if assignment.assignment_id in self._held:
            return
        if self._loses_first_send and assignment.assignment_id not in self._lost:
            self._lost.add(assignment.assignment_id)
            return
        self._held[assignment.assignment_id] = _Held(assignment)

    def revoke(self, assignment_id: str) -> Revocation:
        held = self._held.get(assignment_id)
        if held is None:
            return Revocation.UNKNOWN
        if held.finished is not None:
            return Revocation.FINISHED
        if held.started is not None:
            return Revocation.STARTED
        held.revoked = True
        return Revocation.REVOKED

    def status(self, assignment_id: str) -> AssignmentStatus:
        held = self._held.get(assignment_id)
        if held is None or held.assignment.ref.action_id in self._unreachable:
            return AssignmentStatus.UNKNOWN
        if held.revoked:
            return AssignmentStatus.REVOKED
        if held.finished is not None:
            return AssignmentStatus.FINISHED
        if held.started is not None:
            return AssignmentStatus.STARTED
        return AssignmentStatus.RECEIVED

    def reports(self, after: int = 0) -> tuple[ExecutionReport, ...]:
        return tuple(self._reports[after:])

    def finishes(self) -> tuple[datetime, ...]:
        """When each assignment it holds and has not finished will finish,
        so that a gateway on the same clock wakes then, as one on a real
        clock hears the report."""
        return tuple(
            (held.started or held.assignment.at) + self._duration
            for held in self._held.values()
            if not held.revoked and held.finished is None
        )

    def advance(self, to: datetime) -> None:
        held_in_order = sorted(
            self._held.values(), key=lambda h: (h.assignment.at, h.assignment.assignment_id)
        )
        for held in held_in_order:
            if held.revoked or held.finished is not None or held.assignment.at > to:
                continue
            if held.started is None:
                held.started = held.assignment.at
            done = held.started + self._duration
            if done > to:
                continue
            held.finished = done
            if held.assignment.ref.action_id not in self._unreachable:
                self._reports.append(
                    ExecutionReport(
                        assignment_id=held.assignment.assignment_id,
                        status=ReportStatus.DONE,
                        started_at=held.started,
                        finished_at=done,
                        effect=effect_of(held.assignment.action),
                    )
                )
        self.now = max(self.now, to)


@dataclass
class _Action:
    """One action of a plan as the gateway holds it: an occurrence, or a
    fallback."""

    plan_id: str
    revision: int
    ref: ActionRef
    planned: PlannedAction
    action: Action
    timing: Timing
    principal: Principal
    waits_for: list[str]
    order: tuple[int, int, int]
    state: ActionStateKind = ActionStateKind.WAITING
    due: datetime | None = None
    assignment_id: str | None = None
    starts_at: datetime | None = None
    late: bool = False
    carried_from: RunEpoch | None = None
    # Where the gateway holds it: under its key, or, once a revision has
    # replaced it while it ran, under a key of its revision's, so that it
    # still ends in its own outcome.
    slot: str = ""

    @property
    def key(self) -> str:
        return f"{self.plan_id}/{self.ref}"

    @property
    def current(self) -> bool:
        """Whether it is its key's incarnation, not one a revision replaced."""
        return self.slot in {"", self.key}


@dataclass
class _PlanRecord:
    owner: Principal
    sequence: int
    revisions: dict[int, Plan] = field(default_factory=dict)

    @property
    def latest(self) -> Plan:
        return self.revisions[max(self.revisions)]


def _key(plan_id: str, action_id: str, occurrence: int | None) -> str:
    return f"{plan_id}/{ActionRef(action_id=action_id, occurrence=occurrence)}"


def _moved(timing: Timing, by: timedelta) -> Timing:
    match timing:
        case At(at=at):
            return At(at=at + by)
        case Window(not_before=not_before, not_after=not_after):
            return Window(not_before=not_before + by, not_after=not_after + by)
        case Asap(deadline=deadline):
            return Asap(deadline=None if deadline is None else deadline + by)


class InMemoryGateway:
    """A run's gateway, in memory, on a clock that continues: a restart that
    continues the clock carries what is pending, one that does not starts
    the run over, and may follow a finish. `items` is what the run has to
    act on, its controller's targets among them, and `executor_ref` names
    its executor in outcomes and in a plan's `executed_by`."""

    def __init__(
        self,
        authorisation: AuthorisationConfig,
        start: datetime,
        *,
        executor: ClockedExecutor | None = None,
        executor_ref: ExecutorRef = EXECUTOR,
        items: ActionTargets | None = None,
        limits: GatewayLimits | None = None,
        greenhouse_id: str = "gh_memory",
        run_id: str = "run_memory",
    ) -> None:
        self.greenhouse_id = greenhouse_id
        self.run_id = run_id
        self._start = start
        self.now = start
        self.epoch = 0
        self.started_at = start
        self.continues_from: RunEpoch | None = None
        self.finished = False
        self._executor: ClockedExecutor = executor or MemoryExecutor(start)
        self._executor_ref = executor_ref
        self._items = items or ActionTargets(
            devices=frozenset({"vent_1", "heater"}),
            plants=frozenset({"p30", "p31"}),
            targets=CONTROLLER_TARGETS,
        )
        self._limits = limits or GatewayLimits(max_actions=100, max_occurrences=1000)
        self._config = authorisation
        self._authorisation = [AuthorisationChange(version=authorisation.version, at=start)]
        self._plans: dict[str, _PlanRecord] = {}
        self._actions: dict[str, _Action] = {}
        self._resolved: dict[str, ActionOutcome] = {}
        self._failed_hard: set[str] = set()
        self._log: list[ActionOutcome] = []
        self._sequence = 0
        self._made = 0
        self._reports_seen = 0

    # The contract.

    def run(self) -> RunDescriptor:
        return RunDescriptor(
            run_id=self.run_id,
            epoch=self.epoch,
            greenhouse_id=self.greenhouse_id,
            started_at=self.started_at,
            clock=RunClock(
                simulated_now=self.now,
                day=(self.now - self.started_at).days,
                playing=not self.finished,
            ),
            continues_from=self.continues_from,
        )

    def limits(self) -> GatewayLimits:
        return self._limits

    def submit(self, plan: Plan, *, by: Principal) -> Receipt:
        self._writable()
        record = self._plans.get(plan.plan_id)
        previous = None if record is None else record.latest
        errors = list(self._stale(plan, record))
        if record is not None and by != record.owner and not self._config.may_manage_plans(by):
            errors.append(f"{by.id} neither owns plan {plan.plan_id!r} nor may manage plans")
        errors += check_limits(plan, self._limits)
        kept = {} if previous is None else {p.action_id: p for p in previous.actions}
        for planned in plan.actions:
            if kept.get(planned.action_id) == planned:
                continue
            if not self._config.may_propose_for(by, planned.proposed_by):
                errors.append(
                    f"{by.id} may not propose {planned.action_id} for {planned.proposed_by.id}"
                )
        if errors:
            return Receipt(
                accepted=False, plan_id=plan.plan_id, revision=plan.revision, errors=tuple(errors)
            )
        self._sequence += 1
        if record is None:
            record = self._plans[plan.plan_id] = _PlanRecord(owner=by, sequence=self._sequence)
        record.sequence = self._sequence
        record.revisions[plan.revision] = plan
        self._revise(plan, kept, by)
        refused = self._add(plan, kept, record.sequence)
        self._step()
        return Receipt(
            accepted=True,
            plan_id=plan.plan_id,
            revision=plan.revision,
            sequence=record.sequence,
            refused=refused,
        )

    def cancel(self, keys: Sequence[ActionKey], *, by: Principal) -> Receipt:
        self._writable()
        cancelled: list[ActionRef] = []
        stale: list[ActionKey] = []
        not_permitted: list[ActionKey] = []
        for key in keys:
            record = self._plans.get(key.plan_id)
            if record is None or key.epoch != self.epoch or key.revision != max(record.revisions):
                stale.append(key)
                continue
            if by != record.owner and not self._config.may_manage_plans(by):
                not_permitted.append(key)
                continue
            for action in self._chosen(key):
                if self._withdraw(action):
                    self._end(action, OutcomeStatus.CANCELLED, reason="cancelled", cancelled_by=by)
                    cancelled.append(action.ref)
        self._step()
        return Receipt(
            accepted=True,
            cancelled=tuple(cancelled),
            stale=tuple(stale),
            not_permitted=tuple(not_permitted),
        )

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int, by: Principal) -> Receipt:
        self._writable()
        record = self._plans.get(plan_id)
        if record is None or epoch != self.epoch or revision != max(record.revisions):
            return Receipt(
                accepted=False, plan_id=plan_id, errors=("stale: not the revision in force",)
            )
        if by != record.owner and not self._config.may_manage_plans(by):
            return Receipt(accepted=False, plan_id=plan_id, errors=(f"{by.id} may not cancel it",))
        cancelled = []
        for action in [a for a in self._in_order() if a.plan_id == plan_id]:
            if self._withdraw(action):
                self._end(
                    action,
                    OutcomeStatus.CANCELLED,
                    reason="the plan was cancelled",
                    cancelled_by=by,
                )
                cancelled.append(action.ref)
        self._step()
        return Receipt(
            accepted=True, plan_id=plan_id, revision=revision, cancelled=tuple(cancelled)
        )

    def actions(
        self,
        *,
        states: frozenset[ActionStateKind] | None = None,
        kinds: frozenset[ActionKind] | None = None,
        targets: ActionTargets | None = None,
        plan_id: str | None = None,
    ) -> tuple[ActionState, ...]:
        return tuple(
            self._state(action)
            for action in self._in_order()
            if (states is None or action.state in states)
            and (kinds is None or action.action.kind in kinds)
            and (plan_id is None or action.plan_id == plan_id)
            and (targets is None or _acts_on_any(action.action, targets))
        )

    def plan(self, plan_id: str, revision: int | None = None) -> PlanState:
        record = self._plans[plan_id]
        return PlanState(
            plan=record.revisions[revision or max(record.revisions)],
            owner=record.owner,
            sequence=record.sequence,
            unresolved=self.actions(plan_id=plan_id),
            outcomes=tuple(o for o in self._log if o.plan_id == plan_id),
            authorisation=tuple(self._authorisation),
        )

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch:
        chosen = self._log[after:] if limit is None else self._log[after : after + limit]
        return OutcomeBatch(
            run_id=self.run_id,
            epoch=self.epoch,
            after=after,
            next=after + len(chosen),
            simulated_now=self.now,
            has_more=after + len(chosen) < len(self._log),
            outcomes=tuple(chosen),
        )

    # What a test moves it with.

    def items(self) -> ActionTargets:
        return self._items

    def advance(self, to: datetime) -> None:
        while (moment := self._next_moment(to)) is not None:
            self.now = moment
            self._step()
        self.now = max(self.now, to)
        self._step()

    def authorise(self, config: AuthorisationConfig) -> None:
        self._config = config
        self._authorisation.append(AuthorisationChange(version=config.version, at=self.now))

    def restart(self, *, continue_clock: bool) -> None:
        before = RunEpoch(run_id=self.run_id, epoch=self.epoch)
        pending = self._in_order()
        self.epoch += 1
        self._log = []
        self._reports_seen = len(self._executor.reports())
        if continue_clock:
            self.started_at = self.now
            self.continues_from = before
            for action in pending:
                action.carried_from = before
                reason = self._cannot(
                    action.action, action.principal, action.timing, action.planned.executed_by
                )
                if reason is not None:
                    self._withdraw(action)
                    self._end(action, OutcomeStatus.REFUSED, reason=f"{reason}, as it was carried")
                elif action.state == ActionStateKind.ASSIGNED and action.assignment_id is not None:
                    if self._executor.revoke(action.assignment_id) == Revocation.REVOKED:
                        action.state = ActionStateKind.WAITING
                        action.assignment_id = None
        else:
            self.now = self.started_at = self._start
            self.continues_from = None
            self.finished = False
            for action in pending:
                self._withdraw(action)
                self._end(action, OutcomeStatus.CANCELLED, reason=f"the run {STARTED_OVER}")
            self._plans = {}
        self._step()

    def finish(self) -> None:
        for action in self._in_order():
            self._withdraw(action)
            self._end(action, OutcomeStatus.CANCELLED, reason="the run finished")
        self.finished = True

    # Within.

    def _writable(self) -> None:
        if self.finished:
            raise ActionNotExecutable(self.greenhouse_id, f"run {self.run_id!r} has finished")

    def _stale(self, plan: Plan, record: _PlanRecord | None) -> list[str]:
        stale = []
        if plan.run_id != self.run_id:
            stale.append(f"plan {plan.plan_id!r} is for run {plan.run_id!r}, not {self.run_id!r}")
        if plan.epoch != self.epoch:
            stale.append(f"stale: plan {plan.plan_id!r} names epoch {plan.epoch}, not {self.epoch}")
        if record is not None and plan.revision <= max(record.revisions):
            stale.append(f"stale: revision {plan.revision} of {plan.plan_id!r} is not newer")
        return stale

    def _cannot(
        self,
        action: Action,
        principal: Principal,
        timing: Timing,
        executed_by: tuple[ExecutorRef, ...] | None = None,
    ) -> str | None:
        if not self._config.allows(principal, action):
            return f"{principal.id} is not authorised to {action.kind}"
        if action.kind not in self._executor.kinds():
            return f"no executor carries out {action.kind}"
        if executed_by is not None and not any(
            _names(each, self._executor_ref) for each in executed_by
        ):
            permitted = ", ".join(f"{each.kind}:{each.id or 'any'}" for each in executed_by)
            return f"none of those who may carry it out ({permitted}) is this run's executor"
        acted_on = targets_of(action)
        missing = (
            (acted_on.devices - self._items.devices)
            | (acted_on.plants - self._items.plants)
            | (acted_on.targets - self._items.targets)
        )
        if missing:
            return f"the run has no {', '.join(sorted(missing))}"
        if isinstance(timing, At) and not self._executor.honours(action.kind, timing.at):
            return f"no executor honours {action.kind} at {timing.at.isoformat()}"
        return None

    def _revise(self, plan: Plan, kept: dict[str, PlannedAction], by: Principal) -> None:
        for action in [a for a in self._in_order() if a.plan_id == plan.plan_id]:
            if kept.get(action.ref.action_id) in plan.actions:
                action.revision = plan.revision
            elif self._withdraw(action):
                self._end(
                    action,
                    OutcomeStatus.SUPERSEDED,
                    reason=f"revision {plan.revision}",
                    cancelled_by=by,
                )

    def _add(
        self, plan: Plan, kept: dict[str, PlannedAction], sequence: int
    ) -> tuple[ActionRef, ...]:
        refused = []
        by_id = {p.action_id: p for p in plan.actions}
        for position, planned in enumerate(plan.actions):
            if kept.get(planned.action_id) == planned:
                continue
            count = occurrences(planned)
            for n in range(count):
                occurrence = None if planned.every is None else n
                waits_for = [
                    _key(
                        plan.plan_id,
                        prerequisite,
                        occurrence if by_id[prerequisite].every else None,
                    )
                    for prerequisite in planned.after
                ]
                timing = planned.timing
                if planned.every is not None:
                    timing = _moved(planned.timing, planned.every.period * n)
                action = _Action(
                    plan_id=plan.plan_id,
                    revision=plan.revision,
                    ref=ActionRef(action_id=planned.action_id, occurrence=occurrence),
                    planned=planned,
                    action=planned.action,
                    timing=timing,
                    principal=planned.proposed_by,
                    waits_for=waits_for,
                    order=(sequence, position, n),
                    due=_due(timing),
                )
                reason = self._cannot(action.action, action.principal, timing, planned.executed_by)
                if reason is not None:
                    self._retire(action.key)
                    self._end(action, OutcomeStatus.REFUSED, reason=reason)
                    refused.append(action.ref)
                else:
                    self._hold(action)
        return tuple(refused)

    def _retire(self, key: str) -> None:
        """Makes way for a new incarnation of the action under `key`. The one
        before, which started and so a revision could not withdraw, runs on
        under its revision's key, to its own outcome; and what the one
        before resolved to is forgotten, so that what waits for the key
        waits for the new incarnation."""
        before = self._actions.get(key)
        if before is not None:
            before.slot = f"{key}#{before.revision}"
            self._actions[before.slot] = before
            del self._actions[key]
        self._resolved.pop(key, None)
        self._failed_hard.discard(key)

    def _hold(self, action: _Action) -> None:
        """Holds a new incarnation of an action under its key."""
        self._retire(action.key)
        action.slot = action.key
        self._actions[action.key] = action

    def _active(self, action: _Action) -> bool:
        """Whether an action taken from an earlier listing is still held: one
        ended since, as by an aborted plan, is not dispatched."""
        return self._actions.get(action.slot or action.key) is action

    def _chosen(self, key: ActionKey) -> list[_Action]:
        return [
            action
            for action in self._in_order()
            if action.plan_id == key.plan_id
            and action.ref.action_id == key.ref.action_id
            and action.ref.fallback == key.ref.fallback
            and (key.ref.occurrence is None or action.ref.occurrence == key.ref.occurrence)
        ]

    def _withdraw(self, action: _Action) -> bool:
        """Takes an action back before it starts, revoking its assignment if
        it has one; False if it started already."""
        if action.state == ActionStateKind.STARTED:
            return False
        if (
            action.state == ActionStateKind.ASSIGNED
            and action.assignment_id is not None
            and self._executor.revoke(action.assignment_id) != Revocation.REVOKED
        ):
            action.state = ActionStateKind.STARTED
            return False
        return True

    def _in_order(self) -> list[_Action]:
        """Its actions in the one order of one instant: by when they fall
        due, then recurring before one-off, then the order the revisions
        were accepted in, then place in the plan. What waits for a
        prerequisite is held back until it resolves."""
        return sorted(
            self._actions.values(),
            key=lambda a: (
                a.due or datetime.max.replace(tzinfo=self.now.tzinfo),
                a.planned.every is None,
                a.order,
            ),
        )

    def _next_moment(self, to: datetime) -> datetime | None:
        moments = []
        for action in self._actions.values():
            lead = timedelta(seconds=self._executor.lead_time_s(action.action.kind))
            longest = timedelta(seconds=self._executor.longest_duration_s(action.action.kind))
            if action.due is not None and action.state in NOT_STARTED:
                moments += [action.due - lead, action.due]
            if action.starts_at is not None:
                moments += [action.starts_at, action.starts_at + longest]
        moments += self._executor.finishes()
        later = [m for m in moments if self.now < m <= to]
        return min(later, default=None)

    def _step(self) -> None:
        """Everything that happens at the clock's instant, until nothing more
        does."""
        while True:
            before = (
                len(self._log),
                tuple((a.key, a.state, a.due) for a in self._actions.values()),
            )
            # Checked again as it falls due, before the executor may start it.
            self._recheck_due()
            self._executor.advance(self.now)
            self._collect()
            self._settle()
            self._dispatch()
            self._time_out()
            if before == (
                len(self._log),
                tuple((a.key, a.state, a.due) for a in self._actions.values()),
            ):
                return

    def _collect(self) -> None:
        reports = self._executor.reports(self._reports_seen)
        self._reports_seen += len(reports)
        by_assignment = {a.assignment_id: a for a in self._actions.values() if a.assignment_id}
        for report in reports:
            action = by_assignment.get(report.assignment_id)
            if action is None:
                continue
            if report.status == ReportStatus.DONE:
                status = OutcomeStatus.LATE if action.late else OutcomeStatus.EXECUTED
                self._end(action, status, report=report)
            elif report.status == ReportStatus.FAILED:
                self._end(action, OutcomeStatus.FAILED, report=report, reason=report.reason)
            else:
                self._end(action, OutcomeStatus.REFUSED, reason=report.reason)

    def _settle(self) -> None:
        for action in self._in_order():
            if not self._active(action) or action.state not in NOT_STARTED:
                continue
            ends = [self._resolved.get(key) for key in action.waits_for]
            failed = [
                key
                for key, end in zip(action.waits_for, ends, strict=True)
                if end is not None
                and end.status not in {OutcomeStatus.EXECUTED, OutcomeStatus.LATE}
            ]
            if failed and (
                action.planned.if_prerequisite_fails == IfPrerequisiteFails.CANCEL
                or any(key in self._failed_hard for key in failed)
            ):
                self._end(
                    action,
                    OutcomeStatus.CANCELLED,
                    reason=f"its prerequisite {failed[0]} did not end done",
                )
                continue
            if any(end is None for end in ends):
                continue
            if action.due is None and isinstance(action.timing, Asap):
                action.due = self.now

    def _dispatch(self) -> None:
        for action in self._in_order():
            if not self._active(action) or action.state != ActionStateKind.WAITING:
                continue
            if action.due is None or any(self._resolved.get(k) is None for k in action.waits_for):
                continue
            lead = timedelta(seconds=self._executor.lead_time_s(action.action.kind))
            if self.now < action.due - lead:
                continue
            if not self._config.allows(action.principal, action.action):
                self._end(
                    action,
                    OutcomeStatus.REFUSED,
                    reason=f"{action.principal.id} is no longer authorised",
                )
                continue
            deadline = _deadline(action)
            if deadline is not None and self.now > deadline:
                self._late(action)
                continue
            self._assign(action)

    def _recheck_due(self) -> None:
        """Each assignment whose instant has come, its authorisation checked
        again: revoked, and refused, if its principal may no longer carry it
        out; started otherwise."""
        for action in self._in_order():
            if (
                not self._active(action)
                or action.state != ActionStateKind.ASSIGNED
                or action.starts_at is None
                or self.now < action.starts_at
            ):
                continue
            if not self._config.allows(action.principal, action.action) and self._withdraw(action):
                self._end(
                    action,
                    OutcomeStatus.REFUSED,
                    reason=f"{action.principal.id} is no longer authorised",
                )
            elif action.state == ActionStateKind.ASSIGNED:
                action.state = ActionStateKind.STARTED

    def _assign(self, action: _Action, *, late: bool = False) -> None:
        assert action.due is not None
        self._made += 1
        action.assignment_id = f"e{self.epoch}-a{self._made}"
        action.starts_at = max(action.due, self.now)
        action.late = late
        assignment = Assignment(
            assignment_id=action.assignment_id,
            run_id=self.run_id,
            ref=action.ref,
            action=action.action,
            at=action.starts_at,
            # One carried out late has no deadline left to start by.
            deadline=None if late else _deadline(action),
        )
        self._executor.perform(assignment)
        if self._executor.status(assignment.assignment_id) == AssignmentStatus.UNKNOWN:
            self._executor.perform(assignment)  # unsure it arrived: sent again, at most once
        action.state = ActionStateKind.ASSIGNED

    def _late(self, action: _Action) -> None:
        on_late = action.planned.lateness.on_late
        if on_late == OnLate.RUN_LATE:
            self._assign(action, late=True)
            return
        fallback = None
        if on_late == OnLate.FALLBACK and action.planned.lateness.fallback is not None:
            fallback = ActionRef(
                action_id=action.ref.action_id, occurrence=action.ref.occurrence, fallback=True
            )
            self._hold(
                _Action(
                    plan_id=action.plan_id,
                    revision=action.revision,
                    ref=fallback,
                    planned=action.planned,
                    action=action.planned.lateness.fallback,
                    timing=Asap(),
                    principal=action.principal,
                    waits_for=[],
                    order=action.order,
                    due=self.now,
                )
            )
        if on_late == OnLate.CRITICAL:
            self._failed_hard.add(action.key)
        self._end(action, OutcomeStatus.MISSED, reason="late", fallback=fallback)
        if on_late == OnLate.ABORT_PLAN:
            for other in [a for a in self._in_order() if a.plan_id == action.plan_id]:
                if self._withdraw(other):
                    self._end(other, OutcomeStatus.CANCELLED, reason="its plan was aborted")

    def _time_out(self) -> None:
        for action in self._in_order():
            if not self._active(action) or action.starts_at is None or action.assignment_id is None:
                continue
            longest = timedelta(seconds=self._executor.longest_duration_s(action.action.kind))
            if self.now < action.starts_at + longest or action.state not in {
                ActionStateKind.ASSIGNED,
                ActionStateKind.STARTED,
            }:
                continue
            if self._executor.status(action.assignment_id) in {
                AssignmentStatus.UNKNOWN,
                AssignmentStatus.STARTED,
                AssignmentStatus.FINISHED,
            }:
                self._end(action, OutcomeStatus.UNCONFIRMED, reason="its executor never reported")

    def _state(self, action: _Action) -> ActionState:
        return ActionState(
            plan_id=action.plan_id,
            revision=action.revision,
            ref=action.ref,
            action=action.action,
            timing=action.timing,
            due=action.due if not isinstance(action.timing, Window) else action.timing,
            principal=action.principal,
            state=action.state,
            waiting_for=tuple(
                self._actions[key].ref for key in action.waits_for if key in self._actions
            ),
            waited_on_by=tuple(a.ref for a in self._in_order() if action.key in a.waits_for),
            carried_from=action.carried_from,
        )

    def _end(
        self,
        action: _Action,
        status: OutcomeStatus,
        *,
        reason: str | None = None,
        cancelled_by: Principal | None = None,
        report: ExecutionReport | None = None,
        fallback: ActionRef | None = None,
    ) -> None:
        self._made += 1
        ran = report is not None and report.started_at is not None
        due: datetime | Window | None = action.due
        if isinstance(action.timing, Window):
            due = action.timing
        outcome = ActionOutcome(
            outcome_id=f"e{self.epoch}-o{self._made}",
            greenhouse_id=self.greenhouse_id,
            run_id=self.run_id,
            epoch=self.epoch,
            plan_id=action.plan_id,
            revision=action.revision,
            ref=action.ref,
            action=action.action,
            timing=action.timing,
            principal=action.principal,
            status=status,
            due=due,
            started_at=report.started_at if ran and report else None,
            finished_at=report.finished_at if ran and report else None,
            resolved_at=self.now,
            executor=self._executor_ref if ran or status == OutcomeStatus.UNCONFIRMED else None,
            reason=reason,
            cancelled_by=cancelled_by,
            fallback=fallback,
            effect=report.effect
            if report and status in {OutcomeStatus.EXECUTED, OutcomeStatus.LATE}
            else None,
        )
        self._log.append(outcome)
        if action.current:
            self._resolved[action.key] = outcome
        slot = action.slot or action.key
        if self._actions.get(slot) is action:
            del self._actions[slot]


def _due(timing: Timing) -> datetime | None:
    match timing:
        case At(at=at):
            return at
        case Window(not_before=not_before):
            return not_before
        case Asap():
            return None


def _deadline(action: _Action) -> datetime | None:
    """When the action may start at the latest, before it is late."""
    tolerance = timedelta(seconds=action.planned.lateness.tolerance_s)
    match action.timing:
        case At(at=at):
            return at + tolerance
        case Window(not_after=not_after):
            return not_after + tolerance
        case Asap(deadline=deadline):
            return None if deadline is None else deadline + tolerance


def _acts_on_any(action: Action, targets: ActionTargets) -> bool:
    acted_on = targets_of(action)
    return bool(
        acted_on.devices & targets.devices
        or acted_on.plants & targets.plants
        or acted_on.targets & targets.targets
    )


def _names(permitted: ExecutorRef, executor: ExecutorRef) -> bool:
    """Whether `permitted`, from an action's `executed_by`, names
    `executor`: its kind, and its id or any of the kind."""
    return permitted.kind == executor.kind and permitted.id in {None, executor.id}
