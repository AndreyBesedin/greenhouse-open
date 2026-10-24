"""When a gateway starts an action (P13.6, decision 0046): at the earliest
instant its executor honours, as the executor says (`SaysWhen`), with one of
its hands free for as long as the action's kind takes at the longest; late,
by the action's own rule, when there is none by its deadline."""

from datetime import UTC, datetime, timedelta
from typing import Any, Final

import pytest

from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.assignment import Assignment
from greenhouse_protocol.contracts.execution import SaysWhen, check_executor
from greenhouse_protocol.contracts.gateway import OPERATOR, conformance_authorisation
from greenhouse_protocol.contracts.memory_gateway import InMemoryGateway, MemoryExecutor
from greenhouse_protocol.outcome import OutcomeStatus
from greenhouse_protocol.plan import (
    Asap,
    At,
    Lateness,
    OnLate,
    Plan,
    PlannedAction,
    Window,
)

START: Final = datetime(2026, 3, 1, 6, tzinfo=UTC)
HOUR: Final = timedelta(hours=1)
MINUTE: Final = timedelta(minutes=1)
HALF_AN_HOUR: Final = 1800.0
SHUT: Final = SetLevel(device_id="vent_1", level=0.0)


class _Hourly(MemoryExecutor):
    """Carries out every kind on the hour, and says so."""

    def honours(self, kind: ActionKind, instant: datetime) -> bool:
        return instant == instant.replace(minute=0, second=0, microsecond=0)

    def earliest(
        self, kind: ActionKind, not_before: datetime, not_after: datetime | None = None
    ) -> datetime | None:
        at = not_before
        if not self.honours(kind, at):
            at = at.replace(minute=0, second=0, microsecond=0) + HOUR
        return at if not_after is None or at <= not_after else None


class _LevelsTakeNothing(MemoryExecutor):
    """One hand, which a level does not hold: it takes no time."""

    def longest_duration_s(self, kind: ActionKind) -> float:
        return 0.0 if kind == ActionKind.SET_LEVEL else HALF_AN_HOUR


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


def _given(executor: MemoryExecutor, *actions: PlannedAction) -> InMemoryGateway:
    gateway = InMemoryGateway(conformance_authorisation(), START, executor=executor)
    receipt = gateway.submit(
        Plan(plan_id="p", run_id=gateway.run_id, epoch=gateway.epoch, revision=1, actions=actions),
        by=OPERATOR,
    )
    assert receipt.accepted, receipt.errors
    return gateway


def _ends(gateway: InMemoryGateway) -> dict[str, tuple[OutcomeStatus, datetime | None]]:
    return {str(o.ref): (o.status, o.started_at) for o in gateway.outcomes().outcomes}


def _one_hand(start: datetime = START) -> MemoryExecutor:
    """One hand, each action taking it half an hour."""
    return MemoryExecutor(start, duration_s=HALF_AN_HOUR, longest_s=HALF_AN_HOUR, capacity=1)


def test_a_window_starts_at_the_first_instant_its_executor_honours_in_it() -> None:
    executor = _Hourly(START)
    window = Window(not_before=START + 10 * MINUTE, not_after=START + 3 * HOUR)
    gateway = _given(executor, _vent("open", timing=window))
    gateway.advance(START + 4 * HOUR)

    assert isinstance(executor, SaysWhen)
    assert _ends(gateway) == {"open": (OutcomeStatus.EXECUTED, START + HOUR)}


def test_a_window_its_executor_honours_no_instant_in_is_refused_at_once() -> None:
    window = Window(not_before=START + 10 * MINUTE, not_after=START + 50 * MINUTE)
    gateway = _given(_Hourly(START), _vent("open", timing=window))
    (refused,) = gateway.outcomes().outcomes

    assert refused.status == OutcomeStatus.REFUSED
    assert refused.reason == (
        f"no executor honours set_level from {(START + 10 * MINUTE).isoformat()} "
        f"by {(START + 50 * MINUTE).isoformat()}"
    )


