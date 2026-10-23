"""A run's plan (decision 0046): timing, recurrence and lateness as a plan
can say them, and the plan refused whole when malformed."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from greenhouse_protocol.actions import ActionRef, Harvest, HarvestScope, Lower, SetLevel
from greenhouse_protocol.plan import (
    ActionKey,
    ActionState,
    ActionStateKind,
    Asap,
    At,
    Lateness,
    OnLate,
    Plan,
    PlannedAction,
    Principal,
    PrincipalKind,
    Recurrence,
    Window,
)
from greenhouse_protocol.run import RunEpoch

OPERATOR = Principal(kind=PrincipalKind.PERSON, id="operator")
EIGHT = datetime(2026, 3, 1, 8, tzinfo=UTC)
DAILY = Recurrence(period=timedelta(days=1), count=10)


def _planned(action_id: str, *, after: tuple[str, ...] = (), **fields: object) -> PlannedAction:
    defaults: dict[str, object] = dict(
        action_id=action_id,
        action=SetLevel(device_id="vent_1", level=1.0),
        timing=At(at=EIGHT),
        after=after,
        proposed_by=OPERATOR,
    )
    defaults.update(fields)
    return PlannedAction.model_validate(defaults)


def _plan(*actions: PlannedAction) -> Plan:
    return Plan(plan_id="morning", run_id="run_1", epoch=0, revision=1, actions=actions)


def test_a_plan_of_ordered_and_side_by_side_actions() -> None:
    plan = _plan(
        _planned("harvest", action=Harvest(plant_id="p30", scope=HarvestScope.RIPE)),
        _planned("lower", action=Lower(plant_id="p30", by_internodes=2), after=("harvest",)),
        _planned("vent", timing=Window(not_before=EIGHT, not_after=EIGHT + timedelta(hours=1))),
    )

    assert Plan.model_validate_json(plan.model_dump_json()) == plan


def test_a_window_may_not_close_before_it_opens() -> None:
    with pytest.raises(ValidationError, match="closes no earlier than it opens"):
        Window(not_before=EIGHT, not_after=EIGHT - timedelta(minutes=1))


@pytest.mark.parametrize(
    "fields",
    [
        dict(period=timedelta(0), count=3),
        dict(period=timedelta(days=-1), count=3),
        dict(period=timedelta(days=1)),
        dict(period=timedelta(days=1), count=3, until=EIGHT),
        dict(period=timedelta(days=1), count=0),
    ],
)
def test_a_recurrence_has_a_positive_period_and_one_end(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Recurrence.model_validate(fields)


def test_a_recurrence_needs_an_anchor_and_ends_after_it() -> None:
    with pytest.raises(ValidationError, match="no deadline to move"):
        _planned("vent", timing=Asap(), every=DAILY)
    with pytest.raises(ValidationError, match="until before its first occurrence"):
        _planned(
            "vent", every=Recurrence(period=timedelta(days=1), until=EIGHT - timedelta(days=1))
        )
    assert _planned("vent", timing=Asap(deadline=EIGHT), every=DAILY).anchor() == EIGHT


@pytest.mark.parametrize(
    "lateness",
    [
        dict(on_late=OnLate.FALLBACK),
        dict(on_late=OnLate.SKIP, fallback=SetLevel(device_id="vent_1", level=0.0)),
        dict(on_late=OnLate.CRITICAL, fallback=SetLevel(device_id="vent_1", level=0.0)),
        dict(tolerance_s=-1),
    ],
)
def test_a_fallback_comes_with_its_choice_only(lateness: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Lateness.model_validate(lateness)


def test_critical_is_one_choice_among_the_others() -> None:
    critical = Lateness(tolerance_s=2, on_late=OnLate.CRITICAL)

    assert critical.on_late == OnLate.CRITICAL
    assert Lateness(on_late=OnLate.FALLBACK, fallback=SetLevel(device_id="v", level=0)).fallback


@pytest.mark.parametrize(
    "actions, reason",
    [
        ((_planned("vent"), _planned("vent")), "more than once"),
        ((_planned("lower", after=("harvest",)),), "not in the plan"),
        (
            (_planned("a", after=("c",)), _planned("b", after=("a",)), _planned("c", after=("b",))),
            "wait for each other",
        ),
        (
            (_planned("once", after=("daily",)), _planned("daily", every=DAILY)),
            "which occurrence is not said",
        ),
        (
            (
                _planned("lower", every=DAILY, after=("harvest",)),
                _planned("harvest", every=Recurrence(period=timedelta(days=2), count=10)),
            ),
            "recur differently",
        ),
    ],
)
def test_a_malformed_plan_is_refused_whole(actions: tuple[PlannedAction, ...], reason: str) -> None:
    with pytest.raises(ValidationError, match=reason):
        _plan(*actions)


def test_an_action_waits_for_another_once_and_never_for_itself() -> None:
    with pytest.raises(ValidationError, match="waits for itself"):
        _planned("vent", after=("vent",))
    with pytest.raises(ValidationError, match="more than once"):
        _planned("lower", after=("vent", "vent"))


def test_recurring_actions_alike_pair_their_occurrences() -> None:
    plan = _plan(
        _planned("harvest", every=DAILY),
        _planned("lower", every=DAILY, after=("harvest",)),
        _planned("check", timing=At(at=EIGHT - timedelta(hours=1))),
        _planned("vent", every=DAILY, after=("check",)),
    )

    assert [planned.action_id for planned in plan.actions] == ["harvest", "lower", "check", "vent"]


def test_a_long_chain_is_checked_without_a_deep_stack() -> None:
    chain = [_planned("a0")] + [_planned(f"a{n}", after=(f"a{n - 1}",)) for n in range(1, 3000)]

    assert len(_plan(*chain).actions) == 3000
    with pytest.raises(ValidationError, match="wait for each other"):
        _plan(_planned("a0", after=("a2999",)), *chain[1:])


@pytest.mark.parametrize(
    "fields", [dict(epoch=-1), dict(revision=0), dict(plan_id="morning@1"), dict(run_id="")]
)
def test_a_plan_names_its_run_epoch_and_revision(fields: dict[str, object]) -> None:
    document: dict[str, object] = dict(plan_id="morning", run_id="run_1", epoch=0, revision=1)
    document.update(fields)

    with pytest.raises(ValidationError):
        Plan.model_validate({**document, "actions": ()})


def test_an_action_key_and_an_action_as_it_stands() -> None:
    key = ActionKey(plan_id="morning", epoch=1, revision=2, ref=ActionRef(action_id="harvest"))
    state = ActionState(
        plan_id="morning",
        revision=2,
        ref=ActionRef(action_id="lower"),
        action=Lower(plant_id="p30", by_internodes=2),
        timing=Asap(),
        principal=OPERATOR,
        state=ActionStateKind.WAITING,
        waiting_for=(key.ref,),
        carried_from=RunEpoch(run_id="run_1", epoch=0),
    )

    assert ActionState.model_validate_json(state.model_dump_json()) == state
    assert ActionKey.model_validate_json(key.model_dump_json()) == key
