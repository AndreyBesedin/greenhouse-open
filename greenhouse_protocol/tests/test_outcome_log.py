"""The outcome log, a third log of the consumer interface (decision 0046),
and the receipts a gateway gives: what they must hold."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from greenhouse_protocol.actions import ActionRef, SetLevel
from greenhouse_protocol.contracts.conformance import check_outcomes
from greenhouse_protocol.contracts.consumer import (
    OutcomeBatch,
    check_batch,
    check_polls,
    delivered_at,
    record_id,
)
from greenhouse_protocol.contracts.gateway import Receipt
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import ActionKey, At, Principal, PrincipalKind

OPERATOR = Principal(kind=PrincipalKind.PERSON, id="operator")
TEN = datetime(2026, 3, 1, 10, tzinfo=UTC)
MINUTE = timedelta(minutes=1)


def _refused(outcome_id: str, action_id: str, at: datetime, **fields: object) -> ActionOutcome:
    document: dict[str, object] = dict(
        outcome_id=outcome_id,
        greenhouse_id="gh_1",
        run_id="run_1",
        epoch=0,
        plan_id="p",
        revision=1,
        ref=ActionRef(action_id=action_id),
        action=SetLevel(device_id="vent_1", level=1.0),
        timing=At(at=at),
        principal=OPERATOR,
        status=OutcomeStatus.REFUSED,
        due=at,
        resolved_at=at,
        reason="not authorised",
    )
    document.update(fields)
    return ActionOutcome.model_validate(document)


def _batch(
    *outcomes: ActionOutcome, after: int = 0, now: datetime = TEN + 10 * MINUTE
) -> OutcomeBatch:
    return OutcomeBatch(
        run_id="run_1",
        epoch=0,
        after=after,
        next=after + len(outcomes),
        simulated_now=now,
        outcomes=outcomes,
    )


def test_an_outcome_is_delivered_when_resolved_or_when_it_reached_the_log() -> None:
    resolved = _refused("o1", "a", TEN)
    delivered = _refused("o2", "b", TEN, delivered_at=TEN + MINUTE)

    assert delivered_at(resolved) == TEN
    assert delivered_at(delivered) == TEN + MINUTE
    assert record_id(resolved) == "o1"


def test_a_conforming_outcome_batch_has_no_violations() -> None:
    batch = _batch(_refused("o1", "a", TEN), _refused("o2", "b", TEN + MINUTE))

    assert check_batch(batch, greenhouse_id="gh_1") == []
    assert check_polls([batch, _batch(after=2)], greenhouse_id="gh_1") == []


def test_an_outcome_batch_is_held_to_the_logs_rules() -> None:
    out_of_order = _batch(_refused("o1", "a", TEN + MINUTE), _refused("o2", "b", TEN))
    late = _batch(_refused("o1", "a", TEN + MINUTE), now=TEN)
    other_greenhouse = _batch(_refused("o1", "a", TEN, greenhouse_id="gh_2"))

    assert any("delivery order" in v for v in check_batch(out_of_order))
    assert any("after its clock" in v for v in check_batch(late))
    assert any("not the run's" in v for v in check_batch(other_greenhouse, greenhouse_id="gh_1"))


def test_each_action_ends_once_in_a_revision() -> None:
    twice = [_refused("o1", "a", TEN), _refused("o2", "a", TEN)]
    same_id = [_refused("o1", "a", TEN), _refused("o1", "b", TEN)]
    replaced = [_refused("o1", "a", TEN), _refused("o2", "a", TEN, revision=2)]

    assert check_outcomes(twice) == ["a of plan 'p' revision 1 in epoch 0 ends 2 times"]
    assert check_outcomes(same_id) == ["outcome 'o1' appears 2 times"]
    assert check_outcomes(replaced) == []
    assert check_batch(_batch(*twice)) == ["a of plan 'p' revision 1 in epoch 0 ends 2 times"]


def test_a_receipt_is_accepted_exactly_when_it_has_no_errors() -> None:
    key = ActionKey(plan_id="p", epoch=0, revision=1, ref=ActionRef(action_id="a"))

    assert Receipt(accepted=True, sequence=3, refused=(ActionRef(action_id="a"),)).sequence == 3
    assert Receipt(accepted=True, stale=(key,), not_permitted=(key,)).stale == (key,)
    assert Receipt(accepted=False, errors=("stale",)).errors == ("stale",)
    with pytest.raises(ValidationError, match="exactly when it has no errors"):
        Receipt(accepted=True, errors=("stale",))
    with pytest.raises(ValidationError, match="exactly when it has no errors"):
        Receipt(accepted=False)
    with pytest.raises(ValidationError, match="refused and cancelled nothing"):
        Receipt(accepted=False, errors=("stale",), cancelled=(ActionRef(action_id="a"),))


def test_an_action_ends_once_however_its_log_is_paged() -> None:
    """Two outcomes of one action, each in a page of its own (#326's
    review): the polls together are refused, as one batch holding both is;
    a repoll of the same position, or a new epoch's outcome, is not."""
    first = _refused("o1", "vent", TEN)
    twin = _refused("o2", "vent", TEN + MINUTE)
    paged = [_batch(first), _batch(twin, after=1)]

    assert check_polls(paged) == [
        "outcomes batch of run 'run_1' epoch 0 after=1 (poll 1) ends vent of plan 'p' "
        "revision 1 again, at position 2 after position 1"
    ]
    assert check_polls([_batch(first), _batch(first)]) == []
    started_over = OutcomeBatch(
        run_id="run_1",
        epoch=1,
        after=0,
        next=1,
        simulated_now=TEN + 10 * MINUTE,
        outcomes=(twin.model_copy(update={"epoch": 1}),),
    )
    assert check_polls([_batch(first), started_over]) == []
