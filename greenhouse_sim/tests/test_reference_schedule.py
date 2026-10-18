"""A scenario's own daily commands (P09.4): the reference run heats, vents
and stirs its house by the clock every day, as its manifest says, unless a
run gives daily commands of its own; and its sensors observe the season it
makes, only through the observation path."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any, Final

import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import DailyCommand
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import fields, sensors
from greenhouse_sim.world.sensors import PointSensor

REFERENCE = SCENARIO_REGISTRY["reference_greenhouse"]
HOUR_S: Final = 3600.0
# The reference run's second day: its evening, heated in full, and the small
# hours after, the heat set back.
EVENING_S: Final = DAY_S + 22 * HOUR_S
SMALL_HOURS_S: Final = 2 * DAY_S + 3 * HOUR_S


def _own() -> list[tuple[float, str, float]]:
    return [(c.time_of_day_s, c.actuator_id, c.level) for c in REFERENCE.daily]


def _body(path: str) -> dict[str, Any]:
    response = respond("GET", path)
    assert response.status == HTTPStatus.OK, response.body
    assert isinstance(response.body, dict)
    return response.body


def test_the_reference_run_heats_vents_and_stirs_its_house_every_day() -> None:
    actuators = {command.actuator_id for command in REFERENCE.daily}

    assert actuators == {
        "heater",
        "fan_left",
        "fan_right",
        "roof_vent_1",
        "roof_vent_2",
        "roof_vent_3",
    }
    # Every other scenario's runs give none of their own.
    others = [s for s in SCENARIO_REGISTRY.values() if s is not REFERENCE]
    assert all(other.daily == [] for other in others)


def test_a_run_gives_its_scenarios_daily_commands_unless_it_gives_its_own() -> None:
    own = fields.run_schedule("reference_greenhouse")
    replaced = fields.run_schedule("reference_greenhouse", daily=[(64800.0, "heater", 1.0)])
    none = fields.run_schedule("reference_greenhouse", daily=[])

    expected = [
        (day * DAY_S + time, actuator, level)
        for day in range(REFERENCE.duration_days)
        for time, actuator, level in _own()
    ]
    assert sorted((c.time_s, c.actuator_id, c.level) for c in own.commands) == sorted(expected)
    assert [(c.time_s, c.actuator_id) for c in replaced.commands][:2] == [
        (64800.0, "heater"),
        (DAY_S + 64800.0, "heater"),
    ]
    assert none.commands == ()


def test_the_api_reads_daily_none_as_none_and_leaves_out_none_as_its_own() -> None:
    own = _body("/api/scenarios/reference_greenhouse/timeline?t=86400")
    none = _body("/api/scenarios/reference_greenhouse/timeline?t=86400&daily=none")
    commands = own["processes"].index("commands")

    assert own["process"].count(commands) == len(REFERENCE.daily)
    assert none["process"].count(commands) == 0
    summaries = respond("GET", "/api/scenarios").body
    assert isinstance(summaries, list)
    reference = next(
        s for s in summaries if isinstance(s, dict) and s["id"] == REFERENCE.greenhouse_id
    )
    assert reference["daily"] == [c.model_dump(mode="json") for c in REFERENCE.daily]


def test_a_scenario_refuses_daily_commands_to_what_it_does_not_have() -> None:
    with pytest.raises(ValidationError, match="daily commands to what it does not have: boiler"):
        type(REFERENCE).model_validate(
            REFERENCE.model_dump()
            | {"daily": [DailyCommand(time_of_day_s=0.0, actuator_id="boiler", level=1.0)]}
        )


def _reading(time_s: float, daily: list[tuple[float, str, float]] | None = None) -> float:
    """What the front temperature sensor, a clean one, observed at `time_s`."""
    log = sensors.observations(
        "reference_greenhouse", until_s=time_s, from_s=time_s - 60.0, daily=daily
    )
    return next(
        o.value
        for o in log.observations
        if o.sensor_id == "temperature_front"
        and o.timestamp == REFERENCE.run_start() + timedelta(seconds=time_s)
    )


def test_the_heaters_night_setback_shows_in_the_readings() -> None:
    evening, small_hours = _reading(EVENING_S), _reading(SMALL_HOURS_S)
    unheated = _reading(SMALL_HOURS_S, daily=[])

    # Set back, the house cools from the evening's warmth, but stays well
    # above what an unheated house falls to.
    assert small_hours < evening - 1.0
    assert small_hours > unheated + 5.0


def test_its_sensors_observe_only_the_run_they_belong_to_through_the_season() -> None:
    sensor = next(s for s in REFERENCE.layout.sensors if s.sensor_id == "temperature_front")
    assert isinstance(sensor, PointSensor)
    air, run_id = fields.air_through_a_run("reference_greenhouse")
    log = sensors.observations(
        "reference_greenhouse", until_s=SMALL_HOURS_S, from_s=SMALL_HOURS_S - 300.0, clean=True
    )
    observed = [o for o in log.observations if o.sensor_id == "temperature_front"]

    assert log.run_id == run_id
    assert [o.value for o in observed] == pytest.approx(
        [
            air((o.timestamp - REFERENCE.run_start()).total_seconds()).sample(
                AirQuantity.TEMPERATURE, sensor.position
            )
            for o in observed
        ],
        rel=1e-6,
    )


def _door_flow(weather: str) -> float:
    body = _body(
        f"/api/scenarios/reference_greenhouse/climate/openings?t=43200&open=door:1&weather={weather}"
    )
    return float(next(o["net_m3_s"] for o in body["openings"] if o["opening_id"] == "door"))


def test_the_winds_direction_can_be_overridden_for_qa_and_an_open_door_follows_it() -> None:
    own = _body("/api/scenarios/reference_greenhouse/weather?t=43200")["weather"]
    east = _body("/api/scenarios/reference_greenhouse/weather?t=43200&weather=default~90")[
        "weather"
    ]
    clouded = _body(
        "/api/scenarios/reference_greenhouse/weather?t=43200&weather=cold_spring_day@80~0"
    )["weather"]

    # Only its direction turns: its speed is its own, and so is the rest.
    assert east["wind_direction_deg"] == 90.0
    assert east["wind_speed_m_s"] == own["wind_speed_m_s"]
    assert east["air_temperature_c"] == own["air_temperature_c"]
    assert (clouded["wind_direction_deg"], clouded["cloud_cover_pct"]) == (0.0, 80.0)
    # From the west, its own at noon, the wind blows in through the front
    # door; from the north, the house draws out through it.
    assert own["wind_direction_deg"] == 270.0
    assert _door_flow("default") > 10.0
    assert _door_flow("default~0") < 0.0
    for refused in ("default~360", "default~-5", "default~east"):
        response = respond(
            "GET", f"/api/scenarios/reference_greenhouse/weather?t=0&weather={refused}"
        )
        assert response.status == HTTPStatus.BAD_REQUEST
