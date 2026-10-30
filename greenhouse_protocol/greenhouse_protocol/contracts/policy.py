"""A policy's port: what a control policy reads of a run, and gives it, as
its own principal, and nothing else (decision 0061).

A port is opened for one principal. In the simulator's process, whoever
opens it names the principal; over the network, the credential its
requests carry does. No call names one: every plan goes to the run's
gateway (`greenhouse_protocol.contracts.gateway`) as the port's principal,
and the gateway's grants decide the rest.

A policy reads only what an observation process makes, and what it may
know of its greenhouse:

- **its context** (`greenhouse_protocol.context`), built for its principal
  in the run's epoch, and **its budget** (`greenhouse_protocol.budget`);
- **the observations** as they were delivered, noisy, late and clipped, of
  the types the context's sources observe;
- **the events,** each with only the parameters its type lets a policy
  read;
- **the outcomes** of the actions of the plans it owns, and **those
  plans;**
- **the forecasts** of its budget's providers, each no earlier than it was
  issued.

Never the simulated world's truth, its state, its future, or another
principal's plans and outcomes. What it may read of each record is an
allowlist, field by field (`READABLE_FIELDS`, `READABLE_EVENT_PARAMETERS`),
which `check_readable` holds a port's records to.

## Its logs and cursors

A port keeps four logs, its observations, events, outcomes and forecasts,
each with the consumer interface's rules
(`greenhouse_protocol.contracts.consumer`): in delivery order, positions
dense, appended and never rewritten, nothing delivered after the clock, a
cursor counted in one epoch. A port's logs are its own: each holds what
its principal may read, so its positions are not the run's, and its
cursors are not shared with the consumer interface's.

## Routes

A port is served by a server of its own, apart from the local API, for one
run. Every route lives under `/policy/v1`, the `POLICY_INTERFACE_VERSION`:

    GET  /policy/v1/run                                     -> RunDescriptor
    GET  /policy/v1/context                                 -> CapabilityContext
    GET  /policy/v1/budget                                  -> InformationBudget
    GET  /policy/v1/observations?after=&limit=              -> ObservationBatch
    GET  /policy/v1/events?after=&limit=                    -> EventBatch
    GET  /policy/v1/outcomes?after=&limit=                  -> OutcomeBatch
    GET  /policy/v1/forecasts?after=&limit=                 -> ForecastBatch
    GET  /policy/v1/plans/{plan_id}                         -> PlanState
    POST /policy/v1/plans                    a plan, or a revision -> Receipt
    POST /policy/v1/plans/{plan_id}/cancel?revision=&epoch=        -> Receipt
    POST /policy/v1/actions/cancel           chosen actions, by key -> Receipt

Every request carries a bearer token, whose principal the server knows; one
without a token it knows is `401`. A plan the principal does not own is
`404`, as one that does not exist. The rest is as the gateway's routes
answer it.

## A policy, stepped

An experiment's runner steps a policy in the process (`Policy`): it
starts it with its context and budget, gives it, at each decision, what
reached its port since the last (`Delivery`), and turns its `Decision`
into its plan's next revision, which it gives through the port. The runner
owns the cursors, the epoch, the plan's id and revisions, the receipts,
retries and stopping; the policy owns its memory, started and reset with
each episode. Over the network, a policy uses the port's calls directly.

`check_policy_port` holds a port to this contract, through a harness that
moves its run's clock, delivers records to its run, and opens a port for
another principal.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Annotated, Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from greenhouse_protocol.actions import ActionKind, ActionRef, Identifier, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
    RunDescriptor,
    check_polls,
    check_run,
)
from greenhouse_protocol.contracts.gateway import OPERATOR, PlanState, Receipt
from greenhouse_protocol.enums import EventSource, EventType, ObservationType, SourceType
from greenhouse_protocol.event import Event
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import ActionKey, At, Plan, PlannedAction, Principal, PrincipalKind
from greenhouse_protocol.provenance import RecordSource

type Name = Annotated[str, StringConstraints(min_length=1)]

POLICY_INTERFACE_VERSION: Final = "v1"
POLICY_PREFIX: Final = f"/policy/{POLICY_INTERFACE_VERSION}"

# What a policy may read of each record its port gives, field by field. A
# field one of them gains is a decision: the protocol's tests fail until
# it is named here, and until then a port gives it only at its default.
READABLE_FIELDS: Final[Mapping[type[BaseModel], frozenset[str]]] = MappingProxyType(
    {
        Observation: frozenset(
            {
                "observation_id",
                "greenhouse_id",
                "compartment_id",
                "plant_id",
                "timestamp",
                "observation_type",
                "value",
                "source",
                "sensor_id",
                "delivered_at",
                "quality",
            }
        ),
        Event: frozenset(
            {
                "event_id",
                "greenhouse_id",
                "compartment_id",
                "plant_id",
                "timestamp",
                "event_type",
                "source",
                "confidence",
                "parameters",
            }
        ),
        ActionOutcome: frozenset(
            {
                "outcome_id",
                "greenhouse_id",
                "run_id",
                "epoch",
                "plan_id",
                "revision",
                "ref",
                "action",
                "timing",
                "principal",
                "status",
                "due",
                "started_at",
                "finished_at",
                "resolved_at",
                "delivered_at",
                "executor",
                "reason",
                "cancelled_by",
                "fallback",
                "effect",
                "event_id",
            }
        ),
        Forecast: frozenset(
            {
                "forecast_id",
                "greenhouse_id",
                "compartment_id",
                "provider_id",
                "provider_version",
                "issued_at",
                "valid_from",
                "valid_until",
                "quantity",
                "value",
                "standard_deviation",
            }
        ),
        PlanState: frozenset(
            {"plan", "owner", "sequence", "unresolved", "outcomes", "authorisation"}
        ),
        CapabilityContext: frozenset(
            {
                "context_version",
                "run_id",
                "epoch",
                "greenhouse_id",
                "principal",
                "sources",
                "devices",
                "targets",
                "crops",
                "cadences",
                "limits",
                "grants",
                "goals",
            }
        ),
    }
)
# Of an event's parameters, those a policy may read, by the event's type:
# the crop work's and the crew's. Every other parameter is dropped, and
# every parameter of a type not named here.
READABLE_EVENT_PARAMETERS: Final[Mapping[EventType, frozenset[str]]] = MappingProxyType(
    {
        EventType.HARVEST: frozenset({"harvested_mass_g", "harvested_fruit_count", "action"}),
        EventType.LOWERING: frozenset({"amount_cm", "action"}),
        EventType.PRUNING: frozenset({"leaf_id", "action"}),
        EventType.MANUAL_INSPECTION: frozenset({"reason", "action"}),
    }
)

type PolicyRecord = Observation | Event | ActionOutcome | Forecast | PlanState | CapabilityContext


def readable_event(event: Event) -> Event:
    """The event with only the parameters a policy may read of its type."""
    allowed = READABLE_EVENT_PARAMETERS.get(event.event_type, frozenset())
    kept = {name: value for name, value in event.parameters.items() if name in allowed}
    if kept == event.parameters:
        return event
    return event.model_copy(update={"parameters": kept})


def readable_forecast(forecast: Forecast, budget: InformationBudget) -> bool:
    """Whether a policy given `budget` reads `forecast`: one of its
    providers', at its version, of a quantity it forecasts."""
    provider = budget.provider(forecast.provider_id)
    return (
        provider is not None
        and provider.version == forecast.provider_version
        and forecast.quantity in provider.quantities
    )


