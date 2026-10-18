"""A climate run (P05.3): the air through time on its own clock, applying
its schedule's commands at their moments, the same every time it is run."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import NoReturn

import numpy as np
import pytest

from greenhouse_sim.climate.commands import Command, Schedule
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.grid import air_grid

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
SOLID = cfd.geometry("climate_box").solid()
AIR = ~SOLID


def _run(*commands: Command) -> ClimateRun:
    return ClimateRun(
        base=CONFIG.airflow,
        equipment=CONFIG.layout.equipment,
        schedule=Schedule.of(commands),
        settings=CONFIG.climate,
        grid=GRID,
        solid=SOLID,
        weather=CONFIG.run_weather(),
    )


def _at(time_s: float, actuator_id: str, level: float) -> Command:
    return Command(time_s=time_s, actuator_id=actuator_id, level=level)


def test_a_run_starts_from_its_starting_air_with_its_levels_as_scheduled() -> None:
    run = _run(_at(0, "heater", 1.0), _at(300, "fan", 0.5))

    assert (run.temperature_at(0.0) == CONFIG.climate.start_temperature_c).all()
    assert run.levels_at(0) == {"fan": 0.0, "heater": 1.0, "dehumidifier": 0.0}
    assert run.levels_at(300)["fan"] == 0.5
    assert not run.flows_at(0).velocity().any()
    assert run.flows_at(300).velocity().any()


def test_a_command_takes_effect_at_its_moment() -> None:
    switched_off = _run(_at(0, "heater", 1.0), _at(300, "heater", 0.0))
    kept_on = _run(_at(0, "heater", 1.0))
    never_on = _run()

    np.testing.assert_array_equal(switched_off.temperature_at(300), kept_on.temperature_at(300))
    later = switched_off.temperature_at(900)[AIR].mean()
    assert never_on.temperature_at(900)[AIR].mean() < later
    assert later < kept_on.temperature_at(900)[AIR].mean()


def test_the_same_schedule_gives_the_same_air_every_time() -> None:
    commands = (_at(0, "heater", 1.0), _at(120, "fan", 1.0), _at(480, "heater", 0.5))

    first = _run(*commands).temperature_at(600)
    again = _run(*commands).temperature_at(600)

    np.testing.assert_array_equal(first, again)


def test_a_later_moment_carries_on_from_the_latest_kept_before_it() -> None:
    commands = (_at(0, "heater", 1.0), _at(120, "fan", 1.0))
    asked_in_turn = _run(*commands)
    for moment in (600.0, 300.0, 900.0):
        asked_in_turn.temperature_at(moment)
    straight = _run(*commands).temperature_at(900)

    np.testing.assert_allclose(asked_in_turn.temperature_at(900), straight, atol=1e-9)


def test_its_air_is_the_same_whatever_moments_were_asked_for_before() -> None:
    # A viewer scrubbing a run asks for moments between its minutes: the
    # air later is worked out from the minutes kept, never from those.
    commands = (_at(0, "heater", 1.0), _at(150, "fan", 1.0))
    scrubbed = _run(*commands)
    for moment in (90.0, 170.0, 245.5):
        scrubbed.air_at(moment)
    alone = _run(*commands)

    for moment in (245.5, 300.0, 330.0):
        air, expected = scrubbed.air_at(moment), alone.air_at(moment)
        assert np.array_equal(air.temperature, expected.temperature)
        assert np.array_equal(air.humidity, expected.humidity)
        assert np.array_equal(air.co2, expected.co2)
    # Asked again, as a viewer's requests for one moment ask, it is not
    # worked out again.
    assert scrubbed.air_at(245.5) is scrubbed.air_at(245.5)


def test_it_carries_on_from_another_without_waiting_for_a_request_working_it_on(
    finishes_beside_held: Callable[[AbstractContextManager[bool], Callable[[], object]], bool],
) -> None:
    first = _run()
    first.air_at(600.0)
    second = _run()

    assert finishes_beside_held(first._working, lambda: second.carry_on_from(first))
    assert second._kept.keys() == first._kept.keys()


def test_it_takes_over_what_another_keeps_after_it_carried_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A branch made while a request works its source on does not wait for
    # it (above): what the source keeps afterwards, up to where their
    # schedules differ, is the branch's air too, and is not worked out again.
    first = _run()
    second = _run(_at(900, "heater", 1.0))
    second.carry_on_from(first)
    first.air_at(600.0)

    def not_again(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("the branch worked out a stretch its source had")

    monkeypatch.setattr(second, "_transport", not_again)
    assert second.air_at(600.0) is first.air_at(600.0)
