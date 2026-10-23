"""A climate run's schedule as a client asks for it (P05.6): commands at
their moments after the levels set from the start, an override taking
effect from its moment on, the same schedule replaying to the same air, and
commands a scenario cannot run refused."""

import math
import random
from collections.abc import Callable

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Command, Schedule
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.services import fields
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator


def _climate(simulator: Simulator, query: str) -> EnvironmentField:
    response = respond(simulator, "GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _temperature(simulator: Simulator, query: str) -> np.ndarray:
    return _climate(simulator, query).channels[AirQuantity.TEMPERATURE]


def _same_air(first: np.ndarray, second: np.ndarray) -> None:
    """The same air, to the last bits of its published 32-bit floats: a kept
    run carries on from the latest moment it has, in steps that round
    differently from a run's from its start."""
    np.testing.assert_allclose(first, second, rtol=0, atol=1e-5)


def test_scheduled_commands_switch_the_equipment_on_their_own(simulator: Simulator) -> None:
    scheduled = _climate(simulator, "?schedule=60:fan:1,120:heater:1&t=600")
    started = _climate(simulator, "?set=fan:1,heater:1&t=600")

    assert np.abs(scheduled.channels[AirQuantity.VELOCITY]).max() > 4.0
    # Switched on a minute or two late, the house is a little cooler.
    assert (
        0.0
        < (
            started.channels[AirQuantity.TEMPERATURE] - scheduled.channels[AirQuantity.TEMPERATURE]
        ).mean()
    )
    assert (
        np.abs(_climate(simulator, "?schedule=60:fan:1&t=30").channels[AirQuantity.VELOCITY]).max()
        == 0.0
    )


def test_an_override_takes_effect_from_its_moment_on(simulator: Simulator) -> None:
    overridden = "?set=heater:1&schedule=300:heater:0"

    _same_air(
        _temperature(simulator, f"{overridden}&t=300"),
        _temperature(simulator, "?set=heater:1&t=300"),
    )
    assert (
        _temperature(simulator, f"{overridden}&t=600").mean()
        < _temperature(simulator, "?set=heater:1&t=600").mean() - 3
    )


def test_the_later_command_at_a_moment_wins(simulator: Simulator) -> None:
    _same_air(
        _temperature(simulator, "?schedule=0:heater:1,0:heater:0&t=300"),
        _temperature(simulator, "?t=300"),
    )
    _same_air(
        _temperature(simulator, "?set=heater:1&schedule=0:heater:0&t=300"),
        _temperature(simulator, "?t=300"),
    )


def test_the_same_schedule_replays_to_the_same_air(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    query = "?set=fan:0.5&schedule=120:heater:1,240:dehumidifier:1,360:fan:0&t=480"
    # Each run afresh, not found among the kept runs.
    first = fields.field(
        RunRequest(
            "climate_box",
            levels={"fan": 0.5},
            commands=((120, "heater", 1), (240, "dehumidifier", 1), (360, "fan", 0)),
        ),
        "climate",
        time_s=480,
    )
    afresh()
    again = _climate(simulator, query)

    for quantity in (AirQuantity.VELOCITY, AirQuantity.TEMPERATURE, AirQuantity.HUMIDITY):
        np.testing.assert_array_equal(
            EnvironmentField.from_document(first).channels[quantity], again.channels[quantity]
        )


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("?schedule=60:boiler:1", "climate_box has no equipment 'boiler'"),
        ("?schedule=60:fan:2,120:fan:1", "a level runs from 0 to 1: fan"),
        (
            "?schedule=1300000:fan:1",
            "a command's moment lies within the run, 0 to 1209600 s: 1300000",
        ),
        ("?schedule=-1:fan:1", "a command's moment lies within the run, 0 to 1209600 s: -1"),
        (
            "?schedule=soon:fan:1",
            "schedule wants seconds:actuator:level commands, not 'soon:fan:1'",
        ),
        ("?schedule=60:fan", "schedule wants seconds:actuator:level commands, not '60:fan'"),
    ],
    ids=["unknown", "above full", "after the run", "before it", "not a moment", "no level"],
)
def test_commands_a_scenario_cannot_run_are_refused(
    simulator: Simulator, query: str, error: str
) -> None:
    response = respond(simulator, "GET", f"/api/scenarios/climate_box/fields/climate{query}")

    assert (response.status, response.body) == (400, {"error": error})


def test_two_schedules_are_the_same_until_the_first_command_they_differ_in() -> None:
    heater_on = Command(time_s=60.0, actuator_id="heater", level=1.0)
    fan_on = Command(time_s=120.0, actuator_id="fan", level=1.0)
    fan_half = Command(time_s=120.0, actuator_id="fan", level=0.5)
    heater_off = Command(time_s=300.0, actuator_id="heater", level=0.0)
    both = Schedule.of([heater_on, fan_on])

    assert both.same_until(Schedule.of([heater_on, fan_on])) == math.inf
    assert both.same_until(Schedule.of([heater_on, fan_half])) == 120.0
    assert both.same_until(Schedule.of([heater_on])) == 120.0
    assert both.same_until(Schedule.of([heater_on, fan_on, heater_off])) == 300.0
    assert both.same_until(Schedule()) == 60.0


def test_the_schedule_read_by_moment_is_the_schedule_read_through() -> None:
    # A schedule is indexed by moment for a season's thousands of commands;
    # read through from the start, it gives the same commands and levels, a
    # later command at one moment winning, as it does to an actuator twice.
    draws = random.Random(3)
    actuators = ("heater", "fan", "roof_vent", "door")
    schedule = Schedule.of(
        Command(
            time_s=float(draws.randrange(0, 50, 5)),
            actuator_id=draws.choice(actuators),
            level=round(draws.random(), 2),
        )
        for _ in range(60)
    )

    for moment in (step / 2 for step in range(-2, 110)):
        through = [c for c in schedule.commands if c.time_s <= moment]
        levels = dict.fromkeys(("heater", "fan", "unknown"), 0.0)
        for command in through:
            if command.actuator_id in levels:
                levels[command.actuator_id] = command.level
        assert schedule.applied(moment) == through
        assert schedule.levels_at(("heater", "fan", "unknown"), moment) == levels
        assert schedule.moments_between(moment, moment + 7.5) == sorted(
            {c.time_s for c in schedule.commands if moment < c.time_s <= moment + 7.5}
        )


def test_a_schedules_commands_cannot_change_under_its_indexes() -> None:
    # Read once, its indexes are kept: a command added afterwards would be
    # in its commands and not in what it applies.
    schedule = Schedule.of([Command(time_s=0.0, actuator_id="heater", level=1.0)])
    schedule.applied(0.0)

    with pytest.raises(AttributeError):
        schedule.commands.append(  # type: ignore[attr-defined]
            Command(time_s=10.0, actuator_id="fan", level=1.0)
        )
    assert schedule.applied(10.0) == list(schedule.commands)