def check_readable(
    records: Iterable[PolicyRecord], *, context: CapabilityContext, budget: InformationBudget
) -> list[str]:
    """What a port may give the principal `context` is for, record by
    record: no field the allowlist does not name, unless at its default;
    an event's parameters its type allows; observations of the types the
    context's sources observe; forecasts its budget's providers make; and
    its own plans and context. Whose plan an outcome's is, the port's
    gateway knows, and `check_policy_port` checks."""
    observed = context.observed_types()
    violations: list[str] = []
    for record in records:
        label = _describe(record)
        violations += [
            f"{label} gives {name}, which a policy does not read" for name in _withheld(record)
        ]
        match record:
            case Observation(observation_type=kind) if kind not in observed:
                violations.append(
                    f"{label} is of {kind}, which none of the context's sources observe"
                )
            case Event(event_type=kind, parameters=parameters):
                unread = set(parameters) - READABLE_EVENT_PARAMETERS.get(kind, frozenset())
                if unread:
                    violations.append(
                        f"{label} gives {sorted(unread)}, which a policy does not read of {kind}"
                    )
            case Forecast() if not readable_forecast(record, budget):
                violations.append(f"{label} is not of a provider and quantity its budget names")
            case PlanState(owner=owner) | CapabilityContext(principal=owner) if (
                owner != context.principal
            ):
                violations.append(f"{label} is {owner.id}'s, not {context.principal.id}'s")
    return violations


