"""A run's gateway: its local endpoint, which holds its plan and decides
(decision 0046).

A gateway holds the run's plan and its revisions, schedules the actions,
applies the lateness rules, authorises, and writes the outcome log. It
serves the run's read side, the consumer interface with outcomes beside
observations and events (`greenhouse_protocol.contracts.consumer`), and the
actions not yet resolved as they stand; and its write side, plans given and
revised, and actions cancelled. Executors behind it carry actions out
(`greenhouse_protocol.contracts.execution`). The simulator ships a gateway
in process; a physical site runs one of its own, through the same
contracts.

## Routes

The write side and the actions as they stand, under `/actuation/v1`:

    POST /actuation/v1/runs/{run_id}/plans                    a plan, or a revision -> Receipt
    POST /actuation/v1/runs/{run_id}/plans/{plan_id}/cancel   a whole plan          -> Receipt
    GET  /actuation/v1/runs/{run_id}/plans/{plan_id}?revision=                      -> PlanState
    GET  /actuation/v1/runs/{run_id}/actions?state=&kind=&target=&plan=     -> ActionState list
    POST /actuation/v1/runs/{run_id}/actions/cancel           chosen actions, by key -> Receipt

The caller's principal is the one the channel or the API authenticated,
never one a document names.

## The rules a gateway keeps

- **A malformed or stale request is refused whole,** by its receipt, and
  writes no outcome: a plan given for an epoch that has ended, a revision
  no newer than the one in force, a plan beyond the gateway's limits, an
  action proposed for a principal the submitter may not propose for, a
  revision by a principal that neither owns the plan nor may manage plans.
  A manager's revision keeps the owner's actions it leaves unchanged.
- **Each well-formed action that cannot be carried out is refused at once,**
  as an outcome: one its principal may not carry out, of a kind no
  executor carries out, on a device, plant or target the run does not
  have, at an instant no executor honours; with the executor's own words
  for why, when it gives them (`ExplainsRefusals`).
- **Authorisation is checked again** when an assignment is sent and when it
  falls due; a refusal after it was sent revokes it.
- **An action starts at the earliest instant it can,** from when it falls
  due: one its executor honours, as the executor says when it does
  (`SaysWhen`), and at which one of its hands is free (`capacity`). Each
  assignment holds a hand from its start for as long as its kind takes at
  the longest. A window's action starts within its window, and an as soon
  as possible one once what it waits for is done. It is sent no earlier
  than its executor's lead time before its start, which is reserved
  meanwhile, holding its hand. A window its executor honours no instant
  in, or an as soon as possible action it honours none for from then on,
  is refused at once. One already past is late, by its rule.
- **An action that cannot start by its deadline is late:** its instant,
  its window's end or its own deadline, with its tolerance. The gateway
  decides that at the deadline, by the action's `on_late`. One run late
  starts at the next instant it can, and is missed if there is none.
- **A revision steers from then on:** the actions of the one before not
  yet started are superseded unless it keeps them unchanged; what started
  keeps its outcome.
- **Cancelling** is authorised as every write is, the plan's owner's or a
  manager's; a key from a replaced revision or an ended epoch is stale.
  Each cancelled action is an outcome naming who cancelled it, and what
  waits for it is cancelled unless its plan says `proceed`.
- **One order at one instant:** a prerequisite before what waits for it,
  then recurring actions, then the order the gateway accepted revisions
  in, then place in the plan.
- **A run that continues the clock** (its descriptor's `continues_from`)
  carries the actions not yet resolved, checked again, assignments kept; one
  that starts its clock over cancels them, the run having started over, as
  the first outcomes of its new epoch, where a consumer reads them; one
  that ends for good cancels them. A finished or recorded run refuses a plan
  with `ActionNotExecutable`.
- **Every action, occurrence and fallback ends in exactly one outcome,** in
  a log with the consumer interface's rules (`check_polls`).

`check_gateway` holds a gateway to these, through a harness that moves its
clock and restarts it.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Annotated, Final, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from greenhouse_protocol.actions import (
    ActionKind,
    ActionRef,
    ActionTargets,
    Identifier,
    Inspect,
    SetLevel,
)
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.contracts.consumer import OutcomeBatch, RunDescriptor, check_polls
from greenhouse_protocol.contracts.execution import ActionNotExecutable
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import (
    ActionKey,
    ActionState,
    ActionStateKind,
    Asap,
    At,
    Plan,
    PlannedAction,
    Principal,
    PrincipalKind,
    Recurrence,
)
from greenhouse_protocol.run import RunEpoch

ACTUATION_PREFIX: Final = "/actuation/v1"


class GatewayLimits(BaseModel):
    """How much one plan may hold: actions, and their occurrences expanded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_actions: Annotated[int, Field(ge=1)]
    max_occurrences: Annotated[int, Field(ge=1)]


