"""The arithmetic a measure's definition implies (P25, decision 0081), on
plain series, so that a value can be worked out from its definition by
anyone, and by hand.

- **A quantity through time** is its samples, `(moment, value)`, the moment
  in seconds from the run's start, in strictly increasing order. Between
  its samples it is taken as its definition says (`BetweenSamples.HELD`:
  each value holds until the next sample, the last until the window's end).
- **Amounts** are given at moments, such as a minute's heat or a harvest's
  fruit: `(moment, amount)`.
- **The window** is its intervals, `[from, to)` in seconds, in order and
  apart: the measure's window, and, for a measure against a goal, only the
  hours its goal holds in. Working them out from a benchmark's warm-up and
  a goal's hours is its evaluator's.

`series_value` gives an instrument's measure of one series, such as one
device's levels; `record_values` a record's measure of an episode's record;
and `priced_value` a priced score of the values of the measures it weighs,
at its benchmark's prices. Each refuses a definition it is not for.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Mapping, Sequence
from itertools import islice, pairwise
from math import floor
from typing import Final

from greenhouse_protocol.benchmark import (
    AGAINST_A_GOAL,
    Aggregation,
    BetweenSamples,
    By,
    FromInstrument,
    FromMeasures,
    FromRecord,
    MeasureDefinition,
    MeasureNamed,
    MeasureValue,
    NotComparable,
    Per,
    RecordField,
)
from greenhouse_protocol.context import Goal, GoalSense
from greenhouse_protocol.experiment import EpisodeRecord
from greenhouse_protocol.outcome import OutcomeStatus

SECONDS_PER_HOUR: Final = 3600.0
SECONDS_PER_DAY: Final = 86400.0

type Sample = tuple[float, float]
type Interval = tuple[float, float]


def _check_window(within: Sequence[Interval]) -> None:
    previous_end = float("-inf")
    for start, end in within:
        if not previous_end <= start <= end:
            raise ValueError(
                "a window's intervals are in order, apart, and each ends after it starts"
            )
        previous_end = end


def _sample_times(samples: Sequence[Sample]) -> list[float]:
    times = [moment for moment, _ in samples]
    if any(later <= earlier for earlier, later in pairwise(times)):
        raise ValueError("a quantity's samples are in strictly increasing time")
    return times


def held(samples: Sequence[Sample], within: Sequence[Interval]) -> Iterator[tuple[float, float]]:
    """The quantity through its window, as pieces `(seconds, value)`, each
    sample's value held until the next. Its value at each interval's start
    is its last sample's at or before it: a quantity with none is refused."""
    _check_window(within)
    times = _sample_times(samples)
    for start, end in within:
        last = bisect_right(times, start) - 1
        if last < 0:
            raise ValueError(f"the quantity has no value at {start} s, where its window starts")
        at, value = start, samples[last][1]
        for moment, next_value in islice(samples, last + 1, None):
            if moment >= end:
                break
            yield moment - at, value
            at, value = moment, next_value
        yield end - at, value


def _outside(value: float, goal: Goal) -> float:
    """How far a value is outside its goal's bounds: 0 on a bound or within."""
    if goal.low is not None and value < goal.low:
        return goal.low - value
    if goal.high is not None and value > goal.high:
        return value - goal.high
    return 0.0


def _check_goal(goal: Goal) -> None:
    if goal.sense != GoalSense.WITHIN:
        raise ValueError(f"goal {goal.goal_id!r} is not a constraint, and has no bounds")


def hours_outside(samples: Sequence[Sample], within: Sequence[Interval], goal: Goal) -> float:
    """The hours the quantity is outside its goal's bounds."""
    _check_goal(goal)
    return sum(s for s, value in held(samples, within) if _outside(value, goal)) / SECONDS_PER_HOUR


def integral_outside(samples: Sequence[Sample], within: Sequence[Interval], goal: Goal) -> float:
    """How far outside its goal's bounds the quantity is, integrated through
    time, in its unit-hours: 2 K under a band for 3 h is 6 K·h."""
    _check_goal(goal)
    return sum(s * _outside(value, goal) for s, value in held(samples, within)) / SECONDS_PER_HOUR


def integral(samples: Sequence[Sample], within: Sequence[Interval]) -> float:
    """The quantity integrated through time, in its unit-hours: a device at
    half its level for 4 h is 2 level-hours."""
    return sum(s * value for s, value in held(samples, within)) / SECONDS_PER_HOUR


def changes(samples: Sequence[Sample], within: Sequence[Interval]) -> int:
    """The times the quantity changes value within its window: each sample
    within it whose value is not the one before it. A first sample, with
    none before it, is where the quantity starts, not a change."""
    _check_window(within)
    times = _sample_times(samples)
    count = 0
    for start, end in within:
        first = max(bisect_left(times, start), 1)
        for index in range(first, bisect_left(times, end)):
            count += samples[index][1] != samples[index - 1][1]
    return count


def total(amounts: Sequence[Sample], within: Sequence[Interval]) -> float:
    """The amounts given at moments within the window, summed."""
    _check_window(within)
    return sum(
        amount for moment, amount in amounts if any(start <= moment < end for start, end in within)
    )