def _withheld(record: BaseModel) -> list[str]:
    """The fields of `record` the allowlist does not name, given at other
    than their default."""
    readable = READABLE_FIELDS[type(record)]
    return [
        name
        for name, field in type(record).model_fields.items()
        if name not in readable
        and getattr(record, name) != field.get_default(call_default_factory=True, validated_data={})
    ]


def _describe(record: PolicyRecord) -> str:
    match record:
        case Observation(observation_id=identity):
            return f"observation {identity!r}"
        case Event(event_id=identity):
            return f"event {identity!r}"
        case ActionOutcome(outcome_id=identity):
            return f"outcome {identity!r}"
        case Forecast(forecast_id=identity):
            return f"forecast {identity!r}"
        case PlanState(plan=plan):
            return f"plan {plan.plan_id!r}"
        case CapabilityContext(run_id=run_id, epoch=epoch):
            return f"the context of run {run_id!r} epoch {epoch}"


class PolicyIdentity(BaseModel):
    """A policy, as an experiment names it: its name and its version."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: Identifier
    version: Name


class Delivery(BaseModel):
    """What reached a policy's port since its last decision: each log's new
    records, in delivery order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observations: tuple[Observation, ...] = ()
    events: tuple[Event, ...] = ()
    outcomes: tuple[ActionOutcome, ...] = ()
    forecasts: tuple[Forecast, ...] = ()


class Keep(BaseModel):
    """The plan in force, kept as it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["keep"] = "keep"


class Revise(BaseModel):
    """The actions of the policy's plan's next revision, which the runner
    makes and gives: from then on they replace those of the revision in
    force not yet started, as the gateway's rule has it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    kind: Literal["revise"] = "revise"
    actions: tuple[PlannedAction, ...]


class CancelPlan(BaseModel):
    """The plan in force cancelled, what of it has not started."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["cancel_plan"] = "cancel_plan"


type Decision = Annotated[Keep | Revise | CancelPlan, Field(discriminator="kind")]


class Policy(Protocol):
    """A control policy, as an experiment's runner steps it in the
    process."""

    @property
    def identity(self) -> PolicyIdentity: ...

    @property
    def decide_every_s(self) -> float:
        """How often it decides, in seconds of the run's clock."""
        ...

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        """An episode starts: nothing of an earlier one is remembered."""
        ...

    def decide(self, at: datetime, delivered: Delivery) -> Decision: ...

    def stop(self) -> None: ...


class PolicyPort(Protocol):
    """A run, as a policy reaches it, as the port's principal: see the
    module."""

    def run(self) -> RunDescriptor: ...

    def context(self) -> CapabilityContext: ...

    def budget(self) -> InformationBudget: ...

    def observations(self, after: int = 0, limit: int | None = None) -> ObservationBatch: ...

    def events(self, after: int = 0, limit: int | None = None) -> EventBatch: ...

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch: ...

    def forecasts(self, after: int = 0, limit: int | None = None) -> ForecastBatch: ...

    def plan(self, plan_id: str) -> PlanState | None:
        """The plan in force, if the port's principal owns it; None if it
        does not, as for a plan that does not exist."""
        ...

    def submit(self, plan: Plan) -> Receipt: ...

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int) -> Receipt: ...

    def cancel(self, keys: Sequence[ActionKey]) -> Receipt: ...


