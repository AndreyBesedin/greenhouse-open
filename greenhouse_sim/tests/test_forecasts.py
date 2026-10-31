"""The forecasts a policy's port serves (P15.6, decision 0061): persistence
from the observations a port has delivered, issued no earlier than what it
is made from is known, and an episode given it."""

from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Final

import pytest
from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.policy import Decision, Delivery, Keep, PolicyIdentity
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.plan import Principal, PrincipalKind
from greenhouse_protocol.provenance import RecordSource

from greenhouse_sim.experiment import Episode, EpisodeSummary, run_episode
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.forecasts import PERSISTED, PERSISTENCE, persistence_budget
from greenhouse_sim.services.playback import Playback
from greenhouse_sim.services.policy_requests import served_budget
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S, HOUR_S

START: Final = datetime(2025, 3, 1, tzinfo=UTC)
HOUR: Final = timedelta(hours=1)
DAY: Final = timedelta(days=1)
TEMPERATURE: Final = ObservationType.OUTSIDE_AIR_TEMPERATURE_C
HUMIDITY: Final = ObservationType.OUTSIDE_RELATIVE_HUMIDITY_PCT
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="watching")


def _reading(
    n: int,
    at: datetime,
    value: float,
    kind: ObservationType = TEMPERATURE,
    delivered_at: datetime | None = None,
) -> Observation:
    return Observation(
        observation_id=f"o{n}",
        greenhouse_id="house",
        plant_id=None,
        timestamp=at,
        observation_type=kind,
        value=value,
        source=RecordSource(type=SourceType.SIMULATION),
        delivered_at=delivered_at,
    )


def _issue(
    observed: list[Observation], until: datetime, after: datetime | None = None
) -> list[Forecast]:
    return PERSISTENCE.issue_due(
        observed, start=START, greenhouse_id="house", after=after, until=until
    )


def test_persistence_forecasts_each_hour_of_the_day_ahead_as_the_last_day_was() -> None:
    readings = [
        _reading(1, START + 30 * timedelta(minutes=1), 10.0),
        _reading(2, START + 50 * timedelta(minutes=1), 14.0),
        _reading(3, START + 3 * HOUR, 8.0),
        _reading(4, START + 3 * HOUR, 55.0, HUMIDITY),
        _reading(5, START + 4 * HOUR, 99.0, ObservationType.OUTSIDE_WIND_SPEED_M_S),
    ]

    forecasts = _issue(readings, START + DAY)

    assert [(f.quantity, f.valid_from - START, f.value) for f in forecasts] == [
        (TEMPERATURE, DAY, 12.0),
        (TEMPERATURE, DAY + 3 * HOUR, 8.0),
        (HUMIDITY, DAY + 3 * HOUR, 55.0),
    ]
    assert {f.issued_at for f in forecasts} == {START + DAY}
    assert all(f.valid_until - f.valid_from == HOUR for f in forecasts)
    assert all(f.standard_deviation is None for f in forecasts)
    assert len({f.forecast_id for f in forecasts}) == len(forecasts)
    assert all(
        (f.provider_id, f.provider_version) == ("persistence", "1") and f.greenhouse_id == "house"
        for f in forecasts
    )


def test_persistence_forecasts_nothing_before_a_day_of_readings_has_passed() -> None:
    readings = [_reading(1, START + HOUR, 10.0)]

    assert _issue(readings, START + DAY - timedelta(seconds=1)) == []
    assert _issue([], START + DAY) == []


def test_persistence_uses_only_readings_delivered_by_the_moment_it_issues() -> None:
    readings = [
        _reading(1, START + HOUR, 10.0),
        # Taken in the last day, but delivered after the forecast is issued.
        _reading(2, START + HOUR, 30.0, delivered_at=START + DAY + HOUR),
        # Taken the day before the last, or on the day forecast.
        _reading(3, START + DAY + HOUR, 70.0),
    ]

    (forecast,) = _issue(readings, START + DAY)

    assert (forecast.value, forecast.issued_at) == (10.0, START + DAY)


def test_persistence_issues_each_day_once_and_the_second_from_the_second_day() -> None:
    readings = [_reading(1, START + HOUR, 10.0), _reading(2, START + DAY + HOUR, 20.0)]

    first = _issue(readings, START + DAY)
    nothing_new = _issue(readings, START + DAY + HOUR, after=START + DAY)
    second = _issue(readings, START + 2 * DAY, after=START + DAY + HOUR)
    both = _issue(readings, START + 2 * DAY)

    assert nothing_new == []
    assert [f.value for f in first] == [10.0] and [f.value for f in second] == [20.0]
    assert both == first + second
    assert second[0].issued_at == START + 2 * DAY


