"""The actuation contracts (decision 0046), held to their conformance
checks through their in-memory reference implementation: an executor that
may lose messages, and a gateway on a clock that continues."""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.actions import ActionKind, ActionRef, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.contracts.consumer import check_polls
from greenhouse_protocol.contracts.execution import check_executor
from greenhouse_protocol.contracts.gateway import (
    OPERATOR,
    GatewayLimits,
    check_gateway,
    check_limits,
    conformance_authorisation,
    occurrences,
)
from greenhouse_protocol.contracts.memory_gateway import InMemoryGateway, MemoryExecutor
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import (
    ActionStateKind,
    Asap,
    At,
    Lateness,
    OnLate,
    Plan,
    PlannedAction,
    Recurrence,
)

START = datetime(2026, 3, 1, 6, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _gateway(
    config: AuthorisationConfig, start: datetime, executor: MemoryExecutor | None = None
) -> InMemoryGateway:
    return InMemoryGateway(config, start, executor=executor or MemoryExecutor(start))


def test_the_in_memory_gateway_keeps_the_gateway_contract() -> None:
    assert check_gateway(lambda config, start: _gateway(config, start), START) == []


def test_it_keeps_it_with_an_executor_that_loses_first_sends_and_wants_a_lead() -> None:
    violations = check_gateway(
        lambda config, start: _gateway(
            config, start, MemoryExecutor(start, loses_first_send=True, lead_s=600)
        ),
        START,
    )

    assert violations == []


def test_the_memory_executor_keeps_the_executor_contract() -> None:
    assert check_executor(lambda start: MemoryExecutor(start), START) == []
    assert check_executor(lambda start: MemoryExecutor(start, loses_first_send=True), START) == []


def test_an_executor_that_cannot_be_reached_does_not_conform() -> None:
    violations = check_executor(
        lambda start: MemoryExecutor(start, unreachable=frozenset({"soon"})), START
    )

    assert violations == ["an assignment received was neither reported nor said to be under way"]


def _vent(action_id: str, **fields: object) -> PlannedAction:
    return PlannedAction.model_validate(
        dict(
            action_id=action_id,
            action=SetLevel(device_id="vent_1", level=1.0),
            timing=At(at=START + HOUR),
            proposed_by=OPERATOR,
        )
        | fields
    )


def _plan(gateway: InMemoryGateway, *actions: PlannedAction) -> Plan:
    return Plan(
        plan_id="p", run_id=gateway.run_id, epoch=gateway.epoch, revision=1, actions=actions
    )


def test_a_lost_report_ends_unconfirmed_and_cancels_what_waits_for_it() -> None:
    gateway = _gateway(
        conformance_authorisation(), START, MemoryExecutor(START, unreachable=frozenset({"vent"}))
    )
    gateway.submit(
        _plan(gateway, _vent("vent"), _vent("after", timing=Asap(), after=("vent",))), by=OPERATOR
    )
    gateway.advance(START + 3 * HOUR)
    ends = {o.ref.action_id: o.status for o in gateway.outcomes().outcomes}

    assert ends == {"vent": OutcomeStatus.UNCONFIRMED, "after": OutcomeStatus.CANCELLED}


def test_a_critical_action_given_late_is_missed_and_its_dependents_cancelled() -> None:
    gateway = _gateway(conformance_authorisation(), START + 2 * HOUR)
    critical = _vent("pick", lateness=Lateness(on_late=OnLate.CRITICAL))
    place = _vent("place", timing=Asap(), after=("pick",), if_prerequisite_fails="proceed")
    gateway.submit(_plan(gateway, critical, place), by=OPERATOR)
    ends = {o.ref.action_id: o.status for o in gateway.outcomes().outcomes}

    assert ends == {"pick": OutcomeStatus.MISSED, "place": OutcomeStatus.CANCELLED}


def test_a_late_action_with_a_fallback_carries_the_fallback_out() -> None:
    gateway = _gateway(conformance_authorisation(), START + 2 * HOUR)
    shut = SetLevel(device_id="vent_1", level=0.0)
    gateway.submit(
        _plan(gateway, _vent("open", lateness=Lateness(on_late=OnLate.FALLBACK, fallback=shut))),
        by=OPERATOR,
    )
    outcomes = gateway.outcomes().outcomes

    assert [(str(o.ref), o.status) for o in outcomes] == [
        ("open", OutcomeStatus.MISSED),
        ("open/fallback", OutcomeStatus.EXECUTED),
    ]
    assert outcomes[0].fallback == ActionRef(action_id="open", fallback=True)


def test_run_late_carries_it_out_late() -> None:
    gateway = _gateway(conformance_authorisation(), START + 2 * HOUR)
    gateway.submit(_plan(gateway, _vent("open")), by=OPERATOR)

    assert [o.status for o in gateway.outcomes().outcomes] == [OutcomeStatus.LATE]


def test_recurring_actions_pair_their_occurrences_and_fill_the_log_in_order() -> None:
    gateway = _gateway(conformance_authorisation(), START)
    daily = Recurrence(period=timedelta(days=1), count=3)
    harvest = _vent("open", every=daily)
    lower = _vent("shut", every=daily, timing=At(at=START + 2 * HOUR), after=("open",))
    gateway.submit(_plan(gateway, harvest, lower), by=OPERATOR)
    gateway.advance(START + timedelta(days=3))
    outcomes = gateway.outcomes().outcomes

    assert [str(o.ref) for o in outcomes] == [
        "open@0",
        "shut@0",
        "open@1",
        "shut@1",
        "open@2",
        "shut@2",
    ]
    assert all(o.status == OutcomeStatus.EXECUTED for o in outcomes)
    assert check_polls([gateway.outcomes()], greenhouse_id=gateway.greenhouse_id) == []


def test_the_listing_filters_by_state_kind_target_and_plan() -> None:
    gateway = _gateway(conformance_authorisation(), START)
    gateway.submit(
        _plan(gateway, _vent("open"), _vent("shut", timing=Asap(), after=("open",))), by=OPERATOR
    )

    assert [
        s.ref.action_id for s in gateway.actions(states=frozenset({ActionStateKind.WAITING}))
    ] == [
        "open",
        "shut",
    ]
    assert gateway.actions(kinds=frozenset({ActionKind.HARVEST})) == ()
    assert gateway.actions(plan_id="other") == ()
    listed = gateway.actions()
    assert listed[0].waited_on_by == (ActionRef(action_id="shut"),)
    assert listed[1].waiting_for == (ActionRef(action_id="open"),)


def test_occurrences_and_limits() -> None:
    by_count = _vent("a", every=Recurrence(period=timedelta(hours=1), count=5))
    by_end = _vent("b", every=Recurrence(period=timedelta(hours=1), until=START + 4 * HOUR))
    plan = Plan(
        plan_id="p", run_id="r", epoch=0, revision=1, actions=(by_count, by_end, _vent("c"))
    )

    assert [occurrences(p) for p in plan.actions] == [5, 4, 1]
    assert check_limits(plan, GatewayLimits(max_actions=3, max_occurrences=10)) == []
    assert len(check_limits(plan, GatewayLimits(max_actions=2, max_occurrences=9))) == 2