type Delivered = Observation | Event | Forecast


class PortUnderTest(PolicyPort, Protocol):
    """A port, with what a test needs to move its run: its clock, the
    records its producer delivers, and a port on the same run for another
    principal."""

    def advance(self, to: datetime) -> None: ...

    def deliver(self, records: Sequence[Delivered]) -> None:
        """Records the run's producer delivers, each at its delivery: by the
        clock, now, and the others as the clock reaches them, as the run
        takes them, whatever its ports let through."""
        ...

    def open(self, principal: Principal) -> PolicyPort: ...


# The policies `check_policy_port` opens ports for: the one under test, and
# another, on the same run, whose plans are not its.
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="policy")
RIVAL: Final = Principal(kind=PrincipalKind.POLICY, id="rival")
HOUR: Final = timedelta(hours=1)
# The identities the check's own records and plans take, so that what a
# live run delivers beside them is told apart.
CHECK: Final = "conformance"
# What the check's harvest weighed, and its watering gave.
HARVESTED_G: Final = 50.0
WATERED_ML: Final = 100.0


def conformance_policy_authorisation() -> AuthorisationConfig:
    """The authorisation `check_policy_port` runs a port's run under: the
    operator may do anything, and each policy may set a device's level as
    itself."""
    return AuthorisationConfig(
        version=1,
        groups=(
            AuthorisationGroup(
                group_id="operators",
                principals=frozenset({OPERATOR}),
                grants=(Grant(kinds=frozenset(ActionKind)),),
            ),
            AuthorisationGroup(
                group_id="policies",
                principals=frozenset({POLICY, RIVAL}),
                grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
            ),
        ),
    )


type MakePort = Callable[[AuthorisationConfig, datetime], PortUnderTest]


def check_policy_port(make: MakePort, start: datetime) -> list[str]:
    """Holds a port to this module's rules, scenario by scenario, each on a
    port `make` opens for `POLICY` on a run starting at `start`, under
    `conformance_policy_authorisation()`. The run has a device to set.
    Returns the violations, empty when it conforms."""
    violations: list[str] = []
    for scenario in _SCENARIOS:
        name = scenario.__name__.removeprefix("_")
        try:
            violations += [
                f"{name}: {v}" for v in scenario(make(conformance_policy_authorisation(), start))
            ]
        except Exception as error:  # a scenario that breaks is a violation, not a crash
            violations.append(f"{name}: raised {error!r}")
    return violations


def _now(port: PolicyPort) -> datetime:
    return port.run().clock.simulated_now


def _plan(port: PolicyPort, plan_id: str, *actions: PlannedAction, revision: int = 1) -> Plan:
    run = port.run()
    return Plan(
        plan_id=f"{CHECK}-{plan_id}",
        run_id=run.run_id,
        epoch=run.epoch,
        revision=revision,
        actions=actions,
    )


def _level(
    port: PolicyPort, action_id: str, at: datetime, proposed_by: Principal = POLICY
) -> PlannedAction:
    device = min(device.device_id for device in port.context().devices)
    return PlannedAction(
        action_id=action_id,
        action=SetLevel(device_id=device, level=1.0),
        timing=At(at=at),
        proposed_by=proposed_by,
    )


def _own[RecordT: (Observation, Event, Forecast)](records: Iterable[RecordT]) -> list[RecordT]:
    """The check's own records, among what a live run delivers beside
    them."""
    return [record for record in records if _identity(record).startswith(CHECK)]


def _own_ends(outcomes: Iterable[ActionOutcome]) -> list[ActionOutcome]:
    """The outcomes of the check's own plans."""
    return [outcome for outcome in outcomes if outcome.plan_id.startswith(CHECK)]