def quantile(values: Sequence[float], q: float) -> float:
    """A quantile of the values, by linear interpolation between the closest
    ranks: 0.5 the median, 1 the largest."""
    if not values:
        raise ValueError("a quantile of no values")
    if not 0 <= q <= 1:
        raise ValueError(f"a quantile is between 0 and 1, not {q}")
    ranked = sorted(values)
    rank = (len(ranked) - 1) * q
    below = floor(rank)
    if below == len(ranked) - 1:
        return ranked[below]
    return ranked[below] + (rank - below) * (ranked[below + 1] - ranked[below])


def _days(within: Sequence[Interval]) -> float:
    return sum(end - start for start, end in within) / SECONDS_PER_DAY


def series_value(
    definition: MeasureDefinition,
    samples: Sequence[Sample],
    within: Sequence[Interval],
    *,
    goal: Goal | None = None,
    floor_area_m2: float | None = None,
) -> float:
    """An instrument's measure of one series over its window, divided by its
    denominators: the house's floor area, given, and the window's days. The
    series is in the measure's unit times its denominators: MJ for a heat
    given in MJ m⁻², a level from 0 to 1 for level-hours. A measure against
    a goal is given its benchmark's goal, by the id it names."""
    if not isinstance(definition.source, FromInstrument):
        raise ValueError(f"{definition.name!r} is not made from an instrument's series")
    if definition.aggregation in AGAINST_A_GOAL and (
        goal is None or goal.goal_id != definition.goal
    ):
        raise ValueError(f"{definition.name!r} is scored against goal {definition.goal!r}")
    if definition.between_samples not in {None, BetweenSamples.HELD}:
        raise ValueError(f"no arithmetic between samples {definition.between_samples!r}")
    match definition.aggregation:
        case Aggregation.TOTAL:
            value = total(samples, within)
        case Aggregation.INTEGRAL:
            value = integral(samples, within)
        case Aggregation.HOURS_OUTSIDE if goal is not None:
            value = hours_outside(samples, within, goal)
        case Aggregation.INTEGRAL_OUTSIDE if goal is not None:
            value = integral_outside(samples, within, goal)
        case Aggregation.CHANGES:
            value = float(changes(samples, within))
        case aggregation:
            raise ValueError(f"no arithmetic for a series by {aggregation!r}")
    if Per.FLOOR_M2 in definition.per:
        if floor_area_m2 is None or floor_area_m2 <= 0:
            raise ValueError(f"{definition.name!r} is per m² of floor: give the floor's area")
        value /= floor_area_m2
    if Per.DAY in definition.per:
        days = _days(within)
        if days <= 0:
            raise ValueError(f"{definition.name!r} is per day, over a window of no time")
        value /= days
    return value


def record_values(
    definition: MeasureDefinition, record: EpisodeRecord
) -> dict[str | None, MeasureValue]:
    """A record's measure of an episode's record: one value, under None, or
    one for each part it is broken down by, every status of an outcome's
    included."""
    if not isinstance(definition.source, FromRecord) or definition.per:
        raise ValueError(f"{definition.name!r} is not made from the record alone")
    match definition.source.field, definition.aggregation, definition.by:
        case RecordField.OUTCOME_STATUS, Aggregation.COUNT, By.STATUS:
            statuses = [outcome.status for outcome in record.outcomes]
            return {status.value: float(statuses.count(status)) for status in OutcomeStatus}
        case RecordField.DECISION_SKIPPED, Aggregation.COUNT, None:
            return {None: float(sum(decision.skipped for decision in record.trace))}
        case RecordField.DECISION_TIME, Aggregation.QUANTILE, None if (
            definition.quantile is not None
        ):
            times = [decision.took_s for decision in record.trace]
            if not times:
                return {None: NotComparable(not_comparable="the episode made no decision")}
            return {None: quantile(times, definition.quantile)}
        case field, aggregation, by:
            raise ValueError(f"no arithmetic for {field} by {aggregation}, broken down by {by}")


def priced_value(
    definition: MeasureDefinition,
    values: Mapping[MeasureNamed, MeasureValue],
    prices: Mapping[str, float],
) -> MeasureValue:
    """A priced score: each measure it weighs times its price, summed. Not
    comparable when a measure it weighs is not, and refused when a measure
    or a price it names is not given."""
    if not isinstance(definition.source, FromMeasures):
        raise ValueError(f"{definition.name!r} is not a priced score")
    score = 0.0
    for term in definition.source.terms:
        if term.measure not in values:
            raise ValueError(f"{definition.name!r} weighs {term.measure.name!r}: give its value")
        if term.price not in prices:
            raise ValueError(f"{definition.name!r} weighs at price {term.price!r}: give it")
        value = values[term.measure]
        if isinstance(value, NotComparable):
            return NotComparable(
                not_comparable=f"it weighs {term.measure.name!r}, not comparable:"
                f" {value.not_comparable}"
            )
        score += value * prices[term.price]
    return score
