"""Daily schedules (P09.2): a command at a time of day, every day of a run,
as if it were given on each day, and overridden by one given for its moment.

The climate box's runs last its 14 days; its heater runs from 18 h to 22 h.
"""

import sys
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Command, DailyCommand
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

EVENINGS = "64800:heater:1,79200:heater:0"
# The same evenings, as commands on each of the first two days.
TWO_EVENINGS = "64800:heater:1,79200:heater:0,151200:heater:1,165600:heater:0"
TWO_DAYS = f"t={2 * DAY_S:.0f}&from=0"


def _house(simulator: Simulator, query: str) -> dict[str, Any]:
    response = respond(simulator, "GET", f"/api/scenarios/climate_box/climate/house?{query}")
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


def test_a_daily_schedule_runs_as_its_commands_on_each_day(simulator: Simulator) -> None:
    daily = _house(simulator, f"{TWO_DAYS}&daily={EVENINGS}")
    given = _house(simulator, f"{TWO_DAYS}&schedule={TWO_EVENINGS}")
    off = _house(simulator, TWO_DAYS)

    assert daily["controlled"] == given["controlled"]
    # Warmer every evening than without it, and the same at each day's start.
    for evening in (72_000.0, DAY_S + 72_000.0):
        assert _at(daily, evening) > _at(off, evening) + 1.0
    assert _at(daily, 3600.0) == _at(off, 3600.0)


def test_a_command_for_a_moment_overrides_the_days_then(simulator: Simulator) -> None:
    overridden = _house(simulator, f"{TWO_DAYS}&daily=64800:heater:1&schedule=64800:heater:0")
    second_day_only = _house(simulator, f"{TWO_DAYS}&schedule=151200:heater:1")

    assert overridden["controlled"]["temperature_c"] == pytest.approx(
        second_day_only["controlled"]["temperature_c"]
    )


def test_the_sensors_read_a_daily_schedules_run() -> None:
    # What its heater makes of the air, whichever model of the air a run has.
    def truth(simulator: Simulator, time_s: float, query: str = "") -> dict[str, Any]:
        path = f"/api/scenarios/climate_box/climate/truth?t={time_s:.0f}{query}"
        response = respond(simulator, "GET", path)
        assert response.status == HTTPStatus.OK, response.body
        assert isinstance(response.body, dict)
        (sensor,) = response.body["sensors"]
        assert isinstance(sensor, dict)
        return sensor

    box = cut("climate_box", days=2, sensors=("temperature_front",))
    first_evening_s, second_evening_s = 72_000.0, DAY_S + 72_000.0
    with simulator_of(box) as simulator:
        heated = truth(simulator, first_evening_s, f"&daily={EVENINGS}")
        unheated = truth(simulator, first_evening_s)
        heated_on = truth(simulator, second_evening_s, f"&daily={EVENINGS}")
        unheated_on = truth(simulator, second_evening_s)

    # Its readings are the unheated house's until the first evening's heat,
    # warmer through it, and through the next evening's too.
    assert heated["times_s"] == unheated["times_s"]
    evening = next(n for n, time_s in enumerate(heated["times_s"]) if time_s > 64_800.0)
    assert evening > 0
    assert heated["values"][:evening] == unheated["values"][:evening]
    assert heated["values"][-1] > unheated["values"][-1] + 1.0
    assert heated_on["values"][-1] > unheated_on["values"][-1] + 1.0


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
def test_a_daily_command_outside_a_day_or_the_house_is_refused(
    simulator: Simulator, daily: str, error: str
) -> None:
    response = respond(simulator, "GET", f"/api/scenarios/climate_box/climate/house?daily={daily}")

    assert (response.status, response.body) == (HTTPStatus.BAD_REQUEST, {"error": error})
