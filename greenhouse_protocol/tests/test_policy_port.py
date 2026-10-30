"""A policy's port (decision 0061): its records, its allowlist, and its
contract, held to its conformance check through the in-memory reference;
and the check, shown to find a port that gives what a policy does not
read."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from greenhouse_protocol.actions import SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.budget import (
    OBSERVATIONS_ONLY,
    ForecastProvider,
    ForecastUncertainty,
    InformationBasis,
    InformationBudget,
)
from greenhouse_protocol.context import (
    CapabilityContext,
    CropBasis,
    CropInstance,
    Goal,
    GoalSense,
    ObservationSource,
    ObservedQuantity,
    SourceKind,
)
from greenhouse_protocol.contracts import policy
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
    check_batch,
    delivered_at,
)
from greenhouse_protocol.contracts.gateway import OPERATOR, PlanState, Receipt
from greenhouse_protocol.contracts.memory_policy import (
    PERSISTENCE,
    InMemoryPolicyPort,
    InMemoryRun,
)
from greenhouse_protocol.contracts.policy import (
    POLICY,
    READABLE_FIELDS,
    RIVAL,
    CancelPlan,
    Decision,
    Delivery,
    Keep,
    Policy,
    PolicyIdentity,
    Revise,
    check_policy_port,
    check_readable,
    conformance_policy_authorisation,
    readable_event,
)
from greenhouse_protocol.enums import EventSource, EventType, ObservationType, SourceType
from greenhouse_protocol.event import Event
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.greenhouse import Plant
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.plan import At, Plan, PlannedAction
from greenhouse_protocol.provenance import RecordSource

START = datetime(2026, 3, 1, 6, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _port(config: AuthorisationConfig, start: datetime) -> InMemoryPolicyPort:
    return InMemoryRun(config, start).open(POLICY)


def test_the_memory_port_keeps_the_contract() -> None:
    assert check_policy_port(_port, START) == []


def test_it_keeps_it_with_a_budget_of_observations_only() -> None:
    def given_none(config: AuthorisationConfig, start: datetime) -> InMemoryPolicyPort:
        return InMemoryRun(config, start, budget=OBSERVATIONS_ONLY).open(POLICY)

    assert check_policy_port(given_none, START) == []


class _OneAtATime(InMemoryPolicyPort):
    """Cuts every batch at one record, as the consumer interface lets a
    producer cap a batch, saying it has more."""

    def observations(self, after: int = 0, limit: int | None = None) -> ObservationBatch:
        return super().observations(after, 1)

    def events(self, after: int = 0, limit: int | None = None) -> EventBatch:
        return super().events(after, 1)

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch:
        return super().outcomes(after, 1)

    def forecasts(self, after: int = 0, limit: int | None = None) -> ForecastBatch:
        return super().forecasts(after, 1)


def test_a_port_that_cuts_its_batches_short_keeps_the_contract() -> None:
    def one_at_a_time(config: AuthorisationConfig, start: datetime) -> InMemoryPolicyPort:
        return _OneAtATime(InMemoryRun(config, start), POLICY)

    assert check_policy_port(one_at_a_time, START) == []


# Ports that give what a policy does not read, each the check finds.


class _EveryReading(InMemoryPolicyPort):
    def observations(self, after: int = 0, limit: int | None = None) -> ObservationBatch:
        everything = tuple(self._run.observations[after:])
        return (
            super()
            .observations(after, limit)
            .model_copy(update={"observations": everything, "next": after + len(everything)})
        )


class _EveryParameter(InMemoryPolicyPort):
    def events(self, after: int = 0, limit: int | None = None) -> EventBatch:
        return (
            super()
            .events(after, limit)
            .model_copy(update={"events": tuple(self._run.events[after:])})
        )


class _EveryForecast(InMemoryPolicyPort):
    def forecasts(self, after: int = 0, limit: int | None = None) -> ForecastBatch:
        everything = tuple(self._run.forecasts[after:])
        return (
            super()
            .forecasts(after, limit)
            .model_copy(update={"forecasts": everything, "next": after + len(everything)})
        )


class _EveryOutcome(InMemoryPolicyPort):
    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch:
        return self._run.gateway.outcomes(after, limit)


class _EveryPlan(InMemoryPolicyPort):
    def plan(self, plan_id: str) -> PlanState | None:
        try:
            return self._run.gateway.plan(plan_id)
        except KeyError:
            return None


class _AsTheOperator(InMemoryPolicyPort):
    def submit(self, plan: Plan) -> Receipt:
        return self._run.gateway.submit(plan, by=OPERATOR)


@pytest.mark.parametrize(
    ("leaky", "scenario"),
    [
        (_EveryReading, "observations_as_delivered"),
        (_EveryParameter, "events_as_allowed"),
        (_EveryForecast, "forecasts_of_its_budget"),
        (_EveryOutcome, "others_plans_unseen"),
        (_EveryPlan, "others_plans_unseen"),
        (_AsTheOperator, "plans_as_its_principal"),
    ],
)
def test_the_check_finds_a_port_that_gives_what_a_policy_does_not_read(
    leaky: type[InMemoryPolicyPort], scenario: str
) -> None:
    def make(config: AuthorisationConfig, start: datetime) -> InMemoryPolicyPort:
        return leaky(InMemoryRun(config, start), POLICY)

    found = check_policy_port(make, START)

    assert any(violation.startswith(f"{scenario}: ") for violation in found), found


# The allowlist.


@pytest.mark.parametrize(
    "record", list(READABLE_FIELDS), ids=[model.__name__ for model in READABLE_FIELDS]
)
def test_every_field_of_a_record_a_policy_reads_is_a_decision(record: type[BaseModel]) -> None:
    assert set(record.model_fields) == READABLE_FIELDS[record], (
        f"{record.__name__} gained or lost a field: name it in READABLE_FIELDS "
        "(greenhouse_protocol.contracts.policy) if a policy reads it, or else leave it out, "
        "and the port gives it only at its default"
    )


def _event(kind: EventType, **parameters: object) -> Event:
    return Event(
        event_id=f"e_{kind}",
        greenhouse_id="gh_memory",
        plant_id="p30",
        timestamp=START,
        event_type=kind,
        source=EventSource.SIMULATION,
        parameters=parameters,
    )


def test_an_event_keeps_only_what_its_type_lets_a_policy_read() -> None:
    harvest = _event(
        EventType.HARVEST, harvested_mass_g=50.0, harvested_fruit_count=1, action="h", truss=3
    )
    watering = _event(EventType.WATERING, amount_ml=100.0)

    assert readable_event(harvest).parameters == {
        "harvested_mass_g": 50.0,
        "harvested_fruit_count": 1,
        "action": "h",
    }
    assert readable_event(watering).parameters == {}
    pruned = _event(EventType.PRUNING, leaf_id="l1", action="p")
    assert readable_event(pruned) is pruned


def _reading(kind: ObservationType, **fields: object) -> Observation:
    return Observation.model_validate(
        dict(
            observation_id=f"o_{kind}",
            greenhouse_id="gh_memory",
            plant_id=None,
            timestamp=START,
            observation_type=kind,
            value=1.0,
            source=RecordSource(type=SourceType.SIMULATION),
        )
        | fields
    )


def _forecast(provider_id: str, quantity: ObservationType) -> Forecast:
    return Forecast(
        forecast_id=f"f_{provider_id}",
        greenhouse_id="gh_memory",
        provider_id=provider_id,
        provider_version="1",
        issued_at=START,
        valid_from=START + HOUR,
        valid_until=START + HOUR,
        quantity=quantity,
        value=1.0,
    )


def test_check_readable_finds_each_record_a_policy_does_not_read() -> None:
    run = InMemoryRun(conformance_policy_authorisation(), START)
    rival = run.open(RIVAL)
    level = PlannedAction(
        action_id="level",
        action=SetLevel(device_id="heater", level=1.0),
        timing=At(at=START + HOUR),
        proposed_by=RIVAL,
    )
    rival.submit(Plan(plan_id="theirs", run_id="run_memory", epoch=0, revision=1, actions=(level,)))
    context = run.context(POLICY)

    found = check_readable(
        [
            _reading(ObservationType.AIR_TEMPERATURE_C),
            _reading(ObservationType.CO2_PPM),
            _event(EventType.HARVEST, harvested_mass_g=50.0, organs=["f1"]),
            _forecast("persistence", ObservationType.OUTSIDE_AIR_TEMPERATURE_C),
            _forecast("persistence", ObservationType.OUTSIDE_RELATIVE_HUMIDITY_PCT),
            _forecast("oracle", ObservationType.OUTSIDE_AIR_TEMPERATURE_C),
            run.gateway.plan("theirs"),
            run.context(RIVAL),
            context,
        ],
        context=context,
        budget=PERSISTENCE,
    )

    assert found == [
        f"observation 'o_{ObservationType.CO2_PPM}' is of {ObservationType.CO2_PPM}, "
        "which none of the context's sources observe",
        "event 'e_HARVEST' gives ['organs'], which a policy does not read of HARVEST",
        "forecast 'f_persistence' is not of a provider and quantity its budget names",
        "forecast 'f_oracle' is not of a provider and quantity its budget names",
        "plan 'theirs' is rival's, not policy's",
        "the context of run 'run_memory' epoch 0 is rival's, not policy's",
    ]


def test_a_field_the_allowlist_leaves_out_is_given_only_at_its_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = InMemoryRun(conformance_policy_authorisation(), START)
    narrower = dict(READABLE_FIELDS)
    narrower[Observation] = READABLE_FIELDS[Observation] - {"quality"}
    narrower[Event] = READABLE_FIELDS[Event] - {"parameters"}
    monkeypatch.setattr(policy, "READABLE_FIELDS", narrower)
    plain = _reading(ObservationType.AIR_TEMPERATURE_C)
    clipped = _reading(ObservationType.AIR_TEMPERATURE_C, quality=frozenset({"CLIPPED"}))
    bare = _event(EventType.WATERING)
    harvest = _event(EventType.HARVEST, harvested_mass_g=50.0)

    found = check_readable(
        [plain, clipped, bare, harvest], context=run.context(POLICY), budget=PERSISTENCE
    )

    assert found == [
        f"observation 'o_{ObservationType.AIR_TEMPERATURE_C}' gives quality, "
        "which a policy does not read",
        "event 'e_HARVEST' gives parameters, which a policy does not read",
    ]


# The budget.


def _provider(basis: InformationBasis) -> ForecastProvider:
    return ForecastProvider(
        provider_id="weather",
        version="1",
        basis=basis,
        quantities=frozenset({ObservationType.OUTSIDE_AIR_TEMPERATURE_C}),
        issued_every_s=3600.0,
        horizon_s=86_400.0,
        uncertainty=ForecastUncertainty.STANDARD_DEVIATION,
    )


@pytest.mark.parametrize(
    ("fields", "oracle"),
    [
        (dict(forecasts=(_provider(InformationBasis.OBSERVED),)), False),
        (dict(forecasts=(_provider(InformationBasis.EXTERNAL),)), False),
        (dict(forecasts=(_provider(InformationBasis.PRIVILEGED),)), True),
        (dict(full_state=True), True),
    ],
)
def test_a_budget_is_labelled_an_oracle_exactly_when_it_gives_the_truth(
    fields: dict[str, object], oracle: bool
) -> None:
    InformationBudget.model_validate(dict(budget_id="b", oracle=oracle) | fields)

    with pytest.raises(ValidationError, match="labelled an oracle exactly when"):
        InformationBudget.model_validate(dict(budget_id="b", oracle=not oracle) | fields)


def test_a_budget_names_each_provider_once() -> None:
    provider = _provider(InformationBasis.OBSERVED)

    with pytest.raises(ValidationError, match="named more than once"):
        InformationBudget(budget_id="b", forecasts=(provider, provider))


# The context.


def test_a_crop_grown_by_area_has_no_plants_and_takes_no_crop_action() -> None:
    row = dict(scope_id="row_1", scope_kind="row", cultivated_m2=1.0, floor_m2=2.0)
    plant = Plant(plant_id="p1", variety="v", row=1, position_in_row=1)

    CropInstance.model_validate(row | dict(grown_by=CropBasis.AREA))
    with pytest.raises(ValidationError, match="grown by area"):
        CropInstance.model_validate(row | dict(grown_by=CropBasis.AREA, plants=(plant,)))
    with pytest.raises(ValidationError, match="not crop actions"):
        CropInstance.model_validate(
            row | dict(grown_by=CropBasis.PLANT, crop_actions=frozenset({"set_level"}))
        )


def test_a_source_is_in_one_place_at_most() -> None:
    air = (ObservedQuantity(observation_type=ObservationType.AIR_TEMPERATURE_C),)

    with pytest.raises(ValidationError, match="at most one of a zone, a plant and a scope"):
        ObservationSource(
            source_id="s", kind=SourceKind.SENSOR, quantities=air, zone_id="z", scope_id="row_1"
        )
    with pytest.raises(ValidationError, match="named more than once"):
        ObservationSource(source_id="s", kind=SourceKind.SENSOR, quantities=air * 2)


@pytest.mark.parametrize(
    ("sense", "bounds", "refused"),
    [
        (GoalSense.MINIMISE, {}, False),
        (GoalSense.MINIMISE, {"high": 1.0}, True),
        (GoalSense.WITHIN, {"low": 15.0, "high": 30.0}, False),
        (GoalSense.WITHIN, {}, True),
        (GoalSense.WITHIN, {"low": 30.0, "high": 15.0}, True),
    ],
)
def test_a_goal_has_bounds_exactly_when_it_is_a_constraint(
    sense: GoalSense, bounds: dict[str, float], refused: bool
) -> None:
    fields = dict(goal_id="air", description="the air", unit="°C", sense=sense) | bounds

    if refused:
        with pytest.raises(ValidationError):
            Goal.model_validate(fields)
    else:
        Goal.model_validate(fields)


def test_a_context_names_each_device_once_and_lists_what_a_policy_acts_on() -> None:
    context = InMemoryRun(conformance_policy_authorisation(), START).context(POLICY)

    assert context.items().devices == {"heater", "vent_1"}
    assert context.items().plants == {"p30", "p31"}
    assert context.observed_types() == {
        ObservationType.AIR_TEMPERATURE_C,
        ObservationType.OUTSIDE_AIR_TEMPERATURE_C,
    }
    with pytest.raises(ValidationError, match="devices named more than once"):
        CapabilityContext.model_validate(context.model_dump() | {"devices": context.devices * 2})


# The forecast.


def test_a_forecast_is_delivered_when_it_is_issued_and_never_before() -> None:
    forecast = _forecast("persistence", ObservationType.OUTSIDE_AIR_TEMPERATURE_C)
    batch = ForecastBatch(
        run_id="run_memory",
        epoch=0,
        after=0,
        next=1,
        simulated_now=START - HOUR,
        forecasts=(forecast,),
    )

    assert delivered_at(forecast) == START
    assert check_batch(batch) == [
        "forecasts batch of run 'run_memory' epoch 0 after=0 delivers 'f_persistence' at "
        f"{START.isoformat()}, after its clock ({(START - HOUR).isoformat()})"
    ]
    with pytest.raises(ValidationError, match="before it is valid from"):
        Forecast.model_validate(forecast.model_dump() | {"valid_until": START})


# A policy, as the runner steps it.


class _FullHeat:
    """Sets its heater to full, as soon as it can, and keeps it there."""

    identity = PolicyIdentity(name="full_heat", version="1")
    decide_every_s = 3600.0

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._heater = next(d.device_id for d in context.devices if "heats" in d.does)
        self._decided = False

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        if self._decided:
            return Keep()
        self._decided = True
        action = PlannedAction(
            action_id="heat",
            action=SetLevel(device_id=self._heater, level=1.0),
            timing=At(at=at),
            proposed_by=POLICY,
        )
        return Revise(actions=(action,))

    def stop(self) -> None:
        self._decided = False


def test_a_policy_decides_and_its_revision_is_given_through_its_port() -> None:
    port = InMemoryRun(conformance_policy_authorisation(), START).open(POLICY)
    stepped: Policy = _FullHeat()
    stepped.start(port.context(), port.budget())

    first = stepped.decide(START, Delivery())
    then = stepped.decide(START + HOUR, Delivery())

    assert isinstance(first, Revise)
    assert isinstance(then, Keep)
    receipt = port.submit(
        Plan(plan_id="steer", run_id="run_memory", epoch=0, revision=1, actions=first.actions)
    )
    assert receipt.accepted
    port.advance(START + HOUR)
    assert [o.ref.action_id for o in port.outcomes().outcomes] == ["heat"]


def test_a_decision_is_read_by_its_kind() -> None:
    read = TypeAdapter(Decision).validate_python

    assert read({"kind": "keep"}) == Keep()
    assert read({"kind": "cancel_plan"}) == CancelPlan()
    assert read({"kind": "revise", "actions": []}) == Revise(actions=())
