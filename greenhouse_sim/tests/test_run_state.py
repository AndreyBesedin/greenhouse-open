"""What each process of a run holds at a moment (P09.6), for QA mode's
developer panel: each part is what its own service says at that moment."""

from datetime import timedelta
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Command
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import fields, sensors
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.run_state import LATEST_COMMANDS, RunState, run_state

HEATED = {"heater": 1.0}
# Ten minutes into the climate box's heated run, and noon on the reference
# greenhouse's second day.
TEN_MINUTES_S = 600.0
NOON_S = 43_200.0
SECOND_NOON_S = DAY_S + NOON_S


def test_the_clock_and_the_house_air_are_the_runs_at_the_moment() -> None:
    state = run_state("climate_box", levels=HEATED, until_s=TEN_MINUTES_S)
    trace = fields.house_air("climate_box", levels=HEATED, until_s=TEN_MINUTES_S)

    assert (state.time_s, state.day) == (TEN_MINUTES_S, 0)
    assert state.at == state.start + timedelta(seconds=TEN_MINUTES_S)
    assert state.start == sensors.run_start("climate_box")
    assert state.house_air is not None
    assert state.house_air.temperature_c == pytest.approx(trace.controlled.temperature_c[-1])
    assert state.house_air.humidity_pct == pytest.approx(trace.controlled.humidity_pct[-1])
    assert state.house_air.co2_ppm == pytest.approx(trace.controlled.co2_ppm[-1])


def test_the_sensors_and_cameras_stand_as_the_observation_log_says() -> None:
    state = run_state("climate_box", levels=HEATED, until_s=TEN_MINUTES_S)
    log = sensors.observations("climate_box", levels=HEATED, until_s=TEN_MINUTES_S)

    assert state.run_id == log.run_id
    assert state.sensors == log.freshness
    # A frame a minute from the start, the latest the log's last.
    (camera,) = state.cameras
    assert (camera.sensor_id, camera.frames) == ("front_camera", 11)
    assert camera.latest == log.frames[-1]


def test_the_equipment_doors_and_vents_stand_as_the_commands_set_them() -> None:
    state = run_state("reference_greenhouse", until_s=SECOND_NOON_S)

    # By noon its own schedule has the fans on, the heater off and the roof
    # vents fully open; the door stays shut.
    assert state.levels == {
        "fan_left": 1.0,
        "fan_right": 1.0,
        "heater": 0.0,
        "dehumidifier": 0.0,
        "roof_vent_1": 1.0,
        "roof_vent_2": 1.0,
        "roof_vent_3": 1.0,
        "door": 0.0,
    }
    assert len(state.latest_commands) == LATEST_COMMANDS
    assert state.latest_commands[-1] == Command(
        time_s=DAY_S + 11 * 3600, actuator_id="roof_vent_3", level=1.0
    )
    assert state.commands_given > LATEST_COMMANDS
    # Its crop has lived its first day.
    assert (state.crop_model, state.plants, state.days_lived) == ("organ", 32, 1)


def test_a_door_open_from_the_start_stands_open_until_commanded() -> None:
    opened = run_state(
        "climate_box",
        openings={"door": 0.5},
        commands=[(300.0, "door", 0.0)],
        until_s=TEN_MINUTES_S,
    )
    before = run_state("climate_box", openings={"door": 0.5}, until_s=TEN_MINUTES_S)

    assert before.levels["door"] == 0.5
    assert opened.levels["door"] == 0.0
    assert opened.latest_commands == [Command(time_s=300.0, actuator_id="door", level=0.0)]


def test_a_house_without_equipment_has_no_climate_run_to_hold_air() -> None:
    state = run_state("airflow_box", until_s=TEN_MINUTES_S)

    assert state.house_air is None
    # Its doors stand open as its envelope has them, and nothing commands
    # them.
    assert state.levels == {"door_front": 1.0, "door_back": 1.0}
    assert (state.commands_given, state.latest_commands) == (0, [])
    assert (state.crop_model, state.days_lived) == ("simple", 0)


def test_the_state_is_refused_as_its_run_is() -> None:
    with pytest.raises(NotFound):
        run_state("nowhere")
    with pytest.raises(InvalidRequest, match="lasts from 0"):
        run_state("climate_box", until_s=100 * DAY_S)
    with pytest.raises(InvalidRequest):
        run_state("climate_box", levels={"sprinkler": 1.0})


def test_the_api_serves_it_asked_as_the_climate_is() -> None:
    answer = respond("GET", "/api/scenarios/climate_box/climate/state?set=heater:1&t=600")

    assert answer.status == HTTPStatus.OK
    served = RunState.model_validate(answer.body)
    assert served == run_state("climate_box", levels=HEATED, until_s=TEN_MINUTES_S)
    beyond = respond("GET", "/api/scenarios/climate_box/climate/state?t=99999999")
    assert beyond.status == HTTPStatus.BAD_REQUEST
