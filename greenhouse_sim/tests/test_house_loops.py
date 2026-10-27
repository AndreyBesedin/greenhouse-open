"""Every loop decided by the house's air (P11.2): the vents opened stage by
stage the moment the air passes each stage's edge and closed the moment it
falls back below it by the band; the fans run with the vents; a command
taking a vent out of the loop's hands; the grid following what the house
decides; a heating loop alone giving the run it gave as a thermostat; and a
checkpoint keeping how its vents stood."""

from collections.abc import Callable
from dataclasses import replace
from itertools import pairwise
from typing import Final

import pytest

from greenhouse_sim.climate.commands import Command, Schedule
from greenhouse_sim.climate.control import (
    CirculationLoop,
    Control,
    HeatingLoop,
    VentingLoop,
    VentStage,
)
from greenhouse_sim.climate.day import ClimateDay
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.thermostat import OFF, ON, Thermostat
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.services import cfd, checkpoints
from greenhouse_sim.services.climate_runs import climate_vents
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import SceneChanges, changed
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.weather.sources import ConstantWeather

BOX: Final = SCENARIO_REGISTRY["climate_box"]
HOUR_S: Final = 3600.0
MILD: Final = ConstantWeather(air_temperature_c=12.0)
# Two stages: a crack above 19 °C, wide open above 20.5 °C, each closing
# 1 °C below where it opened; the fan from the second. Heated full on in
# mild weather, the box settles near 20.9 °C with its vents cracked, past the
# second stage's edge, and near 17 °C with them wide open, below where the
# second closes: its vents go from one stage to the other, again and again.
VENTING: Final = VentingLoop(
    vents=["roof_vent", "side_vent"],
    day_c=19.0,
    night_c=19.0,
    band_c=1.0,
    stages=[VentStage(above_c=0.0, level=0.2), VentStage(above_c=1.5, level=1.0)],
)
VENTED: Final = Control(venting=VENTING, circulation=CirculationLoop(fans=["fan"], from_stage=2))
# The heater held on full by a command, so that the vents have the heat to
# fight.
HEATED: Final = Schedule.of([Command(time_s=0.0, actuator_id="heater", level=1.0)])
# How closely a switch is found by halving the minute it falls in.
SWITCH_S: Final = 1e-6
# How close the air is to an edge at a switch so found.
AT_THE_EDGE_C: Final = 1e-4


def _day(
    control: Control | None = VENTED,
    schedule: Schedule = HEATED,
    thermostat: Thermostat | None = None,
) -> ClimateDay:
    config = BOX.model_copy(update={"weather": MILD})
    return ClimateDay(
        ClimateRun(
            base=config.airflow,
            equipment=config.layout.equipment,
            schedule=schedule,
            settings=config.climate.run_settings(),
            grid=air_grid(config),
            solid=cfd.geometry(PACKAGED, "climate_box").solid(),
            weather=config.run_weather(),
            vents=_vents(),
            thermostat=thermostat,
            control=control,
        )
    )


def _vents() -> list[Vent]:
    """The box's doors and vents, as a run of it has them: those its venting
    loop runs opened for their cells, each standing shut at the start."""
    opened = SceneChanges(openings=dict.fromkeys(VENTING.vents, 1.0))
    start = {opening.opening_id: opening for opening in BOX.envelope.openings}
    return [
        replace(vent, opening=start[vent.opening_id])
        for vent in climate_vents(
            changed(PACKAGED, BOX, opened), cfd.geometry(PACKAGED, "climate_box", opened)
        )
    ]