def occurrences(planned: PlannedAction) -> int:
    """How many occurrences a planned action has: one, its recurrence's
    count, or as many as fit before its recurrence's end."""
    every = planned.every
    if every is None:
        return 1
    if every.count is not None:
        return every.count
    anchor = planned.anchor()
    assert anchor is not None and every.until is not None  # the plan checked both
    return (every.until - anchor) // every.period + 1


def check_limits(plan: Plan, limits: GatewayLimits) -> list[str]:
    """What makes a plan too large for a gateway, empty if it fits."""
    violations = []
    if len(plan.actions) > limits.max_actions:
        violations.append(
            f"plan {plan.plan_id!r} has {len(plan.actions)} actions, more than {limits.max_actions}"
        )
    expanded = sum(occurrences(planned) for planned in plan.actions)
    if expanded > limits.max_occurrences:
        violations.append(
            f"plan {plan.plan_id!r} has {expanded} occurrences, more than {limits.max_occurrences}"
        )
    return violations


class Receipt(BaseModel):
    """A gateway's answer to a write. A request refused whole has its
    errors and changed nothing; one accepted lists what it refused at once,
    what it cancelled, and the keys it would not act on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted: bool
    plan_id: Identifier | None = None
    revision: Annotated[int, Field(ge=1)] | None = None
    # The gateway's sequence number for an accepted revision, which orders
    # actions of different plans at one instant.
    sequence: Annotated[int, Field(ge=1)] | None = None
    errors: tuple[str, ...] = ()
    refused: tuple[ActionRef, ...] = ()
    cancelled: tuple[ActionRef, ...] = ()
    stale: tuple[ActionKey, ...] = ()
    not_permitted: tuple[ActionKey, ...] = ()

    @model_validator(mode="after")
    def _whole_or_listed(self) -> Self:
        if self.accepted == bool(self.errors):
            raise ValueError("a receipt is accepted exactly when it has no errors")
        if self.errors and (self.refused or self.cancelled):
            raise ValueError("a request refused whole refused and cancelled nothing")
        return self


class AuthorisationChange(BaseModel):
    """Which authorisation configuration a gateway put in force, and when."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[int, Field(ge=1)]
    at: Instant


class PlanState(BaseModel):
    """A revision of a plan, as a gateway holds it: its owner, its sequence
    number, what of it is not yet resolved, what is, and the authorisation
    changes the gateway recorded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: Plan
    owner: Principal
    sequence: Annotated[int, Field(ge=1)]
    unresolved: tuple[ActionState, ...]
    outcomes: tuple[ActionOutcome, ...]
    authorisation: tuple[AuthorisationChange, ...]


class RunGateway(Protocol):
    """A run's gateway, as its callers reach it. The rules it keeps are this
    module's; `check_gateway` holds one to them."""

    def run(self) -> RunDescriptor: ...

    def limits(self) -> GatewayLimits: ...

    def submit(self, plan: Plan, *, by: Principal) -> Receipt:
        """A plan, or its next revision, from the next instant its executors
        can honour. Raises `ActionNotExecutable` for a finished or recorded
        run."""
        ...

    def cancel(self, keys: Sequence[ActionKey], *, by: Principal) -> Receipt: ...

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int, by: Principal) -> Receipt: ...

    def actions(
        self,
        *,
        states: frozenset[ActionStateKind] | None = None,
        kinds: frozenset[ActionKind] | None = None,
        targets: ActionTargets | None = None,
        plan_id: str | None = None,
    ) -> Sequence[ActionState]:
        """Every action not yet resolved, as it stands, filtered: by state,
        by kind, by what it acts on (any of the targets named), by plan."""
        ...

    def plan(self, plan_id: str, revision: int | None = None) -> PlanState: ...

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch: ...


