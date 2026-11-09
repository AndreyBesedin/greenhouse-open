"""A scenario's own daily commands (P09.4): the reference run vents and
stirs its house by the clock every day, as its manifest says, unless a run
gives daily commands of its own, and heats it by its thermostat (P10.3); and
its sensors observe the season it makes, only through the observation
path."""

import sys
from collections.abc import Iterator, Mapping
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import DailyCommand
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services import climate_runs, fields, sensors
from greenhouse_sim.services.runs import Commanded, RunPlan, RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.sensors import PointSensor

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

REFERENCE = SCENARIO_REGISTRY["reference_greenhouse"]
HOUR_S: Final = 3600.0
# The reference run's third day: its small hours, heated to the night's
# setpoint, and its noon, to the day's.
SMALL_HOURS_S: Final = 2 * DAY_S + 3 * HOUR_S
NOON_S: Final = 2 * DAY_S + 12 * HOUR_S
# Outside, as on a March night, in °C.
COLD_NIGHT_C: Final = 2.0


@pytest.fixture(scope="module")
def of_its_season() -> Iterator[Simulator]:
    """A simulator of its first days, its air the whole house's: what a door
    passes follows the wind, whichever model works its air out."""
    with simulator_of(cut("reference_greenhouse", days=2, season=True)) as made:
        yield made


@pytest.fixture
def on_a_march_night() -> Iterator[Simulator]:
    """A simulator of its house in the dark at near freezing, whose thermostat
    is all there is to warm it, and whose third day is seconds away."""
    cold = ConstantWeather(air_temperature_c=COLD_NIGHT_C)
    with simulator_of(cut("reference_greenhouse", weather=cold)) as made:
        yield made


def _own() -> list[tuple[float, str, float]]:
    return [(c.time_of_day_s, c.actuator_id, c.level) for c in REFERENCE.daily]


def _body(simulator: Simulator, path: str) -> dict[str, Any]:
    response = respond(simulator, "GET", path)
    assert response.status == HTTPStatus.OK, response.body
    assert isinstance(response.body, dict)
    return response.body


def test_the_reference_run_vents_and_stirs_its_house_by_the_clock_and_heats_it_by_the_air() -> None:
    actuators = {command.actuator_id for command in REFERENCE.daily}

    assert REFERENCE.thermostat is not None
    assert REFERENCE.thermostat.actuator_id == "heater"
    assert actuators == {
        "fan_left",
        "fan_right",
        "roof_vent_1",
        "roof_vent_2",
        "roof_vent_3",
    }
    # Every other scenario's runs give none of their own, but the TOMGRO and
    # Vanthoor houses', which keep the reference greenhouse's.
    kept = ("tomgro_house", "vanthoor_house")
    assert all(SCENARIO_REGISTRY[house].daily == REFERENCE.daily for house in kept)
    others = [
        s
        for s in SCENARIO_REGISTRY.values()
        if s.greenhouse_id not in (REFERENCE.greenhouse_id, *kept)
    ]
    assert all(other.daily == [] for other in others)


def test_a_run_gives_its_scenarios_daily_commands_unless_it_gives_its_own() -> None:
    own = climate_runs.run_schedule(PACKAGED, RunRequest("reference_greenhouse"))
    replaced = climate_runs.run_schedule(
        PACKAGED,
        RunRequest(
            "reference_greenhouse", plan=RunPlan.requested(daily=((64800.0, "heater", 1.0),))
        ),
    )
    none = climate_runs.run_schedule(
        PACKAGED, RunRequest("reference_greenhouse", plan=RunPlan.requested(daily=()))
    )

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


def test_the_api_reads_daily_none_as_none_and_leaves_out_none_as_its_own(
    simulator: Simulator,
) -> None:
    own = _body(simulator, "/api/scenarios/reference_greenhouse/timeline?t=86400")
    none = _body(simulator, "/api/scenarios/reference_greenhouse/timeline?t=86400&daily=none")
    commands = own["processes"].index("commands")

    assert own["process"].count(commands) == len(REFERENCE.daily)
    assert none["process"].count(commands) == 0
    summaries = respond(simulator, "GET", "/api/scenarios").body
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