def _identity(record: Observation | Event | Forecast) -> str:
    match record:
        case Observation(observation_id=identity):
            return identity
        case Event(event_id=identity):
            return identity
        case Forecast(forecast_id=identity):
            return identity


def _reading(
    port: PolicyPort,
    name: str,
    kind: ObservationType,
    at: datetime,
    delivered_at: datetime | None = None,
) -> Observation:
    run = port.run()
    return Observation(
        observation_id=f"{CHECK}-{name}",
        greenhouse_id=run.greenhouse_id,
        plant_id=None,
        timestamp=at,
        observation_type=kind,
        value=1.0,
        source=RecordSource(type=SourceType.SIMULATION, source_id=run.run_id),
        delivered_at=delivered_at,
    )


def _event(port: PolicyPort, name: str, kind: EventType, parameters: dict[str, object]) -> Event:
    return Event(
        event_id=f"{CHECK}-{name}",
        greenhouse_id=port.run().greenhouse_id,
        plant_id=None,
        timestamp=_now(port),
        event_type=kind,
        source=EventSource.SIMULATION,
        parameters=parameters,
    )


def _forecast(
    port: PolicyPort,
    name: str,
    provider: tuple[str, str],
    quantity: ObservationType,
    issued_at: datetime,
) -> Forecast:
    return Forecast(
        forecast_id=f"{CHECK}-{name}",
        greenhouse_id=port.run().greenhouse_id,
        provider_id=provider[0],
        provider_version=provider[1],
        issued_at=issued_at,
        valid_from=issued_at + HOUR,
        valid_until=issued_at + HOUR,
        quantity=quantity,
        value=1.0,
    )


def _ids[RecordT: (Observation, Event, Forecast)](records: Iterable[RecordT]) -> list[str]:
    return [_identity(record) for record in _own(records)]


def _drained[BatchT: (ObservationBatch, EventBatch, OutcomeBatch, ForecastBatch)](
    read: Callable[[int], BatchT], after: int = 0
) -> list[BatchT]:
    """Every batch from `after` on, polled again at once while the port
    says it cut one short, as a client does."""
    batches = [read(after)]
    while batches[-1].has_more and batches[-1].next > batches[-1].after:
        batches.append(read(batches[-1].next))
    return batches


def _outcomes(port: PolicyPort) -> list[ActionOutcome]:
    return [outcome for batch in _drained(port.outcomes) for outcome in batch.outcomes]


def _describes_its_run(port: PortUnderTest) -> list[str]:
    run = port.run()
    violations = check_run(run)
    context = port.context()
    if (context.run_id, context.epoch, context.greenhouse_id) != (
        run.run_id,
        run.epoch,
        run.greenhouse_id,
    ):
        violations.append(
            f"the context is of run {context.run_id!r} epoch {context.epoch}, "
            f"not of the port's, {run.run_id!r} epoch {run.epoch}"
        )
    if context.principal != POLICY:
        violations.append(f"the context is for {context.principal.id}, not the port's principal")
    granted = conformance_policy_authorisation().grants_of(POLICY)
    if set(context.grants) != set(granted):
        violations.append(f"the context's grants are not its principal's: {context.grants}")
    violations += check_readable([context], context=context, budget=port.budget())
    return violations


def _observations_as_delivered(port: PortUnderTest) -> list[str]:
    violations = []
    context = port.context()
    now = _now(port)
    observed = context.observed_types()
    unobserved = next(kind for kind in ObservationType if kind not in observed)
    records = [_reading(port, "unobserved", unobserved, now)]
    expected: tuple[list[str], list[str]] = ([], [])
    if observed:
        kind = min(observed)
        records += [
            _reading(port, "read", kind, now),
            _reading(port, "late", kind, now, delivered_at=now + HOUR),
        ]
        expected = ([f"{CHECK}-read"], [f"{CHECK}-late"])
    port.deliver(records)
    first = _drained(port.observations)
    port.advance(now + HOUR)
    second = _drained(port.observations, first[-1].next)
    for batches, wanted in zip((first, second), expected, strict=True):
        given = _ids(o for batch in batches for o in batch.observations)
        if given != wanted:
            violations.append(
                f"by {batches[-1].simulated_now.isoformat()} it gave {given}, not {wanted}: "
                "the readings of the context's types, each once it was delivered"
            )
    violations += check_polls([*first, *second], greenhouse_id=port.run().greenhouse_id)
    violations += check_readable(
        [o for batch in (*first, *second) for o in batch.observations],
        context=context,
        budget=port.budget(),
    )
    return violations


