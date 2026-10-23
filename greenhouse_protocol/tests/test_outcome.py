"""One outcome record per planned action (decision 0046): its fields agree
with its status."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from greenhouse_protocol.actions import (
    Action,
    ActionRef,
    Harvest,
    HarvestScope,
    RemoveLeaf,
    SetLevel,
    SetTarget,
)
from greenhouse_protocol.outcome import (
    ActionEffect,
    ActionOutcome,
    Harvested,
    LeafRemoved,
    LevelSet,
    OutcomeStatus,
    TargetSet,
)
from greenhouse_protocol.plan import Asap, At, ExecutorKind, ExecutorRef, Principal, PrincipalKind

OPERATOR = Principal(kind=PrincipalKind.PERSON, id="operator")
ROBOT = ExecutorRef(kind=ExecutorKind.ROBOT, id="picker_1")
TEN = datetime(2026, 3, 1, 10, tzinfo=UTC)
MINUTE = timedelta(minutes=1)


def _outcome(status: OutcomeStatus, **fields: object) -> ActionOutcome:
    document: dict[str, object] = dict(
        outcome_id="o1",
        greenhouse_id="gh_reference",
        run_id="run_1",
        epoch=0,
        plan_id="morning",
        revision=1,
        ref=ActionRef(action_id="harvest"),
        action=Harvest(plant_id="p30", scope=HarvestScope.RIPE),
        timing=At(at=TEN),
        principal=OPERATOR,
        status=status,
        due=TEN,
        resolved_at=TEN + MINUTE,
    )
    document.update(fields)
    return ActionOutcome.model_validate(document)


RAN = dict(started_at=TEN, finished_at=TEN + MINUTE, executor=ROBOT)


def test_an_outcome_of_each_status() -> None:
    outcomes = [
        _outcome(OutcomeStatus.EXECUTED, **RAN, effect=Harvested(fruit_count=4, fresh_mass_g=180)),
        _outcome(OutcomeStatus.LATE, **RAN),
        _outcome(
            OutcomeStatus.MISSED,
            reason="late",
            fallback=ActionRef(action_id="harvest", fallback=True),
        ),
        _outcome(OutcomeStatus.REFUSED, reason="not authorised"),
        _outcome(OutcomeStatus.FAILED, reason="the arm stalled", started_at=TEN, executor=ROBOT),
        _outcome(OutcomeStatus.CANCELLED, reason="cancelled", cancelled_by=OPERATOR),
        _outcome(OutcomeStatus.SUPERSEDED, reason="revision 2", cancelled_by=OPERATOR),
        _outcome(OutcomeStatus.UNCONFIRMED, reason="no report", executor=ROBOT),
    ]

    for outcome in outcomes:
        assert ActionOutcome.model_validate_json(outcome.model_dump_json()) == outcome


@pytest.mark.parametrize(
    "status, fields, reason",
    [
        (OutcomeStatus.EXECUTED, dict(started_at=TEN, finished_at=TEN + MINUTE), "executor"),
        (OutcomeStatus.LATE, dict(executor=ROBOT), "its start, its finish"),
        (OutcomeStatus.REFUSED, {}, "says why"),
        (OutcomeStatus.CANCELLED, dict(reason="  "), "says why"),
        (OutcomeStatus.MISSED, dict(reason="late", started_at=TEN), "never started"),
        (OutcomeStatus.REFUSED, dict(reason="no", executor=ROBOT), "never started"),
        (OutcomeStatus.REFUSED, dict(reason="no", cancelled_by=OPERATOR), "not cancelled"),
        (
            OutcomeStatus.CANCELLED,
            dict(reason="no", fallback=ActionRef(action_id="h", fallback=True)),
            "no fallback",
        ),
        (
            OutcomeStatus.FAILED,
            dict(
                reason="no",
                started_at=TEN,
                executor=ROBOT,
                effect=Harvested(fruit_count=1, fresh_mass_g=5),
            ),
            "no effect",
        ),
        (
            OutcomeStatus.EXECUTED,
            {**RAN, "effect": LevelSet(device_id="vent_1", level=1.0)},
            "effect is harvested",
        ),
        (OutcomeStatus.REFUSED, dict(reason="no", due=None), "has no due"),
        (OutcomeStatus.FAILED, dict(reason="stalled"), "was attempted"),
        (OutcomeStatus.FAILED, dict(reason="stalled", started_at=TEN), "was attempted"),
        (OutcomeStatus.REFUSED, dict(reason="no", finished_at=TEN), "that finished started"),
        (
            OutcomeStatus.MISSED,
            dict(reason="late", fallback=ActionRef(action_id="other", fallback=True)),
            "fallback is harvest/fallback",
        ),
        (
            OutcomeStatus.MISSED,
            dict(reason="late", fallback=ActionRef(action_id="harvest")),
            "fallback is harvest/fallback",
        ),
        (
            OutcomeStatus.MISSED,
            dict(
                reason="late",
                ref=ActionRef(action_id="harvest", fallback=True),
                fallback=ActionRef(action_id="harvest", fallback=True),
            ),
            "fallback is",
        ),
        (
            OutcomeStatus.EXECUTED,
            {**RAN, "finished_at": TEN - MINUTE},
            "finished no earlier than it is started",
        ),
        (
            OutcomeStatus.EXECUTED,
            {**RAN, "resolved_at": TEN},
            "resolved no earlier than it is finished",
        ),
        (
            OutcomeStatus.REFUSED,
            dict(reason="no", delivered_at=TEN),
            "delivered no earlier than it is resolved",
        ),
    ],
)
def test_an_outcome_agrees_with_its_status(
    status: OutcomeStatus, fields: dict[str, object], reason: str
) -> None:
    with pytest.raises(ValidationError, match=reason):
        _outcome(status, **fields)


def test_only_an_as_soon_as_possible_action_dropped_before_it_starts_has_no_due() -> None:
    dropped = _outcome(
        OutcomeStatus.SUPERSEDED,
        timing=Asap(),
        due=None,
        reason="revision 2",
        cancelled_by=OPERATOR,
    )

    assert dropped.due is None
    with pytest.raises(ValidationError, match="has no due"):
        _outcome(OutcomeStatus.EXECUTED, **RAN, timing=Asap(), due=None)


@pytest.mark.parametrize(
    "action, effect",
    [
        (SetLevel(device_id="vent_1", level=1.0), LevelSet(device_id="heater", level=1.0)),
        (
            SetTarget(target="heating_day", value_c=20),
            TargetSet(target="heating_night", value_c=20),
        ),
        (RemoveLeaf(plant_id="p30", leaf_id="l1"), LeafRemoved(leaf_id="l2")),
    ],
)
def test_an_effect_acts_on_what_its_action_does(action: Action, effect: ActionEffect) -> None:
    with pytest.raises(ValidationError, match="acts on what its action does"):
        _outcome(OutcomeStatus.EXECUTED, **RAN, action=action, effect=effect)


def test_an_outcome_names_its_greenhouse_and_carries_its_action() -> None:
    outcome = _outcome(
        OutcomeStatus.EXECUTED,
        **RAN,
        action=SetLevel(device_id="vent_1", level=0.5),
        effect=LevelSet(device_id="vent_1", level=0.5),
    )

    assert outcome.greenhouse_id == "gh_reference"
    assert outcome.action == SetLevel(device_id="vent_1", level=0.5)
    with pytest.raises(ValidationError):
        _outcome(OutcomeStatus.REFUSED, reason="no", greenhouse_id="")