class GatewayUnderTest(RunGateway, Protocol):
    """A gateway, with what a test needs to move it: its clock, the
    authorisation it enforces, a restart, an end. `items` is what its run
    has to act on."""

    def items(self) -> ActionTargets: ...

    def advance(self, to: datetime) -> None: ...

    def authorise(self, config: AuthorisationConfig) -> None: ...

    def restart(self, *, continue_clock: bool) -> None: ...

    def finish(self) -> None: ...


# The principals `check_gateway` acts as: one that may do anything, one
# that may only inspect, and one granted to propose for the first.
OPERATOR: Final = Principal(kind=PrincipalKind.PERSON, id="operator")
OBSERVER: Final = Principal(kind=PrincipalKind.PERSON, id="observer")
PLATFORM: Final = Principal(kind=PrincipalKind.PLATFORM, id="platform")
HOUR: Final = timedelta(hours=1)
# When the scenarios' late actions fall due, and when they look again, after
# the run's start.
FAR: Final = 3 * HOUR
AFTERWARDS: Final = 4 * HOUR
STARTED_OVER: Final = "started over"


def conformance_authorisation(
    version: int = 1, *, operator_kinds: frozenset[ActionKind] = frozenset(ActionKind)
) -> AuthorisationConfig:
    """The authorisation `check_gateway` runs a gateway under."""
    return AuthorisationConfig(
        version=version,
        groups=(
            AuthorisationGroup(
                group_id="operators",
                principals=frozenset({OPERATOR}),
                grants=(Grant(kinds=operator_kinds),),
            ),
            AuthorisationGroup(
                group_id="observers",
                principals=frozenset({OBSERVER}),
                grants=(Grant(kinds=frozenset({ActionKind.INSPECT})),),
            ),
            AuthorisationGroup(
                group_id="platforms",
                principals=frozenset({PLATFORM}),
                grants=(Grant(on_behalf_of=frozenset({OPERATOR})),),
            ),
        ),
    )


type MakeGateway = Callable[[AuthorisationConfig, datetime], GatewayUnderTest]


def check_gateway(make: MakeGateway, start: datetime) -> list[str]:
    """Holds a gateway to this module's rules, scenario by scenario, each on
    a gateway `make` gives for a run starting at `start`, under
    `conformance_authorisation()`. Returns the violations, empty when it
    conforms."""
    violations: list[str] = []
    for scenario in _SCENARIOS:
        try:
            violations += [
                f"{scenario.__name__.removeprefix('_')}: {v}"
                for v in scenario(make(conformance_authorisation(), start), start)
            ]
        except Exception as error:  # a scenario that breaks is a violation, not a crash
            violations.append(f"{scenario.__name__.removeprefix('_')}: raised {error!r}")
    return violations


def _plan(
    gateway: GatewayUnderTest, plan_id: str, *actions: PlannedAction, revision: int = 1
) -> Plan:
    run = gateway.run()
    return Plan(
        plan_id=plan_id, run_id=run.run_id, epoch=run.epoch, revision=revision, actions=actions
    )


def _vent(
    gateway: GatewayUnderTest, action_id: str, at: datetime, **fields: object
) -> PlannedAction:
    device = sorted(gateway.items().devices)[0]
    return PlannedAction.model_validate(
        dict(
            action_id=action_id,
            action=SetLevel(device_id=device, level=1.0),
            timing=At(at=at),
            proposed_by=OPERATOR,
        )
        | fields
    )


def _outcomes(gateway: GatewayUnderTest) -> list[ActionOutcome]:
    return list(gateway.outcomes().outcomes)


def _ends(gateway: GatewayUnderTest, action_id: str) -> list[ActionOutcome]:
    return [o for o in _outcomes(gateway) if o.ref.action_id == action_id]