def _events_as_allowed(port: PortUnderTest) -> list[str]:
    violations = []
    picked: dict[str, object] = {
        "harvested_mass_g": HARVESTED_G,
        "harvested_fruit_count": 1,
        "action": "pick",
    }
    harvest = _event(
        port, "harvest", EventType.HARVEST, picked | {"unnamed": "a parameter no type names"}
    )
    watering = _event(port, "watering", EventType.WATERING, {"amount_ml": WATERED_ML})
    port.deliver([harvest, watering])
    batches = _drained(port.events)
    events = [event for batch in batches for event in batch.events]
    given = {event.event_id: event.parameters for event in _own(events)}
    wanted = {harvest.event_id: picked, watering.event_id: {}}
    if given != wanted:
        violations.append(
            f"it gave the events' parameters {given}, not those their types allow {wanted}"
        )
    violations += check_polls(batches, greenhouse_id=port.run().greenhouse_id)
    violations += check_readable(events, context=port.context(), budget=port.budget())
    return violations


def _forecasts_of_its_budget(port: PortUnderTest) -> list[str]:
    violations = []
    budget = port.budget()
    now = _now(port)
    unknown = (f"{CHECK}-unknown", "0")
    records = [_forecast(port, "unknown", unknown, ObservationType.OUTSIDE_AIR_TEMPERATURE_C, now)]
    wanted: list[str] = []
    if budget.forecasts:
        provider = budget.forecasts[0]
        named = (provider.provider_id, provider.version)
        unforecast = next(kind for kind in ObservationType if kind not in provider.quantities)
        records += [
            _forecast(port, "later", named, min(provider.quantities), now + HOUR),
            _forecast(port, "unforecast", named, unforecast, now),
        ]
        wanted = [f"{CHECK}-later"]
    port.deliver(records)
    first = _drained(port.forecasts)
    before = _ids(f for batch in first for f in batch.forecasts)
    if before:
        violations.append(
            f"it gave {before}: forecasts its budget does not name, or before they were issued"
        )
    port.advance(now + HOUR)
    second = _drained(port.forecasts, first[-1].next)
    issued = _ids(f for batch in second for f in batch.forecasts)
    if issued != wanted:
        violations.append(
            f"once it was issued, it gave {issued}, not {wanted}: "
            "its budget's provider's forecast of a quantity it forecasts"
        )
    violations += check_polls([*first, *second], greenhouse_id=port.run().greenhouse_id)
    violations += check_readable(
        [f for batch in (*first, *second) for f in batch.forecasts],
        context=port.context(),
        budget=budget,
    )
    return violations


def _plans_as_its_principal(port: PortUnderTest) -> list[str]:
    violations = []
    now = _now(port)
    receipt = port.submit(_plan(port, "mine", _level(port, "level", now + HOUR)))
    if not receipt.accepted:
        violations.append(f"a plan of its own, as its grants allow, was refused: {receipt.errors}")
    state = port.plan(f"{CHECK}-mine")
    if state is None or state.owner != POLICY:
        violations.append(f"its own plan is not given as its principal's: {state}")
    for_another = port.submit(
        _plan(port, "for-another", _level(port, "level", now + HOUR, proposed_by=OPERATOR))
    )
    if for_another.accepted:
        violations.append(
            "a plan proposed for the operator, which its grants do not allow, was accepted"
        )
    port.advance(now + 2 * HOUR)
    batches = _drained(port.outcomes)
    outcomes = [outcome for batch in batches for outcome in batch.outcomes]
    ends = [(o.plan_id, str(o.ref)) for o in _own_ends(outcomes)]
    if ends != [(f"{CHECK}-mine", "level")]:
        violations.append(f"its own action's outcome was not given once: {ends}")
    violations += check_polls(batches, greenhouse_id=port.run().greenhouse_id)
    return violations