def test_an_action_as_soon_as_possible_starts_at_the_next_instant_honoured_after_its_wait() -> None:
    executor = _Hourly(START, duration_s=600.0, longest_s=600.0)
    gateway = _given(
        executor, _vent("open"), _vent("shut", action=SHUT, timing=Asap(), after=("open",))
    )
    gateway.advance(START + 3 * HOUR)

    assert _ends(gateway) == {
        "open": (OutcomeStatus.EXECUTED, START + HOUR),
        "shut": (OutcomeStatus.EXECUTED, START + 2 * HOUR),
    }


@pytest.mark.parametrize(
    ("on_late", "ends"),
    [
        (
            OnLate.RUN_LATE,
            {
                "second": (OutcomeStatus.LATE, START + HOUR + HOUR / 2),
                "after": (OutcomeStatus.EXECUTED, START + 2 * HOUR),
                "other": (OutcomeStatus.EXECUTED, START + 5 * HOUR),
            },
        ),
        (
            OnLate.SKIP,
            {
                "second": (OutcomeStatus.MISSED, None),
                "after": (OutcomeStatus.EXECUTED, START + HOUR + HOUR / 2),
                "other": (OutcomeStatus.EXECUTED, START + 5 * HOUR),
            },
        ),
        (
            OnLate.CRITICAL,
            {
                "second": (OutcomeStatus.MISSED, None),
                "after": (OutcomeStatus.CANCELLED, None),
                "other": (OutcomeStatus.EXECUTED, START + 5 * HOUR),
            },
        ),
        (
            OnLate.FALLBACK,
            {
                "second": (OutcomeStatus.MISSED, None),
                "second/fallback": (OutcomeStatus.EXECUTED, START + HOUR + HOUR / 2),
                "after": (OutcomeStatus.EXECUTED, START + 2 * HOUR),
                "other": (OutcomeStatus.EXECUTED, START + 5 * HOUR),
            },
        ),
        (
            OnLate.ABORT_PLAN,
            {
                # Assigned for that instant, it had not started yet.
                "first": (OutcomeStatus.CANCELLED, None),
                "second": (OutcomeStatus.MISSED, None),
                "after": (OutcomeStatus.CANCELLED, None),
                "other": (OutcomeStatus.CANCELLED, None),
            },
        ),
    ],
)
def test_an_action_no_hand_is_free_for_by_its_deadline_is_late_by_its_rule(
    on_late: OnLate, ends: dict[str, tuple[OutcomeStatus, datetime | None]]
) -> None:
    """One hand, taken from an hour on by the first action for half an
    hour: the second, due then too, is late, and what waits for it
    proceeds, unless the second was critical. Aborting its plan cancels
    every action of it that has not started, the first among them."""
    lateness = Lateness(on_late=on_late, fallback=SHUT if on_late == OnLate.FALLBACK else None)
    gateway = _given(
        _one_hand(),
        _vent("first"),
        _vent("second", lateness=lateness),
        _vent("after", timing=Asap(), after=("second",), if_prerequisite_fails="proceed"),
        _vent("other", timing=At(at=START + 5 * HOUR)),
    )
    gateway.advance(START + 6 * HOUR)

    assert _ends(gateway) == {"first": (OutcomeStatus.EXECUTED, START + HOUR), **ends}


@pytest.mark.parametrize(
    ("tolerance_s", "second"),
    [
        (HALF_AN_HOUR, OutcomeStatus.EXECUTED),
        (HALF_AN_HOUR - 1, OutcomeStatus.LATE),
    ],
)
def test_an_action_starting_as_a_hand_comes_free_within_its_tolerance_is_on_time(
    tolerance_s: float, second: OutcomeStatus
) -> None:
    gateway = _given(
        _one_hand(), _vent("first"), _vent("second", lateness=Lateness(tolerance_s=tolerance_s))
    )
    gateway.advance(START + 3 * HOUR)

    assert _ends(gateway)["second"] == (second, START + HOUR + HOUR / 2)


