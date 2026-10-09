"""A climate run through a day (P07.3): the field at a moment from a grid
run started from the whole house an hour before its hour, sensors sampling
the same air however late a run is looked at, and the API taking a day."""

import json
from http import HTTPStatus

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.day import FROM_THE_START_S, HOUR_S, ClimateDay, window_start
from greenhouse_sim.climate.house import grid_mean
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.services import fields, sensors
from greenhouse_sim.services.fields import _climate_day

HEATED = (("heater", 1.0),)
# How closely a later grid run's mean follows the whole house after its
# hour's spin-up, in a shut, heated house (as `test_whole_house` measures).
SHUT_TEMPERATURE_C = 0.3


def _day(commands: tuple[tuple[float, str, float], ...] = ()) -> ClimateDay:
    return _climate_day("climate_box", "default", "default", HEATED, (), commands)


@pytest.mark.parametrize(
    ("moment", "start"),
    [(0.0, 0.0), (3599.0, 0.0), (7199.0, 0.0), (7200.0, 3600.0), (5.5 * HOUR_S, 4 * HOUR_S)],
)
def test_the_field_at_a_moment_is_drawn_from_an_hour_before_its_hour(
    moment: float, start: float
) -> None:
    assert window_start(moment) == start


def test_through_its_first_two_hours_the_field_is_the_grid_run_from_the_start() -> None:
    day = _day()

    assert day.window(5400.0) is day.run
    np.testing.assert_array_equal(
        day.field("f", 5400.0).channels[AirQuantity.TEMPERATURE],
        day.run.field("f", day.run.grid, 5400.0).channels[AirQuantity.TEMPERATURE],
    )


def test_later_the_field_comes_from_a_grid_run_started_from_the_whole_house() -> None:
    day = _day()
    window = day.window(4.5 * HOUR_S)
    house = day.house.air_at(3 * HOUR_S)
    started = window.air_at(3 * HOUR_S)
    air = ~window.solid

    assert window.start_s == 3 * HOUR_S
    np.testing.assert_allclose(started.temperature[air], house.temperature_c)
    np.testing.assert_allclose(started.humidity[air], house.humidity_g_kg)
    # An hour on, the grid has taken its shape about the whole house's mean.
    mixed, mean = day.house.air_at(4 * HOUR_S), grid_mean(window, 4 * HOUR_S)
    assert mean.temperature_c == pytest.approx(mixed.temperature_c, abs=SHUT_TEMPERATURE_C)
    temperature = window.air_at(4 * HOUR_S).temperature[air]
    assert temperature.max() - temperature.min() > 1.0


def test_scrubbing_within_an_hour_carries_one_grid_run_on() -> None:
    day = _day()

    assert day.window(4.1 * HOUR_S) is day.window(4.9 * HOUR_S)
    assert day.window(5.0 * HOUR_S) is not day.window(4.9 * HOUR_S)
    with pytest.raises(ValueError, match="starts at 10800"):
        day.window(4.5 * HOUR_S).air_at(2 * HOUR_S)


def test_an_override_later_in_the_day_carries_on_from_the_air_before_it() -> None:
    day = _day()
    day.field("f", 4.5 * HOUR_S)
    override = _day(((4.5 * HOUR_S, "heater", 0.0),))

    # The air up to the override is the same air, taken over, not run again.
    window = override.window(4.75 * HOUR_S)
    assert window.air_at(4.5 * HOUR_S) is day.window(4.5 * HOUR_S).air_at(4.5 * HOUR_S)


def test_sensors_sample_the_grid_then_the_whole_house() -> None:
    log = sensors.observations(
        "climate_box", levels={"heater": 1.0}, until_s=3 * HOUR_S, clean=True
    )
    by_sensor: dict[str, dict[float, float]] = {}
    for o in log.observations:
        seconds = (o.timestamp - log.start).total_seconds()
        by_sensor.setdefault(o.sensor_id or "", {})[seconds] = o.value
    front, back = by_sensor["temperature_front"], by_sensor["temperature_back"]

    # Through the first two hours the back, by the heater, is the warmer.
    assert back[3600.0] > front[3600.0] + 1.0
    # After them both read the whole house's air.
    house = _day().house.air_at(2.5 * HOUR_S)
    assert front[2.5 * HOUR_S] == back[2.5 * HOUR_S] == pytest.approx(house.temperature_c)
    assert min(front) == 0.0
    assert max(front) == 3 * HOUR_S
    assert FROM_THE_START_S in front


def test_probes_read_the_grid_run_that_draws_the_moment() -> None:
    probes = fields.climate_probes(
        "climate_box", [(6.0, 3.2, 1.5)], levels={"heater": 1.0}, until_s=4.25 * HOUR_S
    )

    assert probes.times_s[0] == 3 * HOUR_S
    assert probes.times_s[-1] == 4.25 * HOUR_S
    assert len(probes.times_s) == 76


def test_the_api_takes_a_run_a_day_long() -> None:
    late = respond("GET", "/api/scenarios/climate_box/fields/climate?t=86400")
    house = respond("GET", "/api/scenarios/climate_box/climate/house?t=86400&set=heater:1")
    body = json.loads(json.dumps(house.body))

    assert late.status == house.status == HTTPStatus.OK
    assert len(body["times_s"]) == 24 * 60 + 1
    # Heated through a still, cold night, the house has long settled.
    assert body["controlled"]["temperature_c"][-1] == pytest.approx(
        body["controlled"]["temperature_c"][-60], abs=1e-6
    )