def test_persistence_budget_names_the_outside_quantities_the_run_observes() -> None:
    both = persistence_budget(PERSISTED | {ObservationType.AIR_TEMPERATURE_C})
    one = persistence_budget(frozenset({TEMPERATURE}))

    assert both.forecasts[0].quantities == PERSISTED
    assert one.forecasts[0].quantities == {TEMPERATURE}
    assert not one.oracle and one.forecasts[0].version == PERSISTENCE.provider.version
    with pytest.raises(InvalidRequest, match="observes none"):
        persistence_budget(frozenset({ObservationType.AIR_TEMPERATURE_C}))


def test_a_server_gives_its_policies_the_budget_it_is_told_and_the_run_can_serve(
    simulator: Simulator,
) -> None:
    box = Playback(simulator, "climate_box")

    assert served_budget(box, None) == OBSERVATIONS_ONLY
    persisting = served_budget(box, "persistence")
    assert persisting.forecasts[0].quantities == PERSISTED
    with pytest.raises(InvalidRequest, match="observes none"):
        served_budget(Playback(simulator, "airflow_box"), "persistence")
    with pytest.raises(InvalidRequest, match="no forecast provider"):
        served_budget(box, "oracle")


# A run with a weather station, over days (slow).


class _Watching:
    """A policy that gives no plan and keeps what it was given."""

    identity: Final = PolicyIdentity(name="watching", version="1")
    decide_every_s: Final = 6 * HOUR_S

    def __init__(self) -> None:
        self.deliveries: list[tuple[datetime, Delivery]] = []

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self.deliveries = []

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        self.deliveries.append((at, delivered))
        return Keep()

    def stop(self) -> None: ...


@pytest.fixture(scope="module")
def simulator() -> Iterator[Simulator]:
    with Simulator() as made:
        yield made


def _episode(budget: InformationBudget, watching: _Watching) -> Episode:
    return Episode(
        scenario_id="climate_box",
        policy=watching,
        principal=POLICY,
        end_s=2.5 * DAY_S,
        budget=budget,
    )


@pytest.mark.slow
def test_an_episode_given_persistence_reads_each_days_forecast_of_the_days_before(
    simulator: Simulator,
) -> None:
    observed = Playback(simulator, "climate_box").context(POLICY).observed_types()
    budget = persistence_budget(observed)
    watching, plain, again = _Watching(), _Watching(), _Watching()

    summary = run_episode(simulator, _episode(budget, watching))
    repeated = run_episode(simulator, _episode(budget, again))
    without = run_episode(simulator, _episode(OBSERVATIONS_ONLY, plain))

    assert isinstance(summary, EpisodeSummary) and summary.budget == budget
    assert not summary.budget.oracle
    # Forecasts reach a policy at the decision after they are issued, and
    # never before, nor before a day has passed.
    given = [(at, f) for at, delivery in watching.deliveries for f in delivery.forecasts]
    assert given and all(f.issued_at <= at for at, f in given)
    assert min(f.issued_at for _, f in given) == watching.deliveries[0][0] + DAY
    assert {f.issued_at - watching.deliveries[0][0] for _, f in given} == {DAY, 2 * DAY}
    # Each is the mean of the last day's readings of its hour that the
    # policy was given.
    start = watching.deliveries[0][0]
    readings: dict[tuple[ObservationType, int], list[float]] = defaultdict(list)
    for _, delivery in watching.deliveries:
        for reading in delivery.observations:
            day = (reading.timestamp - start) // DAY
            hour = (reading.timestamp - start - day * DAY) // HOUR
            known = reading.delivered_at or reading.timestamp
            if day == 0 and known <= start + DAY and reading.observation_type in PERSISTED:
                readings[(reading.observation_type, hour)].append(reading.value)
    day_one = {
        (f.quantity, (f.valid_from - f.issued_at) // HOUR): f
        for _, f in given
        if f.issued_at == start + DAY
    }
    assert readings
    for (quantity, hour), values in readings.items():
        assert day_one[(quantity, hour)].value == pytest.approx(sum(values) / len(values))
    # The same episode is the same, forecasts included; without a budget
    # for them, a policy is given none.
    assert repeated.digest == summary.digest
    assert [d for _, d in again.deliveries] == [d for _, d in watching.deliveries]
    assert without.digest != summary.digest
    assert all(delivery.forecasts == () for _, delivery in plain.deliveries)
