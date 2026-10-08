"""A climate run's schedule as a client asks for it (P05.6): commands at
their moments after the levels set from the start, an override taking
effect from its moment on, the same schedule replaying to the same air, and
commands a scenario cannot run refused."""

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.services import fields


def _climate(query: str) -> EnvironmentField:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _temperature(query: str) -> np.ndarray:
    return _climate(query).channels[AirQuantity.TEMPERATURE]


def test_scheduled_commands_switch_the_equipment_on_their_own() -> None:
    scheduled = _climate("?schedule=60:fan:1,120:heater:1&t=600")
    started = _climate("?set=fan:1,heater:1&t=600")

    assert np.abs(scheduled.channels[AirQuantity.VELOCITY]).max() > 4.0
    # Switched on a minute or two late, the house is a little cooler.
    assert (
        0.0
        < (
            started.channels[AirQuantity.TEMPERATURE] - scheduled.channels[AirQuantity.TEMPERATURE]
        ).mean()
    )
    assert np.abs(_climate("?schedule=60:fan:1&t=30").channels[AirQuantity.VELOCITY]).max() == 0.0


def test_an_override_takes_effect_from_its_moment_on() -> None:
    overridden = "?set=heater:1&schedule=300:heater:0"

    np.testing.assert_array_equal(
        _temperature(f"{overridden}&t=300"), _temperature("?set=heater:1&t=300")
    )
    assert (
        _temperature(f"{overridden}&t=600").mean() < _temperature("?set=heater:1&t=600").mean() - 3
    )


def test_the_later_command_at_a_moment_wins() -> None:
    np.testing.assert_array_equal(
        _temperature("?schedule=0:heater:1,0:heater:0&t=300"), _temperature("?t=300")
    )
    np.testing.assert_array_equal(
        _temperature("?set=heater:1&schedule=0:heater:0&t=300"), _temperature("?t=300")
    )


def test_the_same_schedule_replays_to_the_same_air() -> None:
    query = "?set=fan:0.5&schedule=120:heater:1,240:dehumidifier:1,360:fan:0&t=480"
    first = fields.field(
        "climate_box",
        "climate",
        levels={"fan": 0.5},
        time_s=480,
        commands=[(120, "heater", 1), (240, "dehumidifier", 1), (360, "fan", 0)],
    )
    # Run afresh, not found among the kept runs.
    fields.forget_climate_runs()
    again = _climate(query)

    for quantity in (AirQuantity.VELOCITY, AirQuantity.TEMPERATURE, AirQuantity.HUMIDITY):
        np.testing.assert_array_equal(
            EnvironmentField.from_document(first).channels[quantity], again.channels[quantity]
        )


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("?schedule=60:boiler:1", "climate_box has no equipment 'boiler'"),
        ("?schedule=60:fan:2,120:fan:1", "a level runs from 0 to 1: fan"),
        ("?schedule=4000:fan:1", "a command's moment lies within the run, 0 to 3600 s: 4000"),
        ("?schedule=-1:fan:1", "a command's moment lies within the run, 0 to 3600 s: -1"),
        (
            "?schedule=soon:fan:1",
            "schedule wants seconds:actuator:level commands, not 'soon:fan:1'",
        ),
        ("?schedule=60:fan", "schedule wants seconds:actuator:level commands, not '60:fan'"),
    ],
    ids=["unknown", "above full", "after the run", "before it", "not a moment", "no level"],
)
def test_commands_a_scenario_cannot_run_are_refused(query: str, error: str) -> None:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")

    assert (response.status, response.body) == (400, {"error": error})