def _carried_out(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    violations = []
    receipt = gateway.submit(
        _plan(gateway, "morning", _vent(gateway, "vent", start + HOUR)), by=OPERATOR
    )
    if not receipt.accepted or receipt.sequence is None:
        violations.append(f"a well-formed plan was not accepted: {receipt.errors}")
    if [s.ref.action_id for s in gateway.actions()] != ["vent"]:
        violations.append("an accepted action is not listed as it stands")
    gateway.advance(start + 2 * HOUR)
    ends = _ends(gateway, "vent")
    if [o.status for o in ends] != [OutcomeStatus.EXECUTED] or ends[0].effect is None:
        violations.append(f"an action due and allowed did not end executed: {ends}")
    if gateway.actions():
        violations.append("a resolved action is still listed")
    run = gateway.run()
    violations += check_polls([gateway.outcomes()], greenhouse_id=run.greenhouse_id)
    return violations


def _refused_whole(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    violations = []
    run = gateway.run()
    cases = {
        "an action proposed for another principal, without delegation": (
            _plan(gateway, "a", _vent(gateway, "vent", start + HOUR, proposed_by=OBSERVER)),
            OPERATOR,
        ),
        "a plan for an epoch that is not the run's": (
            Plan(
                plan_id="b",
                run_id=run.run_id,
                epoch=run.epoch + 1,
                revision=1,
                actions=(_vent(gateway, "vent", start + HOUR),),
            ),
            OPERATOR,
        ),
        "a plan beyond the gateway's limits": (
            _plan(
                gateway,
                "c",
                _vent(
                    gateway,
                    "vent",
                    start + HOUR,
                    every=Recurrence(
                        period=timedelta(seconds=1), count=gateway.limits().max_occurrences + 1
                    ),
                ),
            ),
            OPERATOR,
        ),
    }
    for name, (plan, by) in cases.items():
        receipt = gateway.submit(plan, by=by)
        if receipt.accepted or not receipt.errors:
            violations.append(f"{name} was not refused whole")
    if _outcomes(gateway) or gateway.actions():
        violations.append("a request refused whole left an outcome or an action")
    delegated = gateway.submit(
        _plan(gateway, "d", _vent(gateway, "vent", start + HOUR)), by=PLATFORM
    )
    if not delegated.accepted:
        violations.append(f"a delegated submission was refused: {delegated.errors}")
    return violations


def _ownership(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    gateway.submit(_plan(gateway, "mine", _vent(gateway, "vent", start + HOUR)), by=OPERATOR)
    inspect = PlannedAction(
        action_id="look",
        action=Inspect(plant_id=sorted(gateway.items().plants)[0], reason="a check"),
        timing=At(at=start + HOUR),
        proposed_by=OBSERVER,
    )
    receipt = gateway.submit(_plan(gateway, "mine", inspect, revision=2), by=OBSERVER)
    return (
        []
        if not receipt.accepted
        else ["a revision by a principal that does not own the plan was accepted"]
    )


def _refused_at_once(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    violations = []
    receipt = gateway.submit(
        _plan(gateway, "watch", _vent(gateway, "vent", start + HOUR, proposed_by=OBSERVER)),
        by=OBSERVER,
    )
    if not receipt.accepted or [r.action_id for r in receipt.refused] != ["vent"]:
        violations.append(
            f"an action its principal may not carry out was not refused at once: {receipt}"
        )
    ends = _ends(gateway, "vent")
    if [o.status for o in ends] != [OutcomeStatus.REFUSED]:
        violations.append(f"an action refused at once has no refused outcome: {ends}")
    return violations


def _cancelled(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    violations = []
    first = _vent(gateway, "first", start + HOUR)
    then = _vent(gateway, "then", start + HOUR, timing=Asap(), after=("first",))
    alone = _vent(gateway, "alone", start + 2 * HOUR)
    gateway.submit(_plan(gateway, "work", first, then, alone), by=OPERATOR)
    epoch = gateway.run().epoch
    key = ActionKey(plan_id="work", epoch=epoch, revision=1, ref=ActionRef(action_id="first"))
    stale = ActionKey(plan_id="work", epoch=epoch, revision=2, ref=ActionRef(action_id="alone"))
    refused = gateway.cancel(
        [key.model_copy(update={"ref": ActionRef(action_id="alone")})], by=OBSERVER
    )
    if refused.not_permitted == () or refused.cancelled:
        violations.append("a cancellation by a principal that may not cancel was not refused")
    receipt = gateway.cancel([key, stale], by=OPERATOR)
    if [r.action_id for r in receipt.cancelled] != ["first"] or receipt.stale != (stale,):
        violations.append(
            f"a cancellation did not cancel its key alone, or kept a stale one: {receipt}"
        )
    first_end = _ends(gateway, "first")
    if [(o.status, o.cancelled_by) for o in first_end] != [(OutcomeStatus.CANCELLED, OPERATOR)]:
        violations.append(f"a cancelled action does not say who cancelled it: {first_end}")
    if [o.status for o in _ends(gateway, "then")] != [OutcomeStatus.CANCELLED]:
        violations.append("an action waiting for a cancelled one was not cancelled with it")
    if [s.ref.action_id for s in gateway.actions()] != ["alone"]:
        violations.append("cancelling chosen actions changed others")
    return violations


def _rights_withdrawn(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    gateway.submit(_plan(gateway, "later", _vent(gateway, "vent", start + 2 * HOUR)), by=OPERATOR)
    gateway.advance(start + HOUR)
    gateway.authorise(conformance_authorisation(2, operator_kinds=frozenset({ActionKind.INSPECT})))
    gateway.advance(start + FAR)
    ends = _ends(gateway, "vent")
    # Refused when its assignment was to be sent, or when it fell due: after
    # the withdrawal, and no later than its due instant.
    refused_in_time = len(ends) == 1 and start + HOUR <= ends[0].resolved_at <= start + 2 * HOUR
    if not refused_in_time or ends[0].status != OutcomeStatus.REFUSED:
        return [f"an action whose rights were withdrawn was not refused by its due: {ends}"]
    return []


def _carried(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    violations = []
    gateway.submit(_plan(gateway, "far", _vent(gateway, "vent", start + FAR)), by=OPERATOR)
    gateway.advance(start + HOUR)
    before = gateway.run()
    gateway.restart(continue_clock=True)
    after = gateway.run()
    if after.continues_from != RunEpoch(run_id=before.run_id, epoch=before.epoch):
        violations.append(
            f"a run that continues the clock does not say whose: {after.continues_from}"
        )
    listed = gateway.actions()
    if [(s.ref.action_id, s.carried_from) for s in listed] != [("vent", after.continues_from)]:
        violations.append(f"a pending action was not carried, or not said to be: {listed}")
    gateway.advance(start + AFTERWARDS)
    if [o.status for o in _ends(gateway, "vent")] != [OutcomeStatus.EXECUTED]:
        violations.append("a carried action was not carried out")
    return violations


def _dropped(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    violations = []
    gateway.submit(_plan(gateway, "far", _vent(gateway, "vent", start + FAR)), by=OPERATOR)
    gateway.advance(start + HOUR)
    gateway.restart(continue_clock=False)
    dropped = _ends(gateway, "vent")
    if gateway.run().continues_from is not None:
        violations.append("a run that started over says it continues a clock")
    if gateway.actions():
        violations.append("a run that started over kept pending actions")
    cancelled = [o for o in dropped if o.status == OutcomeStatus.CANCELLED]
    if not cancelled or STARTED_OVER not in (cancelled[0].reason or ""):
        violations.append(
            f"a pending action of a run that started over was not cancelled: {dropped}"
        )
    return violations


def _finished(gateway: GatewayUnderTest, start: datetime) -> list[str]:
    gateway.finish()
    try:
        gateway.submit(_plan(gateway, "late", _vent(gateway, "vent", start + HOUR)), by=OPERATOR)
    except ActionNotExecutable:
        return []
    return ["a finished run accepted a plan"]


_SCENARIOS: Final = (
    _carried_out,
    _refused_whole,
    _ownership,
    _refused_at_once,
    _cancelled,
    _rights_withdrawn,
    _carried,
    _dropped,
    _finished,
)
