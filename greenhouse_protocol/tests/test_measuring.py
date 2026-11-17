"""The arithmetic each measure's definition implies (P25.1, decision 0081):
each packaged measure, on hand-made series, gives the value worked out by
hand."""

from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_protocol.actions import ActionRef, SetLevel
from greenhouse_protocol.benchmark import (
    MeasureDefinition,
    MeasureNamed,
    NotComparable,
    packaged_measure,
)
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import Goal, GoalSense
from greenhouse_protocol.contracts.policy import Keep, PolicyIdentity
from greenhouse_protocol.experiment import (
    Condition,
    DecisionTraced,
    DeliveredLogs,
    EpisodePolicy,
    EpisodeRecord,
    EpisodeRun,
    Software,
    WeatherSeries,
    delivered,
)
from greenhouse_protocol.measuring import (
    changes,
    held,
    integral_outside,
    priced_value,
    quantile,
    record_values,
    series_value,
)
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import At, ExecutorKind, ExecutorRef, Principal, PrincipalKind

HOUR = 3600.0
DAY_BAND = Goal(
    goal_id="air-temperature-by-day",
    description="The air by day",
    unit="°C",
    sense=GoalSense.WITHIN,
    low=18.0,
    high=24.0,
)
NIGHT_BAND = DAY_BAND.model_copy(update={"goal_id": "air-temperature-by-night", "low": 15.0})
HUMIDITY = Goal(
    goal_id="air-humidity",
    description="The air's humidity",
    unit="%",
    sense=GoalSense.WITHIN,
    high=85.0,
)
SIX_HOURS = [(0.0, 6 * HOUR)]
# The air 2 K under its band by day, 16 °C, from the first hour to the fourth.
UNDER_FOR_THREE_HOURS = [(0.0, 20.0), (1 * HOUR, 16.0), (4 * HOUR, 20.0)]


def _measure(name: str) -> MeasureDefinition:
    return packaged_measure(name, 1)


def test_air_two_kelvin_under_its_band_for_three_hours_gives_six_kelvin_hours_and_three_hours() -> (
    None
):
    integral = series_value(
        _measure("temperature-outside-band-by-day"),
        UNDER_FOR_THREE_HOURS,
        SIX_HOURS,
        goal=DAY_BAND,
    )
    hours = series_value(
        _measure("hours-temperature-outside-band-by-day"),
        UNDER_FOR_THREE_HOURS,
        SIX_HOURS,
        goal=DAY_BAND,
    )

    assert integral == pytest.approx(6.0)
    assert hours == pytest.approx(3.0)


def test_the_air_above_its_band_counts_and_on_a_bound_it_is_within() -> None:
    # 1 h at 26 °C (2 K over), 2 h on the upper bound, 1 h at 17 °C (1 K under).
    samples = [(0.0, 26.0), (1 * HOUR, 24.0), (3 * HOUR, 17.0), (4 * HOUR, 20.0)]

    assert integral_outside(samples, SIX_HOURS, DAY_BAND) == pytest.approx(3.0)
    assert series_value(
        _measure("hours-temperature-outside-band-by-day"), samples, SIX_HOURS, goal=DAY_BAND
    ) == pytest.approx(2.0)


def test_a_band_by_night_counts_only_the_nights_hours() -> None:
    # Night from 0 h to 6 h and from 20 h to 24 h; 14 °C (1 K under) from 5 h
    # to 22 h, through the day between.
    samples = [(0.0, 16.0), (5 * HOUR, 14.0), (22 * HOUR, 16.0)]
    nights = [(0.0, 6 * HOUR), (20 * HOUR, 24 * HOUR)]
    measure = _measure("temperature-outside-band-by-night")

    assert series_value(measure, samples, nights, goal=NIGHT_BAND) == pytest.approx(3.0)
    with pytest.raises(ValueError, match="scored against goal 'air-temperature-by-night'"):
        series_value(measure, samples, nights, goal=DAY_BAND)


def test_humidity_above_its_limit_by_hand() -> None:
    # 90 % (5 over) for 2 h, 95 % (10 over) for 30 min, 85 % on the limit after.
    samples = [(0.0, 80.0), (1 * HOUR, 90.0), (3 * HOUR, 95.0), (3.5 * HOUR, 85.0)]

    assert series_value(
        _measure("humidity-above-limit"), samples, SIX_HOURS, goal=HUMIDITY
    ) == pytest.approx(15.0)
    assert series_value(
        _measure("hours-humidity-above-limit"), samples, SIX_HOURS, goal=HUMIDITY
    ) == pytest.approx(2.5)


