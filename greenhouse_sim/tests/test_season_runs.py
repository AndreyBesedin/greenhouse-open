"""Runs through their scenario's days (P09.2): one clock, from a run's start
to its last day's end, with a day's series by default.

The climate box's runs last its 14 days; its first day ends at 86 400 s.
"""

from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S, day_start, run_day
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import sensors
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.services.weather import DAY_EVERY_S

BOX = SCENARIO_REGISTRY["climate_box"]
HEATED = {"heater": 1.0}
# Into the box's second day: 25 h.
SECOND_DAY_S = DAY_S + 3600.0


def _body(simulator: Simulator, path: str) -> dict[str, Any]:
    response = respond(simulator, "GET", path)
    assert response.status == HTTPStatus.OK, response.body
    assert isinstance(response.body, dict)
    return response.body


@pytest.mark.parametrize(
    ("time_s", "day"),
    [(0.0, 0), (1.0, 0), (DAY_S, 0), (DAY_S + 1.0, 1), (2 * DAY_S, 1), (2 * DAY_S + 0.5, 2)],
)
def test_a_moment_belongs_to_the_day_it_lies_in_or_ends(time_s: float, day: int) -> None:
    assert run_day(time_s) == day
    assert day_start(time_s) == day * DAY_S


def test_a_run_lasts_its_scenarios_days(simulator: Simulator) -> None:
    assert BOX.run_length_s() == 14 * DAY_S
    assert SCENARIO_REGISTRY["reference_greenhouse"].run_length_s() == 120 * DAY_S
    last = respond(simulator, "GET", f"/api/scenarios/climate_box/weather?t={14 * DAY_S:.0f}")
    after = respond(simulator, "GET", f"/api/scenarios/climate_box/weather?t={14 * DAY_S + 1:.0f}")

    assert last.status == HTTPStatus.OK
    assert (after.status, after.body) == (
        HTTPStatus.BAD_REQUEST,
        {"error": "a run of climate_box lasts from 0 to 1209600 s, its 14 days, not 1209601"},
    )


def test_the_houses_air_is_a_days_by_default_and_carries_on_across_midnight(
    simulator: Simulator,
) -> None:
    first = _body(simulator, "/api/scenarios/climate_box/climate/house?t=86400&set=heater:1")
    second = _body(
        simulator, f"/api/scenarios/climate_box/climate/house?t={SECOND_DAY_S:.0f}&set=heater:1"
    )
    both = _body(
        simulator,
        f"/api/scenarios/climate_box/climate/house?t={SECOND_DAY_S:.0f}&set=heater:1&from=0",
    )

    assert (first["times_s"][0], first["times_s"][-1]) == (0.0, DAY_S)
    assert (second["times_s"][0], second["times_s"][-1]) == (DAY_S, SECOND_DAY_S)
    assert len(both["times_s"]) == len(first["times_s"]) + len(second["times_s"]) - 1
    # The second day begins where the first ended.
    assert second["controlled"]["temperature_c"][0] == first["controlled"]["temperature_c"][-1]
    assert both["controlled"]["temperature_c"] == (
        first["controlled"]["temperature_c"] + second["controlled"]["temperature_c"][1:]
    )


def test_a_series_that_ends_before_it_begins_is_refused(simulator: Simulator) -> None:
    response = respond(simulator, "GET", "/api/scenarios/climate_box/climate/house?t=600&from=700")

    assert (response.status, response.body) == (
        HTTPStatus.BAD_REQUEST,
        {"error": "a series runs from 700 s to no earlier, not 600"},
    )


def test_a_days_log_is_the_whole_logs_from_that_day_on() -> None:
    whole = sensors.observations(
        RunRequest("climate_box", levels=HEATED), until_s=SECOND_DAY_S, from_s=0.0
    )
    days = sensors.observations(RunRequest("climate_box", levels=HEATED), until_s=SECOND_DAY_S)
    midnight = whole.start + timedelta(seconds=DAY_S)

    assert days.observations == [o for o in whole.observations if o.timestamp >= midnight]
    assert days.frames == [f for f in whole.frames if f.timestamp >= midnight]
    assert days.freshness == whole.freshness
    truths = sensors.truth(RunRequest("climate_box", levels=HEATED), until_s=SECOND_DAY_S)
    assert {t.times_s[0] for t in truths.sensors} == {DAY_S}


@pytest.mark.parametrize("until_s", [0.0, 59.0, 600.0, 1170.0, 1171.0, 1200.0, SECOND_DAY_S])
def test_a_sensors_freshness_is_its_latest_reading_without_reading_them(until_s: float) -> None:
    """Worked out from the draws alone, it agrees with the readings
    delivered: the back thermometer drops samples and is late."""
    log = sensors.observations(
        RunRequest("climate_box", levels=HEATED), until_s=until_s, from_s=0.0
    )
    latest: dict[str, datetime] = {}
    for observation in log.observations:
        sensor_id = observation.sensor_id or ""
        latest[sensor_id] = max(observation.timestamp, latest.get(sensor_id, observation.timestamp))

    for state in log.freshness:
        assert state.latest_at == latest.get(state.sensor_id), state.sensor_id


def test_the_weather_through_a_later_day(simulator: Simulator) -> None:
    body = _body(simulator, f"/api/scenarios/climate_box/weather/day?t={SECOND_DAY_S:.0f}")

    assert body["times_s"][0] == DAY_S
    assert body["times_s"][-1] == 2 * DAY_S
    assert body["every_s"] == DAY_EVERY_S


def test_a_plants_light_integral_is_its_moments_days(simulator: Simulator) -> None:
    light = plant_light("solar_lab", "default", "default")
    body = _body(simulator, f"/api/scenarios/solar_lab/climate/plants?t={SECOND_DAY_S:.0f}")

    assert body["daily_light_integral_mol_m2_d"] == light.daily_light_integral(1)
    assert body["daily_light_integral_mol_m2_d"] != light.daily_light_integral(0)


def test_a_command_may_come_on_any_day_of_the_run(simulator: Simulator) -> None:
    later = _body(
        simulator,
        f"/api/scenarios/climate_box/climate/house?t={SECOND_DAY_S:.0f}"
        f"&schedule={DAY_S + 600:.0f}:heater:1",
    )
    still = _body(simulator, f"/api/scenarios/climate_box/climate/house?t={SECOND_DAY_S:.0f}")

    assert later["controlled"]["temperature_c"][:10] == still["controlled"]["temperature_c"][:10]
    assert later["controlled"]["temperature_c"][-1] > still["controlled"]["temperature_c"][-1] + 1.0
