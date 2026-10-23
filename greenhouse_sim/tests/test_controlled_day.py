"""A controlled and an uncontrolled day (P07.8): the climate box under the
cold spring day, once with nothing running and once heated through the
nights and vented with the fan on through the middle of the day, its roof
vent opened and shut by its schedule."""

from collections.abc import Callable
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.house import HouseTrace
from greenhouse_sim.services import climate_readings, sensors
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.simulator import Simulator

HOUR_S = 3600.0
SPRING = "cold_spring_day"
# Heated until eight and again from six; the roof vent half open and the fan
# on from eleven to four.
SCHEDULE = (
    (8 * HOUR_S, "heater", 0.0),
    (11 * HOUR_S, "roof_vent", 0.5),
    (11 * HOUR_S, "fan", 1.0),
    (16 * HOUR_S, "roof_vent", 0.0),
    (16 * HOUR_S, "fan", 0.0),
    (18 * HOUR_S, "heater", 1.0),
)
HEATED = {"heater": 1.0}


def _controlled(simulator: Simulator, until_s: float) -> HouseTrace:
    return climate_readings.house_air(
        simulator,
        RunRequest(
            "climate_box", levels=HEATED, weather=SPRING, plan=RunPlan.requested(commands=SCHEDULE)
        ),
        until_s=until_s,
    )


def test_a_schedule_opens_and_shuts_a_vent(simulator: Simulator) -> None:
    def opened(moment: float) -> dict[str, float]:
        at = climate_readings.openings(
            simulator,
            RunRequest(
                "climate_box",
                levels=HEATED,
                weather=SPRING,
                plan=RunPlan.requested(commands=SCHEDULE),
            ),
            time_s=moment,
        )
        return {flow.opening_id: flow.exchange_m3_s for flow in at.openings}

    assert opened(10 * HOUR_S) == {}
    assert opened(13 * HOUR_S)["roof_vent"] > 0.0
    assert opened(17 * HOUR_S) == {}


def test_the_controlled_house_is_warmer_through_the_night(simulator: Simulator) -> None:
    trace = _controlled(simulator, 24 * HOUR_S)
    by_hour = {round(time / HOUR_S, 6): index for index, time in enumerate(trace.times_s)}
    controlled, unheated = trace.controlled.temperature_c, trace.all_off.temperature_c

    for hour in (*range(1, 8), *range(19, 24)):
        index = by_hour[hour]
        assert controlled[index] > unheated[index] + 3.0, hour
    # Vented through the afternoon, it is no warmer than a few degrees above
    # the unheated house.
    afternoon = by_hour[14]
    assert controlled[afternoon] < unheated[afternoon] + 3.0


def test_the_two_runs_diverge_as_the_night_falls(simulator: Simulator) -> None:
    trace = _controlled(simulator, 24 * HOUR_S)
    gap = [
        c - u
        for c, u in zip(trace.controlled.temperature_c, trace.all_off.temperature_c, strict=True)
    ]
    by_hour = {round(time / HOUR_S, 6): index for index, time in enumerate(trace.times_s)}

    assert gap[by_hour[17]] < gap[by_hour[20]] - 3.0


def test_both_runs_replay_exactly(simulator: Simulator, afresh: Callable[[], None]) -> None:
    first = _controlled(simulator, 6 * HOUR_S)
    afresh()
    again = _controlled(simulator, 6 * HOUR_S)

    assert first == again
    observed = sensors.observations(
        simulator,
        RunRequest(
            "climate_box", levels=HEATED, weather=SPRING, plan=RunPlan.requested(commands=SCHEDULE)
        ),
        until_s=1800.0,
    )
    afresh()
    replayed = sensors.observations(
        simulator,
        RunRequest(
            "climate_box", levels=HEATED, weather=SPRING, plan=RunPlan.requested(commands=SCHEDULE)
        ),
        until_s=1800.0,
    )
    assert observed == replayed


@pytest.mark.parametrize(
    ("schedule", "status"),
    [
        ("3600:roof_vent:0.5", HTTPStatus.OK),
        ("3600:skylight:0.5", HTTPStatus.BAD_REQUEST),
        ("3600:roof_vent:2", HTTPStatus.BAD_REQUEST),
    ],
)
def test_the_api_takes_commands_to_doors_and_vents(
    simulator: Simulator, schedule: str, status: HTTPStatus
) -> None:
    path = f"/api/scenarios/climate_box/climate/openings?schedule={schedule}&t=4000"
    assert respond(simulator, "GET", path).status == status
