"""Synthetic days (P07.2): coldest near dawn and warmest in the afternoon on
the site's clock, the air's water held all day, a wind that rises with the
warmth and veers steadily, and gusts the same for the same seed; and a
scenario run under one by name."""

import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import fields, scenarios, weather
from greenhouse_sim.weather.presets import COLD_SPRING_DAY, PRESETS
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.weather.synthetic import SyntheticWeather
from greenhouse_sim.world.site import DEFAULT_SITE

# Midnight in Amsterdam on a winter's day, and a still copy of the spring
# day, whose wind follows its curve exactly.
MIDNIGHT = DEFAULT_SITE.midnight(datetime(2026, 4, 14).date())
STILL = COLD_SPRING_DAY.model_copy(update={"gustiness": 0.0})
SEED = 1201


def _at(day: SyntheticWeather, hours: float, seed: int = SEED) -> WeatherState:
    return day.source(DEFAULT_SITE, seed).at(MIDNIGHT + timedelta(hours=hours))


def _through(day: SyntheticWeather, seed: int = SEED) -> list[WeatherState]:
    return [_at(day, quarter / 4, seed) for quarter in range(24 * 4)]


@pytest.mark.parametrize("name", PRESETS)
def test_a_presets_day_is_coldest_and_warmest_at_its_hours(name: str) -> None:
    day = PRESETS[name]
    temperatures = [state.air_temperature_c for state in _through(day)]

    assert _at(day, day.coldest_hour).air_temperature_c == pytest.approx(day.coldest_c)
    assert _at(day, day.warmest_hour).air_temperature_c == pytest.approx(day.warmest_c)
    assert min(temperatures) == pytest.approx(day.coldest_c)
    assert max(temperatures) == pytest.approx(day.warmest_c)


def test_the_day_warms_through_the_morning_and_cools_through_the_evening() -> None:
    morning = [_at(STILL, hour).air_temperature_c for hour in range(6, 16)]
    evening = [_at(STILL, hour).air_temperature_c for hour in range(15, 24)]

    assert morning == sorted(morning)
    assert evening == sorted(evening, reverse=True)
    # The night carries on cooling past midnight, to the next dawn.
    assert _at(STILL, 0.0).air_temperature_c > _at(STILL, 5.0).air_temperature_c


@pytest.mark.parametrize("name", PRESETS)
def test_the_air_holds_the_same_water_all_day(name: str) -> None:
    states = _through(PRESETS[name])
    water = [
        float(humidity_ratio_g_kg(s.air_temperature_c, s.relative_humidity_pct)) for s in states
    ]

    assert max(water) == pytest.approx(min(water), rel=1e-9)
    assert _at(PRESETS[name], PRESETS[name].coldest_hour).relative_humidity_pct == pytest.approx(
        PRESETS[name].humidity_at_coldest_pct
    )


def test_relative_humidity_falls_as_the_day_warms() -> None:
    dawn, afternoon = _at(STILL, 6.0), _at(STILL, 15.0)

    assert afternoon.relative_humidity_pct < dawn.relative_humidity_pct - 40


def test_the_wind_is_calmest_when_coldest_and_windiest_when_warmest() -> None:
    assert _at(STILL, 6.0).wind_speed_m_s == pytest.approx(STILL.calmest_m_s)
    assert _at(STILL, 15.0).wind_speed_m_s == pytest.approx(STILL.windiest_m_s)


def test_the_wind_veers_steadily_through_the_day() -> None:
    # From the south-west at midnight, a quarter turn by the next.
    assert _at(STILL, 0.0).wind_direction_deg == pytest.approx(225.0)
    assert _at(STILL, 12.0).wind_direction_deg == pytest.approx(270.0)
    assert _at(STILL, 18.0).wind_direction_deg == pytest.approx(292.5)
    backing = STILL.model_copy(update={"veer_deg": -90.0})
    assert _at(backing, 12.0).wind_direction_deg == pytest.approx(180.0)


def test_the_same_seed_gives_the_same_gusts_and_another_others() -> None:
    once = [state.wind_speed_m_s for state in _through(COLD_SPRING_DAY, seed=7)]
    again = [state.wind_speed_m_s for state in _through(COLD_SPRING_DAY, seed=7)]
    other = [state.wind_speed_m_s for state in _through(COLD_SPRING_DAY, seed=8)]
    still = [state.wind_speed_m_s for state in _through(STILL)]

    assert once == again
    assert once != other
    # Gusts and lulls about the curve, by about a fifth of its speed.
    shares = [gusty / calm - 1.0 for gusty, calm in zip(once, still, strict=True)]
    assert max(shares) > 0.1
    assert min(shares) < -0.1
    assert all(abs(share) < 1.0 for share in shares)


