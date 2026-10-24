"""The actuation contracts (decision 0046), held to their conformance
checks through their in-memory reference implementation: an executor that
may lose messages, and a gateway on a clock that continues."""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.actions import (
    ActionKind,
    ActionRef,
    ActionTargets,
    Harvest,
    HarvestScope,
    SetLevel,
    SetTarget,
)
from greenhouse_protocol.assignment import Assignment
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.contracts.consumer import check_polls
from greenhouse_protocol.contracts.execution import (
    ActionNotExecutable,
    AssignmentStatus,
    check_executor,
)
from greenhouse_protocol.contracts.gateway import (
    OPERATOR,
    GatewayLimits,
    check_gateway,
    check_limits,
    conformance_authorisation,
    occurrences,
)
from greenhouse_protocol.contracts.memory_gateway import (
    EXECUTOR,
    InMemoryGateway,
    MemoryExecutor,
)
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import (
    ActionStateKind,
    Asap,
    At,
    ExecutorKind,
    ExecutorRef,
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


# What #326's review found the reference gateway and the checks got wrong.


def _ends(gateway: InMemoryGateway) -> list[tuple[str, int, OutcomeStatus]]:
    return [(str(o.ref), o.revision, o.status) for o in gateway.outcomes().outcomes]


def test_it_keeps_the_contract_with_an_executor_sent_its_assignments_hours_ahead() -> None:
    """The conformance check's rights are withdrawn an hour after the run's
    start, its action due an hour after that: with a two-hour lead, the
    assignment was sent before the withdrawal, and must be revoked at its
    due."""
    violations = check_gateway(
        lambda config, start: _gateway(config, start, MemoryExecutor(start, lead_s=2 * 3600)),
        START,
    )

    assert violations == []


def test_rights_withdrawn_after_an_assignment_was_sent_revoke_it_at_its_due() -> None:
    executor = MemoryExecutor(START, lead_s=2 * 3600)
    gateway = _gateway(conformance_authorisation(), START, executor)
    gateway.submit(_plan(gateway, _vent("vent", timing=At(at=START + 3 * HOUR))), by=OPERATOR)
    gateway.advance(START + 2 * HOUR)
    assert [s.state for s in gateway.actions()] == [ActionStateKind.ASSIGNED]

    gateway.authorise(conformance_authorisation(2, operator_kinds=frozenset({ActionKind.INSPECT})))
    gateway.advance(START + 4 * HOUR)

    assert _ends(gateway) == [("vent", 1, OutcomeStatus.REFUSED)]
    assert executor.reports() == ()


def test_an_action_revised_while_it_runs_ends_in_its_own_outcome() -> None:
    """Its revision's replacement is another action, with an outcome of its
    own: both are accounted for."""
    executor = MemoryExecutor(START, duration_s=1800, longest_s=3600)
    gateway = _gateway(conformance_authorisation(), START, executor)
    gateway.submit(_plan(gateway, _vent("vent")), by=OPERATOR)
    gateway.advance(START + HOUR + timedelta(minutes=10))
    revised = _plan(gateway, _vent("vent", timing=At(at=START + 2 * HOUR)))
    gateway.submit(revised.model_copy(update={"revision": 2}), by=OPERATOR)
    gateway.advance(START + 5 * HOUR)

    assert _ends(gateway) == [
        ("vent", 1, OutcomeStatus.EXECUTED),
        ("vent", 2, OutcomeStatus.EXECUTED),
    ]
    assert check_polls([gateway.outcomes()], greenhouse_id=gateway.greenhouse_id) == []


def test_what_waits_for_a_revised_prerequisite_waits_for_its_new_form() -> None:
    then = _vent("then", timing=Asap(), after=("first",))
    gateway = _gateway(conformance_authorisation(), START)
    gateway.submit(_plan(gateway, _vent("first"), then), by=OPERATOR)
    revised = _plan(gateway, _vent("first", timing=At(at=START + 2 * HOUR)), then)
    gateway.submit(revised.model_copy(update={"revision": 2}), by=OPERATOR)
    gateway.advance(START + 3 * HOUR)

    assert _ends(gateway) == [
        ("first", 1, OutcomeStatus.SUPERSEDED),
        ("first", 2, OutcomeStatus.EXECUTED),
        ("then", 2, OutcomeStatus.EXECUTED),
    ]
    finished = {o.ref.action_id: o.resolved_at for o in gateway.outcomes().outcomes}
    assert finished["then"] == START + 2 * HOUR


def test_a_prerequisite_done_then_revised_is_waited_for_again() -> None:
    then = _vent("then", timing=At(at=START + 3 * HOUR), after=("first",))
    gateway = _gateway(conformance_authorisation(), START)
    gateway.submit(_plan(gateway, _vent("first"), then), by=OPERATOR)
    gateway.advance(START + 2 * HOUR)
    revised = _plan(gateway, _vent("first", timing=At(at=START + 4 * HOUR)), then)
    gateway.submit(revised.model_copy(update={"revision": 2}), by=OPERATOR)
    gateway.advance(START + 3 * HOUR + timedelta(minutes=30))

    assert [s.ref.action_id for s in gateway.actions()] == ["then", "first"]


def test_an_aborted_plans_actions_are_never_given_to_its_executor() -> None:
    executor = MemoryExecutor(START + 2 * HOUR)
    gateway = _gateway(conformance_authorisation(), START + 2 * HOUR, executor)
    aborts = _vent("late", lateness=Lateness(on_late=OnLate.ABORT_PLAN))
    also = _vent("also", timing=At(at=START + 2 * HOUR))
    gateway.submit(_plan(gateway, aborts, also), by=OPERATOR)
    gateway.advance(START + 3 * HOUR)

    assert _ends(gateway) == [
        ("late", 1, OutcomeStatus.MISSED),
        ("also", 1, OutcomeStatus.CANCELLED),
    ]
    assert executor.reports() == ()
    assert executor.status("e0-a3") == AssignmentStatus.UNKNOWN


def test_a_dependent_starts_when_its_prerequisite_finishes_however_the_clock_moves() -> None:
    """A prerequisite that takes 10 s of an executor's 60 s at most, and an
    action due within 20 s of its start: carried out in time whether the
    clock is moved in one step or in many."""

    def run(step: timedelta) -> list[tuple[str, int, OutcomeStatus]]:
        executor = MemoryExecutor(START, duration_s=10, longest_s=60)
        gateway = _gateway(conformance_authorisation(), START, executor)
        then = _vent(
            "then", timing=Asap(deadline=START + HOUR + timedelta(seconds=20)), after=("first",)
        )
        gateway.submit(_plan(gateway, _vent("first"), then), by=OPERATOR)
        moment = START
        while moment < START + 2 * HOUR:
            moment = min(moment + step, START + 2 * HOUR)
            gateway.advance(moment)
        return _ends(gateway)

    done = [("first", 1, OutcomeStatus.EXECUTED), ("then", 1, OutcomeStatus.EXECUTED)]
    assert run(2 * HOUR) == run(timedelta(seconds=5)) == done


def test_an_action_none_of_whose_executors_is_the_runs_is_refused_at_once() -> None:
    gateway = _gateway(conformance_authorisation(), START)
    grower = ExecutorRef(kind=ExecutorKind.PERSON, id="grower")
    other_robot = ExecutorRef(kind=ExecutorKind.ROBOT, id="picker")
    any_robot = ExecutorRef(kind=ExecutorKind.ROBOT)
    receipt = gateway.submit(
        _plan(
            gateway,
            _vent("by_hand", executed_by=(grower,)),
            _vent("by_picker", executed_by=(other_robot,)),
            _vent("by_any_robot", executed_by=(grower, any_robot)),
            _vent("by_this_robot", executed_by=(EXECUTOR,)),
        ),
        by=OPERATOR,
    )
    gateway.advance(START + 2 * HOUR)

    assert [ref.action_id for ref in receipt.refused] == ["by_hand", "by_picker"]
    assert {ref: status for ref, _, status in _ends(gateway)} == {
        "by_hand": OutcomeStatus.REFUSED,
        "by_picker": OutcomeStatus.REFUSED,
        "by_any_robot": OutcomeStatus.EXECUTED,
        "by_this_robot": OutcomeStatus.EXECUTED,
    }


def test_recurring_actions_go_before_one_offs_due_at_the_same_instant() -> None:
    """So that a one-off command overrides its standing schedule, whatever
    their places in the plan."""
    gateway = _gateway(conformance_authorisation(), START)
    daily = Recurrence(period=timedelta(days=1), count=1)
    gateway.submit(_plan(gateway, _vent("one_off"), _vent("standing", every=daily)), by=OPERATOR)
    gateway.advance(START + 2 * HOUR)

    assert [ref for ref, _, _ in _ends(gateway)] == ["standing@0", "one_off"]


def test_executors_of_one_kind_are_checked_with_an_action_of_their_kind() -> None:
    class Harvester(MemoryExecutor):
        """Harvests only: it knows how long a harvest takes, and refuses
        anything else."""

        def kinds(self) -> frozenset[ActionKind]:
            return frozenset({ActionKind.HARVEST})

        def longest_duration_s(self, kind: ActionKind) -> float:
            return {ActionKind.HARVEST: 600.0}[kind]

        def perform(self, assignment: Assignment) -> None:
            if assignment.action.kind not in self.kinds():
                raise ActionNotExecutable("gh", f"it does not {assignment.action.kind}")
            super().perform(assignment)

    picked = Harvest(plant_id="p30", scope=HarvestScope.TRUSS, organ_id="p30_t01")

    assert check_executor(Harvester, START) == []
    assert check_executor(Harvester, START, action=picked) == []
    assert check_executor(Harvester, START, action=SetLevel(device_id="vent_1", level=1.0)) == [
        "it was checked with set_level, a kind it does not carry out"
    ]


def test_a_gateway_names_the_executor_it_is_given() -> None:
    """A gateway acting through an executor of its own, such as a
    simulator's run, names it in its outcomes and in a plan's
    `executed_by`, not the memory executor."""
    run = ExecutorRef(kind=ExecutorKind.SIMULATED_RUN, id="run")
    gateway = InMemoryGateway(
        conformance_authorisation(), START, executor=MemoryExecutor(START), executor_ref=run
    )
    gateway.submit(
        _plan(gateway, _vent("vent"), _vent("other", executed_by=(EXECUTOR,))), by=OPERATOR
    )
    gateway.advance(START + 2 * HOUR)
    ends = {o.ref.action_id: o for o in gateway.outcomes().outcomes}

    assert (ends["vent"].status, ends["vent"].executor) == (OutcomeStatus.EXECUTED, run)
    assert ends["other"].status == OutcomeStatus.REFUSED


def test_a_target_the_runs_controller_has_not_is_refused_at_once() -> None:
    gateway = InMemoryGateway(
        conformance_authorisation(),
        START,
        items=ActionTargets(devices=frozenset({"vent_1"}), targets=frozenset({"heating_day"})),
    )
    night = SetTarget(target="heating_night", value_c=15.0)
    gateway.submit(_plan(gateway, _vent("night", action=night)), by=OPERATOR)
    (refused,) = gateway.outcomes().outcomes

    assert (refused.status, refused.reason) == (
        OutcomeStatus.REFUSED,
        "the run has no heating_night",
    )


def test_a_finished_run_started_over_takes_plans_again() -> None:
    gateway = _gateway(conformance_authorisation(), START)
    gateway.finish()
    gateway.restart(continue_clock=False)

    receipt = gateway.submit(_plan(gateway, _vent("vent")), by=OPERATOR)

    assert receipt.accepted
    assert gateway.run().clock.playing
