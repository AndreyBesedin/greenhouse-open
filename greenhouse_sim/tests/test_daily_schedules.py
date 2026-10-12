"""Daily schedules (P09.2): a command at a time of day, every day of a run,
as if it were given on each day, and overridden by one given for its moment.

The climate box's runs last its 14 days; its heater runs from 18 h to 22 h.
"""

from http import HTTPStatus
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Command, DailyCommand
from greenhouse_sim.core.clock import DAY_S

EVENINGS = "64800:heater:1,79200:heater:0"
# The same evenings, as commands on each of the first two days.
TWO_EVENINGS = "64800:heater:1,79200:heater:0,151200:heater:1,165600:heater:0"
TWO_DAYS = f"t={2 * DAY_S:.0f}&from=0"


def _house(query: str) -> dict[str, Any]:
    response = respond("GET", f"/api/scenarios/climate_box/climate/house?{query}")
    assert response.status == HTTPStatus.OK, response.body
    assert isinstance(response.body, dict)
    return response.body


def _at(body: dict[str, Any], time_s: float) -> float:
    temperature: float = body["controlled"]["temperature_c"][body["times_s"].index(time_s)]
    return temperature


def test_a_daily_command_is_a_command_on_each_day() -> None:
    evening = DailyCommand(time_of_day_s=64_800.0, actuator_id="heater", level=1.0)

    assert evening.through(3) == [
        Command(time_s=time_s, actuator_id="heater", level=1.0)
        for time_s in (64_800.0, 151_200.0, 237_600.0)
    ]


def test_a_daily_schedule_runs_as_its_commands_on_each_day() -> None:
    daily = _house(f"{TWO_DAYS}&daily={EVENINGS}")
    given = _house(f"{TWO_DAYS}&schedule={TWO_EVENINGS}")
    off = _house(TWO_DAYS)

    assert daily["controlled"] == given["controlled"]
    # Warmer every evening than without it, and the same at each day's start.
    for evening in (72_000.0, DAY_S + 72_000.0):
        assert _at(daily, evening) > _at(off, evening) + 1.0
    assert _at(daily, 3600.0) == _at(off, 3600.0)


def test_a_command_for_a_moment_overrides_the_days_then() -> None:
    overridden = _house(f"{TWO_DAYS}&daily=64800:heater:1&schedule=64800:heater:0")
    second_day_only = _house(f"{TWO_DAYS}&schedule=151200:heater:1")

    assert overridden["controlled"]["temperature_c"] == pytest.approx(
        second_day_only["controlled"]["temperature_c"]
    )


def test_the_sensors_read_a_daily_schedules_run() -> None:
    path = "/api/scenarios/climate_box/climate/truth?t=162000"
    daily = respond("GET", f"{path}&daily={EVENINGS}")
    off = respond("GET", path)

    assert daily.status == off.status == HTTPStatus.OK
    assert isinstance(daily.body, dict) and isinstance(off.body, dict)
    assert daily.body != off.body


@pytest.mark.parametrize(
    ("daily", "error"),
    [
        (
            "86400:heater:1",
            "a daily command's time of day lies from 0 to 86400 s, before the next midnight: 86400",
        ),
        ("64800:heater:2", "a level runs from 0 to 1: heater"),
        ("64800:boiler:1", "climate_box has no equipment 'boiler'"),
        ("evening:heater:1", "daily wants seconds:actuator:level commands, not 'evening:heater:1'"),
    ],
)
def test_a_daily_command_outside_a_day_or_the_house_is_refused(daily: str, error: str) -> None:
    response = respond("GET", f"/api/scenarios/climate_box/climate/house?daily={daily}")

    assert (response.status, response.body) == (HTTPStatus.BAD_REQUEST, {"error": error})