def test_gusts_between_their_draws_change_linearly() -> None:
    source = COLD_SPRING_DAY.source(DEFAULT_SITE, SEED)
    # A minute's draws, at the start of a minute and at its end.
    minute = datetime(2026, 4, 14, 10, 0, tzinfo=UTC)
    start, end = source.at(minute), source.at(minute + timedelta(minutes=1))
    middle = source.at(minute + timedelta(seconds=30))
    curve = STILL.source(DEFAULT_SITE, SEED)

    def share(state: WeatherState, at: datetime) -> float:
        return state.wind_speed_m_s / curve.at(at).wind_speed_m_s - 1.0

    halfway = (share(start, minute) + share(end, minute + timedelta(minutes=1))) / 2
    assert share(middle, minute + timedelta(seconds=30)) == pytest.approx(halfway, abs=1e-9)


def test_the_day_follows_the_sites_clock_when_the_clocks_change() -> None:
    # Summer time starts in Amsterdam at 02:00 on 29 March 2026: 06:00 on the
    # clock is 04:00 UTC that day, not 05:00.
    source = STILL.source(DEFAULT_SITE, SEED)

    assert source.at(datetime(2026, 3, 29, 4, tzinfo=UTC)).air_temperature_c == pytest.approx(4.0)
    assert source.at(datetime(2026, 3, 28, 5, tzinfo=UTC)).air_temperature_c == pytest.approx(4.0)


def test_its_pressure_is_the_sites_unless_given() -> None:
    high = DEFAULT_SITE.model_copy(update={"elevation_m": 500.0})

    assert STILL.source(high, SEED).at(MIDNIGHT).barometric_pressure_hpa == pytest.approx(
        high.standard_pressure_hpa()
    )
    given = STILL.model_copy(update={"barometric_pressure_hpa": 1020.0})
    assert given.source(high, SEED).at(MIDNIGHT).barometric_pressure_hpa == 1020.0


@pytest.mark.parametrize(
    ("change", "refusal"),
    [
        ({"coldest_hour": 16.0}, "coldest hour comes before the warmest"),
        ({"warmest_c": 0.0}, "no colder than the coldest"),
        ({"windiest_m_s": 1.0}, "no calmer than the calmest"),
        ({"warmest_hour": 24.0}, "less than 24"),
    ],
)
def test_a_day_that_does_not_warm_and_cool_is_refused(
    change: dict[str, float], refusal: str
) -> None:
    with pytest.raises(ValidationError, match=refusal):
        SyntheticWeather.model_validate(COLD_SPRING_DAY.model_dump() | change)


def test_every_scenario_can_be_run_under_any_preset() -> None:
    for summary in scenarios.scenario_summaries():
        assert summary.weathers == ["default", *PRESETS]


def test_a_climate_run_under_a_preset_is_its_weathers() -> None:
    config = SCENARIO_REGISTRY["climate_box"]
    # The run starts at midnight, near 8 °C on the spring day, as on the
    # box's own night; but the spring day is drier and colder by its first
    # hour, so the house's air differs.
    own = fields.field("climate_box", "climate", time_s=3600)
    spring = fields.field("climate_box", "climate", time_s=3600, weather="cold_spring_day")
    outside = weather.at_a_moment("climate_box", 0.0, "cold_spring_day").weather

    assert own.source == spring.source
    assert own.channels != spring.channels
    assert outside.relative_humidity_pct < config.run_weather().at(0.0).relative_humidity_pct


def test_the_api_serves_a_scenario_under_a_preset_and_refuses_an_unknown_one() -> None:
    preset = respond("GET", "/api/scenarios/climate_box/weather?weather=cold_spring_day&t=600")
    body = json.loads(json.dumps(preset.body))

    assert preset.status == HTTPStatus.OK
    assert body["weather"]["cloud_cover_pct"] == 50.0
    for path in (
        "/api/scenarios/climate_box/weather?weather=foggy",
        "/api/scenarios/climate_box/weather/day?weather=foggy",
        "/api/scenarios/climate_box/fields/climate?weather=foggy",
        "/api/scenarios/climate_box/climate/probes?probes=6:3.2:1&weather=foggy",
        "/api/scenarios/climate_box/climate/observations?weather=foggy",
    ):
        assert respond("GET", path).status == HTTPStatus.NOT_FOUND, path


def test_the_api_serves_the_weather_through_the_runs_first_day() -> None:
    response = respond("GET", "/api/scenarios/climate_box/weather/day?weather=cold_spring_day")
    body = json.loads(json.dumps(response.body))

    assert response.status == HTTPStatus.OK
    assert body["start"] == "2025-12-31T23:00:00Z"
    assert body["times_s"][:2] == [0.0, 600.0]
    assert body["times_s"][-1] == 86_400.0
    temperatures = [state["air_temperature_c"] for state in body["weather"]]
    assert min(temperatures) == pytest.approx(4.0)
    assert max(temperatures) == pytest.approx(16.0)
    # Its own weather is the same all day.
    own = weather.through_the_day("climate_box")
    assert {state.air_temperature_c for state in own.weather} == {8.0}