def _switches(house: WholeHouse, device: str, until_s: float) -> list[tuple[float, float]]:
    """Each moment up to `until_s` the house switches `device`, found to
    `SWITCH_S` by halving the minute it falls in, with its level from then."""
    level: Callable[[float], float] = lambda t: house.controlled_at(t)[device]  # noqa: E731
    switches = []
    before = level(0.0)
    for minute in range(1, int(until_s // 60) + 1):
        now = level(minute * 60.0)
        if now == before:
            continue
        low, high = (minute - 1) * 60.0, minute * 60.0
        while high - low > SWITCH_S:
            middle = (low + high) / 2
            if level(middle) == before:
                low = middle
            else:
                high = middle
        switches.append((high, now))
        before = now
    return switches


@pytest.mark.parametrize(
    ("temperature_c", "stage", "then"),
    [
        (18.9, 0, 0),
        (19.1, 0, 1),
        (20.6, 0, 2),
        (18.5, 1, 1),
        (17.9, 1, 0),
        (19.6, 2, 2),
        (19.4, 2, 1),
        (17.0, 2, 0),
    ],
)
def test_a_stage_opens_above_its_edge_and_closes_below_it_by_the_band(
    temperature_c: float, stage: int, then: int
) -> None:
    assert VENTING.stage_at(temperature_c, stage, 19.0) == then


def test_each_stage_switches_the_moment_the_air_reaches_its_edge() -> None:
    house = _day().house

    switches = _switches(house, "roof_vent", 6 * HOUR_S)

    # Opened and closed, stage by stage, more than once.
    assert len(switches) >= 4
    assert {level for _, level in switches} == {0.2, 1.0}
    edges = {(0.0, 0.2): 19.0, (0.2, 1.0): 20.5, (1.0, 0.2): 19.5, (0.2, 0.0): 18.0}
    before = 0.0
    for moment, level in switches:
        air = house.air_at(moment)
        assert air.temperature_c == pytest.approx(edges[(before, level)], abs=AT_THE_EDGE_C)
        before = level


def test_time_moves_on_between_two_switches_of_the_vents() -> None:
    moments = [moment for moment, _ in _switches(_day().house, "roof_vent", 6 * HOUR_S)]

    assert all(later - earlier > 1.0 for earlier, later in pairwise(moments))


def test_the_fans_run_with_the_vents_from_their_stage() -> None:
    house = _day().house

    for minute in range(0, 6 * 60, 7):
        levels = house.controlled_at(minute * 60.0)
        assert levels["fan"] == (ON if levels["roof_vent"] >= 1.0 else OFF)


def test_a_command_takes_a_vent_out_of_the_loops_hands_and_the_fans_follow_its_level() -> None:
    held = Schedule.of([*HEATED.commands, Command(time_s=0.0, actuator_id="roof_vent", level=1.0)])
    day = _day(schedule=held)

    for minute in range(0, 3 * 60, 11):
        levels = day.house.controlled_at(minute * 60.0)
        assert "roof_vent" not in levels
        # Held wide open, the roof vent alone runs the fans.
        assert levels["fan"] == ON
        assert day.run.opening_levels_at(minute * 60.0)["roof_vent"] == 1.0


def test_the_grid_follows_what_the_house_decides() -> None:
    day = _day()

    for minute in range(0, 6 * 60, 13):
        time_s = minute * 60.0
        decided = day.house.controlled_at(time_s)
        assert day.run.opening_levels_at(time_s)["roof_vent"] == decided["roof_vent"]
        assert day.run.opening_levels_at(time_s)["side_vent"] == decided["side_vent"]
        assert day.run.levels_at(time_s)["fan"] == decided["fan"]


def test_a_heating_loop_alone_is_the_thermostat_it_was_to_the_last_digit() -> None:
    heating = HeatingLoop(actuator_id="heater", day_c=16.0, night_c=16.0)
    as_control = _day(control=Control(heating=heating), schedule=Schedule()).house
    thermostat = Control(heating=heating).thermostat()
    as_thermostat = _day(control=None, schedule=Schedule(), thermostat=thermostat).house

    for minute in range(0, 6 * 60, 17):
        assert as_control.air_at(minute * 60.0) == as_thermostat.air_at(minute * 60.0)


def test_a_checkpoint_keeps_how_its_vents_stood_and_refuses_a_stage_its_run_lacks(
    simulator: Simulator,
) -> None:
    saved = checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)
    kept = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
    # The reference greenhouse's controller runs its heater alone.
    vented = kept | {"house": kept["house"] | {"vent_stage": 1}}
    earlier = kept | {
        "checkpoint_format": 8,
        "house": {key: value for key, value in kept["house"].items() if key != "vent_stage"},
    }

    assert kept["house"]["vent_stage"] == 0
    assert checkpoints.read_checkpoint(earlier).house.vent_stage == 0
    with pytest.raises(InvalidRequest, match="vents stand open at stage 1, and its run's have 0"):
        checkpoints.upload_checkpoint(simulator, vented)