def test_a_devices_switches_and_hours_run_per_day_by_hand() -> None:
    # Off, on at 1 h, on again at 2 h (no switch), half at 3 h, off at 4 h;
    # over half a day.
    levels = [(0.0, 0.0), (1 * HOUR, 1.0), (2 * HOUR, 1.0), (3 * HOUR, 0.5), (4 * HOUR, 0.0)]
    half_a_day = [(0.0, 12 * HOUR)]

    assert series_value(_measure("device-switches"), levels, half_a_day) == pytest.approx(6.0)
    # 2 h at full and 1 h at half: 2.5 h in half a day.
    assert series_value(_measure("device-level-hours"), levels, half_a_day) == pytest.approx(5.0)


def test_a_switch_is_counted_where_it_falls_in_the_window() -> None:
    levels = [(0.0, 0.0), (1 * HOUR, 1.0), (3 * HOUR, 0.0)]

    assert changes(levels, [(1 * HOUR, 2 * HOUR)]) == 1
    assert changes(levels, [(1.5 * HOUR, 3 * HOUR)]) == 0
    # Where a quantity starts is not a switch.
    assert changes(levels[1:], [(0.0, 4 * HOUR)]) == 1


def test_the_heat_given_and_the_harvest_are_summed_within_the_window_per_m2_of_floor() -> None:
    # MJ given each half hour; the window is from 0.5 h to 3 h, on 2 m².
    heat = [(0.0, 1.0), (0.5 * HOUR, 2.0), (2 * HOUR, 4.0), (3 * HOUR, 8.0)]
    window = [(0.5 * HOUR, 3 * HOUR)]
    harvest = [(1 * HOUR, 300.0), (2 * HOUR, 500.0)]

    assert series_value(_measure("heat-given"), heat, window, floor_area_m2=2.0) == pytest.approx(
        3.0
    )
    assert series_value(_measure("harvest"), harvest, window, floor_area_m2=4.0) == pytest.approx(
        200.0
    )
    with pytest.raises(ValueError, match="give the floor's area"):
        series_value(_measure("heat-given"), heat, window)


def test_a_quantity_with_no_value_where_its_window_starts_is_refused() -> None:
    with pytest.raises(ValueError, match=r"no value at 0\.0 s"):
        list(held([(60.0, 20.0)], [(0.0, HOUR)]))
    with pytest.raises(ValueError, match="strictly increasing"):
        list(held([(0.0, 20.0), (0.0, 21.0)], [(0.0, HOUR)]))
    with pytest.raises(ValueError, match="in order, apart"):
        list(held([(0.0, 20.0)], [(0.0, 2 * HOUR), (HOUR, 3 * HOUR)]))


def test_a_quantile_by_linear_interpolation_between_ranks() -> None:
    assert quantile([3.0, 1.0, 2.0, 4.0], 0.5) == pytest.approx(2.5)
    assert quantile([3.0, 1.0, 2.0], 0.5) == 2.0
    assert quantile([3.0, 1.0, 2.0], 1.0) == 3.0
    assert quantile([5.0], 0.5) == 5.0
    with pytest.raises(ValueError, match="no values"):
        quantile([], 0.5)


AT = datetime(2026, 3, 1, tzinfo=UTC)
POLICY = Principal(kind=PrincipalKind.POLICY, id="rule")
NOTHING = delivered(())
LOGS = DeliveredLogs(observations=NOTHING, events=NOTHING, outcomes=NOTHING, forecasts=NOTHING)


def _outcome(index: int, status: OutcomeStatus) -> ActionOutcome:
    fields: dict[str, object] = {}
    if status == OutcomeStatus.EXECUTED:
        heater = ExecutorRef(kind=ExecutorKind.SIMULATED_RUN, id="run")
        fields = dict(started_at=AT, finished_at=AT, executor=heater)
    elif status == OutcomeStatus.REFUSED:
        fields = dict(reason="not allowed")
    return ActionOutcome.model_validate(
        dict(
            outcome_id=f"o{index}",
            greenhouse_id="gh",
            run_id="run",
            epoch=0,
            plan_id="rule",
            revision=1,
            ref=ActionRef(action_id=f"a{index}"),
            action=SetLevel(device_id="heater", level=1.0),
            timing=At(at=AT),
            principal=POLICY,
            status=status,
            due=AT,
            resolved_at=AT,
            **fields,
        )
    )


