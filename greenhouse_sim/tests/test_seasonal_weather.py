"""Weather through a season (P10.3): each day's coldest and warmest
temperatures follow the year and wander from it in spells drawn from the
seed, each day its own clouds, a synthetic day's shape between, and nothing
that jumps at midnight; and the reference greenhouse under it."""

from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.weather.seasonal import SeasonalWeather
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.site import DEFAULT_SITE

SEED = 42
# A season with no spells and a sky that does not change: the year alone.
STEADY = SeasonalWeather(
    coldest_c=(0.0, 14.0),
    warmest_c=(6.0, 24.0),
    coldest_day=20,
    coldest_hour=6.0,
    warmest_hour=15.0,
    humidity_at_coldest_pct=90.0,
    calmest_m_s=1.0,
    windiest_m_s=5.0,
    wind_from_deg=225.0,
    cloud_cover_pct=50.0,
)
SPELLS = STEADY.model_copy(
    update={"day_to_day_c": 2.5, "persistence": 0.7, "cloud_spread_pct": 40.0}
)
SPRING = date(2026, 3, 1)


def _at(weather: SeasonalWeather, moment: datetime, seed: int = SEED) -> WeatherState:
    return weather.source(DEFAULT_SITE, seed).at(moment)


def _local(day: date, hours: float) -> datetime:
    return DEFAULT_SITE.midnight(day) + timedelta(hours=hours)


def test_without_spells_a_day_is_its_seasons_on_the_coldest_day_and_half_a_year_on() -> None:
    coldest = date(2026, 1, 20)
    warmest = coldest + timedelta(days=183)

    assert STEADY.temperatures_c(SEED, coldest) == pytest.approx((0.0, 6.0))
    assert STEADY.temperatures_c(SEED, warmest) == pytest.approx((14.0, 24.0), abs=0.01)
    # Coldest and warmest at their hours, as a synthetic day is.
    assert _at(STEADY, _local(coldest, 6.0)).air_temperature_c == pytest.approx(0.0)
    assert _at(STEADY, _local(coldest, 15.0)).air_temperature_c == pytest.approx(6.0)


def test_spring_warms_into_summer_and_no_two_days_are_alike() -> None:
    days = [SPRING + timedelta(days=n) for n in range(120)]
    lows, highs = zip(*(SPELLS.temperatures_c(SEED, day) for day in days), strict=True)

    # The last month well above the first.
    assert sum(highs[-30:]) / 30 > sum(highs[:30]) / 30 + 8.0
    assert sum(lows[-30:]) / 30 > sum(lows[:30]) / 30 + 6.0
    # Not one day's weather again and again: every day its own.
    days_seen = {(round(low, 2), round(high, 2)) for low, high in zip(lows, highs, strict=True)}
    assert len(days_seen) == 120
    # A spell lasts: a day is closer to the day before than to a day a month
    # away, once the season is taken out.
    usual = [STEADY.temperatures_c(SEED, day)[1] for day in days]
    shifts = [high - base for high, base in zip(highs, usual, strict=True)]
    next_day = sum(abs(a - b) for a, b in zip(shifts, shifts[1:], strict=False))
    month_on = sum(abs(a - b) for a, b in zip(shifts, shifts[30:], strict=False))
    assert next_day / (len(shifts) - 1) < month_on / (len(shifts) - 30)


def test_the_same_seed_is_the_same_season_and_another_seed_another() -> None:
    days = [SPRING + timedelta(days=n) for n in range(60)]

    again = SPELLS.model_copy()
    assert [SPELLS.temperatures_c(SEED, d) for d in days] == [
        again.temperatures_c(SEED, d) for d in days
    ]
    assert [SPELLS.temperatures_c(SEED, d) for d in days] != [
        SPELLS.temperatures_c(SEED + 1, d) for d in days
    ]
    # Whenever a run starts, a date's weather is the same.
    moment = _local(SPRING + timedelta(days=40), 13.0)
    early = SPELLS.source(DEFAULT_SITE, SEED, start=_local(SPRING, 0.0)).at(moment)
    late = SPELLS.source(DEFAULT_SITE, SEED, start=_local(SPRING + timedelta(days=39), 0.0))
    assert late.at(moment) == early


def test_each_day_has_its_own_clouds_within_their_range() -> None:
    days = [SPRING + timedelta(days=n) for n in range(60)]
    clouds = [SPELLS.clouds_pct(SEED, day) for day in days]

    assert all(10.0 <= cover <= 90.0 for cover in clouds)
    assert len({round(cover) for cover in clouds}) > 30
    noon = _at(SPELLS, _local(days[3], 12.0))
    assert noon.cloud_cover_pct == pytest.approx(clouds[3])
    assert noon.global_radiation_w_m2 > 0


def test_nothing_jumps_from_one_day_to_the_next() -> None:
    # April and May, clear of the clocks going forward in March.
    start = _local(date(2026, 4, 1), 0.0)
    states = [_at(SPELLS, start + timedelta(minutes=10 * step)) for step in range(6 * 24 * 60)]
    temperatures = [state.air_temperature_c for state in states]
    humidities = [state.relative_humidity_pct for state in states]

    assert max(abs(b - a) for a, b in zip(temperatures, temperatures[1:], strict=False)) < 0.5
    assert max(abs(b - a) for a, b in zip(humidities, humidities[1:], strict=False)) < 3.0


def test_the_evening_cools_from_the_days_warmest_to_the_next_days_coldest() -> None:
    day = SPRING + timedelta(days=50)
    _, warmest = SPELLS.temperatures_c(SEED, day)
    coldest_next, _ = SPELLS.temperatures_c(SEED, day + timedelta(days=1))

    assert _at(SPELLS, _local(day, 15.0)).air_temperature_c == pytest.approx(warmest)
    assert _at(SPELLS, _local(day + timedelta(days=1), 6.0)).air_temperature_c == pytest.approx(
        coldest_next
    )


@pytest.mark.parametrize(
    ("change", "refused"),
    [
        ({"warmest_c": (6.0, 10.0), "coldest_c": (0.0, 14.0)}, "no colder than its coldest"),
        ({"coldest_hour": 16.0}, "coldest hour comes before the warmest"),
        ({"persistence": 0.8}, "persistence"),
        ({"windiest_m_s": 0.5}, "no calmer than the calmest"),
    ],
)
def test_a_season_that_cannot_be_is_refused(change: dict[str, object], refused: str) -> None:
    with pytest.raises(ValidationError, match=refused):
        SeasonalWeather.model_validate(STEADY.model_dump() | change)


def test_the_reference_greenhouse_is_under_a_season() -> None:
    config = SCENARIO_REGISTRY["reference_greenhouse"]

    assert isinstance(config.weather, SeasonalWeather)
    start = config.run_start()
    weather = config.run_weather()
    march = [weather.at(day * 86400.0 + 14 * 3600.0).air_temperature_c for day in range(14)]
    june = [weather.at(day * 86400.0 + 14 * 3600.0).air_temperature_c for day in range(100, 114)]
    assert start == _local(config.start_date, 0.0)
    assert sum(june) / len(june) > sum(march) / len(march) + 8.0
