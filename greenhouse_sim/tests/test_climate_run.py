"""A climate run (P05.3): the air through time on its own clock, applying
its schedule's commands at their moments, the same every time it is run."""

import numpy as np

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