def _record(took_s: tuple[float, ...], skipped: tuple[bool, ...]) -> EpisodeRecord:
    return EpisodeRecord(
        run=EpisodeRun(
            scenario_id="climate_box",
            greenhouse_id="gh",
            layout="default",
            scenario_file_digest=None,
            run_id="run",
            epoch=0,
            condition=Condition(),
            seed=0,
            start=AT,
            duration_s=HOUR,
            episode_end_s=HOUR,
            models=(),
            weather=WeatherSeries(every_s=600.0, sha256="0" * 64),
        ),
        policy=EpisodePolicy(
            identity=PolicyIdentity(name="rule", version="1"),
            made=None,
            principal=POLICY,
            decide_every_s=600.0,
            plan_id="rule",
            budget=InformationBudget(budget_id="none"),
            compute_budget_s=1.0,
        ),
        software=Software(
            producer="sim", producer_version="0", protocol_version="0", python="3.14", commit=None
        ),
        trace=tuple(
            DecisionTraced(
                at=AT + timedelta(minutes=10 * index),
                delivered=LOGS,
                decision=Keep(),
                receipt=None,
                took_s=took,
                skipped=skip,
            )
            for index, (took, skip) in enumerate(zip(took_s, skipped, strict=True))
        ),
        outcomes=tuple(
            _outcome(index, status)
            for index, status in enumerate(
                [OutcomeStatus.EXECUTED, OutcomeStatus.EXECUTED, OutcomeStatus.REFUSED]
            )
        ),
        digest="0" * 64,
    )


def test_the_records_measures_by_hand() -> None:
    record = _record(took_s=(0.2, 1.5, 0.4, 0.1), skipped=(False, True, False, False))

    by_status = record_values(_measure("actions-by-status"), record)
    assert by_status == {status.value: 0.0 for status in OutcomeStatus} | {
        "executed": 2.0,
        "refused": 1.0,
    }
    assert record_values(_measure("decisions-skipped"), record) == {None: 1.0}
    assert record_values(_measure("decision-time-median"), record) == {None: pytest.approx(0.3)}
    assert record_values(_measure("decision-time-largest"), record) == {None: 1.5}


def test_an_episode_of_no_decision_has_no_decision_time_to_compare() -> None:
    record = _record(took_s=(), skipped=())

    assert record_values(_measure("decision-time-median"), record) == {
        None: NotComparable(not_comparable="the episode made no decision")
    }
    assert record_values(_measure("decisions-skipped"), record) == {None: 0.0}


def test_a_measure_is_worked_out_only_by_the_arithmetic_of_its_source() -> None:
    record = _record(took_s=(0.1,), skipped=(False,))

    with pytest.raises(ValueError, match="not made from the record alone"):
        record_values(_measure("heat-given"), record)
    with pytest.raises(ValueError, match="not made from an instrument's series"):
        series_value(_measure("decisions-skipped"), [(0.0, 1.0)], SIX_HOURS)
    with pytest.raises(ValueError, match="not a priced score"):
        priced_value(_measure("heat-given"), {}, {})


def _named(name: str) -> MeasureNamed:
    return MeasureNamed(name=name, version=1)


PRICES = {
    "heat": 0.03,
    "temperature-by-day-penalty": 0.5,
    "temperature-by-night-penalty": 0.25,
    "humidity-penalty": 0.01,
}
VALUES = {
    _named("heat-given"): 120.0,
    _named("temperature-outside-band-by-day"): 6.0,
    _named("temperature-outside-band-by-night"): 2.0,
    _named("humidity-above-limit"): 15.0,
}


def test_the_priced_score_is_its_measures_weighed_at_their_prices() -> None:
    priced = _measure("priced-score")

    # 120 × 0.03 + 6 × 0.5 + 2 × 0.25 + 15 × 0.01
    assert priced_value(priced, VALUES, PRICES) == pytest.approx(7.25)
    doubled = PRICES | {name: 2 * price for name, price in PRICES.items() if name != "heat"}
    assert priced_value(priced, VALUES, doubled) == pytest.approx(3.6 + 2 * 3.65)


def test_the_priced_score_is_not_comparable_when_a_measure_it_weighs_is_not() -> None:
    priced = _measure("priced-score")
    values = VALUES | {_named("humidity-above-limit"): NotComparable(not_comparable="no sensor")}

    assert priced_value(priced, values, PRICES) == NotComparable(
        not_comparable="it weighs 'humidity-above-limit', not comparable: no sensor"
    )
    with pytest.raises(ValueError, match="at price 'heat': give it"):
        priced_value(priced, VALUES, {k: v for k, v in PRICES.items() if k != "heat"})
    with pytest.raises(ValueError, match="weighs 'heat-given': give its value"):
        priced_value(priced, {k: v for k, v in VALUES.items() if k.name != "heat-given"}, PRICES)
