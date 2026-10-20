"""The consumer interface's rules, each exercised against a batch that
breaks it (`greenhouse_protocol.contracts.consumer`)."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from greenhouse_protocol.contracts.consumer import (
    CONSUMER_INTERFACE_VERSION,
    EventBatch,
    ObservationBatch,
    RunClock,
    RunDescriptor,
    check_batch,
    check_polls,
    check_run,
    delivered_at,
)
from greenhouse_protocol.enums import EventSource, EventType, ObservationType, SourceType
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
NOW = START + timedelta(days=1)
SOURCE = RecordSource(type=SourceType.SIMULATION, source_id="run_1")


def _observation(index: int, taken: datetime, delivered: datetime | None = None) -> Observation:
    return Observation(
        observation_id=f"obs_{index}",
        greenhouse_id="gh",
        plant_id=None,
        timestamp=taken,
        observation_type=ObservationType.AIR_TEMPERATURE_C,
        value=20.0 + index,
        source=SOURCE,
        sensor_id="air_1",
        delivered_at=delivered,
    )


def _event(index: int, taken: datetime) -> Event:
    return Event(
        event_id=f"evt_{index}",
        greenhouse_id="gh",
        plant_id=None,
        timestamp=taken,
        event_type=EventType.WATERING,
        source=EventSource.CONTROL_SYSTEM,
    )


def _batch(
    records: tuple[Observation, ...],
    *,
    after: int = 0,
    next: int | None = None,
    epoch: int = 0,
    now: datetime = NOW,
) -> ObservationBatch:
    return ObservationBatch(
        run_id="run_1",
        epoch=epoch,
        after=after,
        next=after + len(records) if next is None else next,
        simulated_now=now,
        observations=records,
    )


def _run(**overrides: object) -> RunDescriptor:
    fields: dict[str, object] = dict(
        run_id="run_1",
        epoch=0,
        greenhouse_id="gh",
        started_at=START,
        clock=RunClock(simulated_now=NOW, day=1, playing=True),
    )
    fields.update(overrides)
    return RunDescriptor.model_validate(fields)


def test_a_run_descriptor_speaks_the_interface_version_by_default() -> None:
    assert _run().interface_version == CONSUMER_INTERFACE_VERSION
    assert check_run(_run()) == []


def test_a_run_that_reads_before_it_started_is_refused() -> None:
    run = _run(clock=RunClock(simulated_now=START - timedelta(hours=1), day=0, playing=False))

    assert check_run(run) == [
        "run 'run_1' epoch 0 reads 2026-03-01T11:00:00+00:00, "
        "before it started (2026-03-01T12:00:00+00:00)"
    ]


def test_another_interface_version_is_a_violation() -> None:
    assert check_run(_run(interface_version="v2")) == [
        "run 'run_1' speaks interface 'v2', not 'v1'"
    ]


def test_a_batch_refuses_negative_cursors_and_naive_clocks() -> None:
    with pytest.raises(ValidationError):
        _batch((), after=-1)
    with pytest.raises(ValidationError):
        _batch((), now=datetime(2026, 3, 2, 12, 0))


def test_a_conforming_batch_has_no_violations() -> None:
    records = (_observation(1, START), _observation(2, START, START + timedelta(seconds=30)))

    assert check_batch(_batch(records)) == []


def test_delivery_is_the_delivery_time_or_the_instant_taken() -> None:
    late = START + timedelta(hours=2)

    assert delivered_at(_observation(1, START)) == START
    assert delivered_at(_observation(1, START, late)) == late
    assert delivered_at(_event(1, START)) == START


def test_positions_must_be_dense() -> None:
    records = (_observation(1, START), _observation(2, START))

    assert check_batch(_batch(records, after=3, next=6)) == [
        "observations batch of run 'run_1' epoch 0 after=3 holds 2 record(s) "
        "but moves the cursor by 3: positions must be dense"
    ]
    assert check_batch(_batch(records, after=3, next=2)) == [
        "observations batch of run 'run_1' epoch 0 after=3 goes backwards: next 2 < after 3"
    ]


def test_records_come_in_delivery_order() -> None:
    later_first = (_observation(1, START, START + timedelta(hours=1)), _observation(2, START))

    assert check_batch(_batch(later_first)) == [
        "observations batch of run 'run_1' epoch 0 after=0 is out of delivery order at 'obs_2': "
        "2026-03-01T12:00:00+00:00 after 2026-03-01T13:00:00+00:00"
    ]


def test_nothing_is_delivered_after_the_batch_s_clock() -> None:
    future = (_observation(1, START, NOW + timedelta(seconds=1)),)

    assert check_batch(_batch(future)) == [
        "observations batch of run 'run_1' epoch 0 after=0 delivers 'obs_1' at "
        "2026-03-02T12:00:01+00:00, after its clock (2026-03-02T12:00:00+00:00)"
    ]


def test_a_batch_s_records_pass_the_record_checks() -> None:
    nan = _observation(1, START).model_copy(update={"value": float("nan")})

    assert check_batch(_batch((nan,))) == [
        "observation 'obs_1' has a non-finite value (nan): a gap is an absent record, not a NaN"
    ]


def test_event_batches_are_checked_the_same_way() -> None:
    batch = EventBatch(
        run_id="run_1",
        epoch=0,
        after=0,
        next=1,
        simulated_now=NOW,
        events=(_event(1, START),),
    )

    assert check_batch(batch) == []
    assert batch.records == batch.events


def test_consecutive_polls_that_follow_the_cursor_conform() -> None:
    first = _batch((_observation(1, START), _observation(2, START)))
    second = _batch((_observation(3, NOW),), after=first.next)
    empty = _batch((), after=second.next)

    assert check_polls([first, second, empty]) == []


def test_a_repoll_extends_what_was_delivered_but_never_rewrites_it() -> None:
    early = _batch((_observation(1, START),), now=START)
    extended = _batch((_observation(1, START), _observation(2, NOW)))
    rewritten = _batch((_observation(9, START), _observation(2, NOW)))

    assert check_polls([early, extended]) == []
    assert check_polls([early, rewritten]) == [
        "observations batch of run 'run_1' epoch 0 after=0 (poll 1) rewrites the log at "
        "position 1: 'obs_9' is not the record delivered there before ('obs_1')"
    ]


def test_a_repoll_cut_shorter_by_its_limit_is_not_a_rewrite() -> None:
    full = _batch((_observation(1, START), _observation(2, START), _observation(3, NOW)))
    cut = _batch((_observation(1, START),), next=1).model_copy(update={"has_more": True})

    assert check_polls([full, cut]) == []
    assert check_polls([cut, full]) == []


def test_a_repoll_that_changes_a_record_is_a_rewrite_even_with_the_same_id() -> None:
    early = _batch((_observation(1, START),), now=START)
    changed = _batch((_observation(1, START).model_copy(update={"value": 99.0}),), now=START)

    assert check_polls([early, changed]) == [
        "observations batch of run 'run_1' epoch 0 after=0 (poll 1) rewrites the log at "
        "position 1: 'obs_1' is not the record delivered there before ('obs_1')"
    ]


def test_a_position_first_seen_from_another_cursor_is_held_to_as_well() -> None:
    first = _batch((_observation(1, START),), now=START)
    second = _batch((_observation(2, START),), after=first.next, now=START)
    replaced = _batch((_observation(1, START), _observation(3, START)), now=START)

    assert check_polls([first, second, replaced]) == [
        "observations batch of run 'run_1' epoch 0 after=0 (poll 2) rewrites the log at "
        "position 2: 'obs_3' is not the record delivered there before ('obs_2')"
    ]


def test_delivery_order_holds_across_consecutive_batches() -> None:
    first = _batch((_observation(1, START), _observation(2, START, START + timedelta(hours=2))))
    later = _batch((_observation(3, START, START + timedelta(hours=1)),), after=first.next)

    assert check_polls([first, later]) == [
        "observations batch of run 'run_1' epoch 0 after=2 (poll 1) is out of delivery order "
        "across batches: 'obs_3' at position 3 (2026-03-01T13:00:00+00:00) was delivered "
        "before position 2 (2026-03-01T14:00:00+00:00)"
    ]


def test_a_record_is_never_delivered_twice_in_an_epoch() -> None:
    first = _batch((_observation(1, START), _observation(2, START)))
    again = _batch((_observation(2, START), _observation(3, NOW)), after=first.next)

    assert check_polls([first, again]) == [
        "observations batch of run 'run_1' epoch 0 after=2 (poll 1) delivers 'obs_2' again, "
        "at position 3 after position 2"
    ]


def test_a_non_empty_batch_answers_only_a_cursor_the_producer_gave() -> None:
    first = _batch((_observation(1, START), _observation(2, START)))
    from_nowhere = _batch((_observation(5, NOW),), after=4)

    assert check_polls([first, from_nowhere]) == [
        "observations batch of run 'run_1' epoch 0 after=4 (poll 1) answers after=4, "
        "a cursor the producer never gave in this epoch"
    ]


def test_an_epoch_never_decreases_and_a_new_one_starts_the_log_over() -> None:
    first = _batch((_observation(1, START), _observation(2, START)), epoch=0)
    stale = _batch((), after=first.next, epoch=1)
    restarted = _batch((_observation(1, START), _observation(2, START)), epoch=1)
    backwards = _batch((), epoch=0)

    assert check_polls([first, stale, restarted]) == []
    assert check_polls([first, stale, restarted, backwards]) == [
        "observations batch of run 'run_1' epoch 0 after=0 (poll 3) returns to epoch 0"
    ]


def test_the_clock_never_turns_back_within_an_epoch() -> None:
    later = _batch((), now=NOW)
    earlier = _batch((), now=START)
    restarted = _batch((), now=START, epoch=1)

    assert check_polls([later, restarted]) == []
    assert check_polls([later, earlier]) == [
        "observations batch of run 'run_1' epoch 0 after=0 (poll 1) turns the clock back "
        "within epoch 0: 2026-03-01T12:00:00+00:00 after 2026-03-02T12:00:00+00:00; "
        "a timeline that starts over is a new epoch"
    ]


def test_a_batch_holds_records_of_the_run_s_greenhouse_only() -> None:
    stranger = _observation(2, START).model_copy(update={"greenhouse_id": "other"})
    batch = _batch((_observation(1, START), stranger))
    violation = (
        "observations batch of run 'run_1' epoch 0 after=0 delivers 'obs_2' of greenhouse "
        "'other', not the run's ('gh')"
    )

    assert check_batch(batch) == []
    assert check_batch(batch, greenhouse_id="gh") == [violation]
    assert check_polls([batch], greenhouse_id="gh") == [violation]


def test_polls_of_several_runs_do_not_belong_together() -> None:
    first = _batch((_observation(1, START),))
    other = first.model_copy(update={"run_id": "run_2"})

    assert check_polls([first, other]) == ["the polls name several runs: ['run_1', 'run_2']"]