def test_an_action_still_waiting_for_a_hand_is_late_at_its_deadline() -> None:
    """Ten minutes' tolerance, and the only hand busy for half an hour: it
    is missed at its deadline, not when the hand comes free."""
    skip = Lateness(tolerance_s=600.0, on_late=OnLate.SKIP)
    gateway = _given(_one_hand(), _vent("first"), _vent("second", lateness=skip))
    gateway.advance(START + 3 * HOUR)
    missed = next(o for o in gateway.outcomes().outcomes if o.ref.action_id == "second")

    assert (missed.status, missed.resolved_at) == (
        OutcomeStatus.MISSED,
        START + HOUR + 10 * MINUTE,
    )


def test_as_many_start_at_once_as_its_executor_has_hands() -> None:
    two = MemoryExecutor(START, duration_s=HALF_AN_HOUR, longest_s=HALF_AN_HOUR, capacity=2)
    gateway = _given(two, _vent("first"), _vent("second"), _vent("third"))
    gateway.advance(START + 3 * HOUR)

    assert _ends(gateway) == {
        "first": (OutcomeStatus.EXECUTED, START + HOUR),
        "second": (OutcomeStatus.EXECUTED, START + HOUR),
        "third": (OutcomeStatus.LATE, START + HOUR + HOUR / 2),
    }


def test_a_kind_that_takes_nothing_holds_no_hand() -> None:
    gateway = _given(_LevelsTakeNothing(START, capacity=1), _vent("first"), _vent("second"))
    gateway.advance(START + 2 * HOUR)

    assert _ends(gateway) == {
        "first": (OutcomeStatus.EXECUTED, START + HOUR),
        "second": (OutcomeStatus.EXECUTED, START + HOUR),
    }


def test_the_same_plan_ends_the_same_however_the_clock_moves() -> None:
    def given() -> InMemoryGateway:
        return _given(
            _one_hand(),
            _vent("first"),
            _vent("second", lateness=Lateness(on_late=OnLate.FALLBACK, fallback=SHUT)),
            _vent("third", timing=Window(not_before=START + HOUR, not_after=START + 3 * HOUR)),
            _vent("after", timing=Asap(), after=("third",)),
        )

    at_once, by_minutes = given(), given()
    at_once.advance(START + 5 * HOUR)
    for minute in range(1, 5 * 60 + 1):
        by_minutes.advance(START + minute * MINUTE)

    def told(gateway: InMemoryGateway) -> list[tuple[str, str, object, object, object]]:
        return [
            (o.outcome_id, str(o.ref), o.status, o.started_at, o.resolved_at)
            for o in gateway.outcomes().outcomes
        ]

    assert told(at_once) == told(by_minutes)
    assert len(told(at_once)) == 5


def test_an_executor_that_says_when_says_what_it_honours() -> None:
    class Hasty(_Hourly):
        """Says it carries every kind out at once, whatever the instant."""

        def earliest(
            self, kind: ActionKind, not_before: datetime, not_after: datetime | None = None
        ) -> datetime | None:
            return not_before

    class Unbounded(_Hourly):
        """Says when, unless it is given a bound."""

        def earliest(
            self, kind: ActionKind, not_before: datetime, not_after: datetime | None = None
        ) -> datetime | None:
            return None if not_after is not None else super().earliest(kind, not_before)

    class BoundedHasty(_Hourly):
        """Says the instant asked for, given it as its bound, honoured or not."""

        def earliest(
            self, kind: ActionKind, not_before: datetime, not_after: datetime | None = None
        ) -> datetime | None:
            if not_after == not_before:
                return not_before
            return super().earliest(kind, not_before, not_after)

    assert check_executor(_Hourly, START) == []
    violations = check_executor(Hasty, START)
    assert (
        f"it says set_level from {(START + timedelta(seconds=30)).isoformat()} at "
        f"{(START + timedelta(seconds=30)).isoformat()}, which it does not honour" in violations
    )
    on_the_hour, off_it = START.isoformat(), (START + timedelta(seconds=30)).isoformat()
    assert f"it honours set_level at {on_the_hour}, and says no instant by then" in check_executor(
        Unbounded, START
    )
    assert f"it does not honour set_level at {off_it}, and says it by then" in check_executor(
        BoundedHasty, START
    )