def _reading(
    simulator: Simulator,
    time_s: float,
    daily: tuple[Commanded, ...] | None = None,
    levels: Mapping[str, float] | None = None,
) -> float:
    """What the front temperature sensor, a clean one, observed at `time_s`."""
    log = sensors.observations(
        simulator,
        RunRequest(
            "reference_greenhouse", levels=levels or {}, plan=RunPlan.requested(daily=daily)
        ),
        until_s=time_s,
        from_s=time_s - 60.0,
    )
    return next(
        o.value
        for o in log.observations
        if o.sensor_id == "temperature_front"
        and o.timestamp == REFERENCE.run_start() + timedelta(seconds=time_s)
    )


def test_the_thermostats_setpoints_show_in_the_readings(on_a_march_night: Simulator) -> None:
    small_hours = _reading(on_a_march_night, SMALL_HOURS_S)
    noon = _reading(on_a_march_night, NOON_S)
    unheated = _reading(
        on_a_march_night,
        SMALL_HOURS_S,
        daily=(),
        levels=climate_runs.off_levels(PACKAGED, "reference_greenhouse"),
    )

    # Near 16 °C at night and 18 °C by day, a sensor's error and the
    # thermostat's band either way, well above what an unheated house falls
    # to on a March night.
    assert small_hours == pytest.approx(16.0, abs=1.5)
    assert noon == pytest.approx(18.0, abs=1.5)
    assert small_hours > unheated + 5.0


def test_its_sensors_observe_only_the_run_they_belong_to_through_the_season(
    simulator: Simulator,
) -> None:
    sensor = next(s for s in REFERENCE.layout.sensors if s.sensor_id == "temperature_front")
    assert isinstance(sensor, PointSensor)
    air, run_id = fields.air_through_a_run(simulator, RunRequest("reference_greenhouse"))
    log = sensors.observations(
        simulator,
        RunRequest("reference_greenhouse"),
        until_s=SMALL_HOURS_S,
        clean=True,
        from_s=SMALL_HOURS_S - 300.0,
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


def _door_flow(simulator: Simulator, weather: str) -> float:
    body = _body(
        simulator,
        f"/api/scenarios/reference_greenhouse/climate/openings?t=43200&open=door:1&weather={weather}",
    )
    return float(next(o["net_m3_s"] for o in body["openings"] if o["opening_id"] == "door"))


def test_the_winds_direction_can_be_overridden_for_qa_and_an_open_door_follows_it(
    of_its_season: Simulator,
) -> None:
    own = _body(of_its_season, "/api/scenarios/reference_greenhouse/weather?t=43200")["weather"]
    east = _body(
        of_its_season, "/api/scenarios/reference_greenhouse/weather?t=43200&weather=default~90"
    )["weather"]
    clouded = _body(
        of_its_season,
        "/api/scenarios/reference_greenhouse/weather?t=43200&weather=cold_spring_day@80~0",
    )["weather"]

    # Only its direction turns: its speed is its own, and so is the rest.
    assert east["wind_direction_deg"] == 90.0
    assert east["wind_speed_m_s"] == own["wind_speed_m_s"]
    assert east["air_temperature_c"] == own["air_temperature_c"]
    assert (clouded["wind_direction_deg"], clouded["cloud_cover_pct"]) == (0.0, 80.0)
    # From the west, its own at noon, the wind blows in through the front
    # door; from the north, the house draws out through it.
    assert own["wind_direction_deg"] == 270.0
    assert _door_flow(of_its_season, "default") > 10.0
    assert _door_flow(of_its_season, "default~0") < 0.0
    for refused in ("default~360", "default~-5", "default~east"):
        response = respond(
            of_its_season,
            "GET",
            f"/api/scenarios/reference_greenhouse/weather?t=0&weather={refused}",
        )
        assert response.status == HTTPStatus.BAD_REQUEST