def _others_plans_unseen(port: PortUnderTest) -> list[str]:
    violations = []
    now = _now(port)
    rival = port.open(RIVAL)
    if rival.context().principal != RIVAL:
        violations.append("a port opened for another principal gives a context not its own")
    theirs = rival.submit(_plan(rival, "theirs", _level(rival, "level", now + HOUR, RIVAL)))
    if not theirs.accepted:
        violations.append(f"another policy's plan of its own was refused: {theirs.errors}")
    if port.plan(f"{CHECK}-theirs") is not None:
        violations.append("it gave another principal's plan")
    revised = port.submit(_plan(port, "theirs", _level(port, "level", now + HOUR), revision=2))
    if revised.accepted:
        violations.append("it revised another principal's plan")
    port.advance(now + 2 * HOUR)
    if any(o.plan_id == f"{CHECK}-theirs" for o in _outcomes(port)):
        violations.append("it gave the outcome of another principal's action")
    if not any(o.plan_id == f"{CHECK}-theirs" for o in _outcomes(rival)):
        violations.append("another principal's port did not give its own action's outcome")
    return violations


def _a_revision_given_twice(port: PortUnderTest) -> list[str]:
    violations = []
    now = _now(port)
    plan = _plan(port, "steer", _level(port, "level", now + HOUR))
    port.submit(plan)
    again = port.submit(plan)
    if again.accepted:
        violations.append("a revision given twice was accepted twice")
    state = port.plan(plan.plan_id)
    if state is None or state.plan.revision != 1:
        violations.append(f"the plan in force is not the revision given: {state}")
    following = port.submit(_plan(port, "steer", _level(port, "level", now + HOUR), revision=2))
    if not following.accepted:
        violations.append(f"the next revision was refused: {following.errors}")
    return violations


def _cancelled_as_its_principal(port: PortUnderTest) -> list[str]:
    violations = []
    now = _now(port)
    epoch = port.run().epoch
    port.submit(_plan(port, "later", _level(port, "level", now + 2 * HOUR)))
    port.submit(_plan(port, "chosen", _level(port, "level", now + 2 * HOUR)))
    if port.open(RIVAL).cancel_plan(f"{CHECK}-later", revision=1, epoch=epoch).accepted:
        violations.append("another principal cancelled its plan")
    whole = port.cancel_plan(f"{CHECK}-later", revision=1, epoch=epoch)
    chosen = port.cancel(
        [
            ActionKey(
                plan_id=f"{CHECK}-chosen", epoch=epoch, revision=1, ref=ActionRef(action_id="level")
            )
        ]
    )
    violations += [
        f"its own action was not cancelled: {receipt}"
        for receipt in (whole, chosen)
        if not receipt.accepted or [ref.action_id for ref in receipt.cancelled] != ["level"]
    ]
    ends = [(o.plan_id, o.status, o.cancelled_by) for o in _own_ends(_outcomes(port))]
    wanted = [
        (f"{CHECK}-later", OutcomeStatus.CANCELLED, POLICY),
        (f"{CHECK}-chosen", OutcomeStatus.CANCELLED, POLICY),
    ]
    if ends != wanted:
        violations.append(f"its cancelled actions' outcomes do not say it cancelled them: {ends}")
    return violations


_SCENARIOS: Final = (
    _describes_its_run,
    _observations_as_delivered,
    _events_as_allowed,
    _forecasts_of_its_budget,
    _plans_as_its_principal,
    _others_plans_unseen,
    _a_revision_given_twice,
    _cancelled_as_its_principal,
)