class _Always(MemoryExecutor):
    """Carries out every kind at any instant, and says so."""

    def earliest(
        self, kind: ActionKind, not_before: datetime, not_after: datetime | None = None
    ) -> datetime | None:
        return not_before if not_after is None or not_before <= not_after else None


class _Receiving(_Hourly):
    """On the hour, as `_Hourly`, keeping when it received each assignment."""

    def __init__(self, start: datetime, **kwargs: Any) -> None:
        super().__init__(start, **kwargs)
        self.received: dict[str, datetime] = {}

    def perform(self, assignment: Assignment) -> None:
        self.received.setdefault(assignment.ref.action_id, self.now)
        super().perform(assignment)


@pytest.mark.parametrize(
    ("timing", "on_late", "ends"),
    [
        (
            Window(not_before=START - 2 * HOUR, not_after=START - HOUR),
            OnLate.RUN_LATE,
            {"open": (OutcomeStatus.LATE, START)},
        ),
        (
            Asap(deadline=START - HOUR),
            OnLate.FALLBACK,
            {
                "open": (OutcomeStatus.MISSED, None),
                "open/fallback": (OutcomeStatus.EXECUTED, START),
            },
        ),
    ],
)
def test_a_window_or_a_deadline_already_past_is_late_by_its_rule_not_refused(
    timing: Window | Asap, on_late: OnLate, ends: dict[str, tuple[OutcomeStatus, datetime | None]]
) -> None:
    lateness = Lateness(on_late=on_late, fallback=SHUT if on_late == OnLate.FALLBACK else None)
    gateway = _given(_Always(START), _vent("open", timing=timing, lateness=lateness))
    gateway.advance(START + HOUR)

    assert _ends(gateway) == ends


@pytest.mark.parametrize(("lead_s", "received"), [(0.0, START + HOUR), (1800.0, START + HOUR / 2)])
def test_an_action_is_sent_no_earlier_than_its_executors_lead_before_its_start(
    lead_s: float, received: datetime
) -> None:
    """Its window opening at 06:10, it starts at 07:00, the hourly executor's
    first instant in it: the assignment is sent then, or its lead before."""
    executor = _Receiving(START, lead_s=lead_s)
    window = Window(not_before=START + 10 * MINUTE, not_after=START + 3 * HOUR)
    gateway = _given(executor, _vent("open", timing=window))
    gateway.advance(START + 2 * HOUR)

    assert executor.received == {"open": received}
    assert _ends(gateway) == {"open": (OutcomeStatus.EXECUTED, START + HOUR)}


def test_a_start_reserved_holds_its_hand_until_it_is_sent() -> None:
    """One hand, a quarter of an hour's lead: the first action's start, an
    hour on, is reserved before it is sent, and the second, due then too,
    finds the hand taken."""
    executor = MemoryExecutor(
        START, lead_s=900.0, duration_s=HALF_AN_HOUR, longest_s=HALF_AN_HOUR, capacity=1
    )
    gateway = _given(executor, _vent("first"), _vent("second"))
    gateway.advance(START + 3 * HOUR)

    assert _ends(gateway) == {
        "first": (OutcomeStatus.EXECUTED, START + HOUR),
        "second": (OutcomeStatus.LATE, START + HOUR + HOUR / 2),
    }


def test_a_gateway_says_the_next_moment_it_has_something_to_do() -> None:
    """Due an hour on, both; the second, late for want of the hand, is
    reserved for when it comes free, half an hour after."""
    gateway = _given(_one_hand(), _vent("first"), _vent("second"))

    assert gateway.next_moment(START + 3 * HOUR) == START + HOUR
    assert gateway.next_moment(START + HOUR / 2) is None
    gateway.advance(START + HOUR)
    assert gateway.next_moment(START + 3 * HOUR) == START + HOUR + HOUR / 2
