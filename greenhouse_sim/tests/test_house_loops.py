"""Every loop decided by the house's air (P11.2): the vents opened stage by
stage the moment the air passes each stage's edge and closed the moment it
falls back below it by the band; the fans run with the vents; a command
taking a vent out of the loop's hands; the grid following what the house
decides; a heating loop alone giving the run it gave as a thermostat; and a
checkpoint keeping how its vents stood."""

import re
from collections.abc import Callable
from dataclasses import replace
from itertools import pairwise
from typing import Final

import pytest

from greenhouse_sim.climate.commands import Command, Schedule
from greenhouse_sim.climate.control import (
    CirculationLoop,
    Control,
    DehumidifyingLoop,
    HeatingLoop,
    VentingLoop,
    VentStage,
)
from greenhouse_sim.climate.day import ClimateDay
from greenhouse_sim.climate.house import HouseAir, WholeHouse
from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.thermostat import OFF, ON, Thermostat
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.services import cfd, checkpoints
from greenhouse_sim.services.climate_runs import (
    checked_targets,
    climate_run,
    climate_vents,
    everything_off,
)
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
# Damp air outside, and dry: the box's dehumidifier fights the first, and
# its vents can let the second in.
DAMP: Final = ConstantWeather(air_temperature_c=12.0, relative_humidity_pct=95.0)
DRY: Final = ConstantWeather(air_temperature_c=12.0, relative_humidity_pct=50.0)
# Heated full on, the box's air warms; the heater held on full by a command,
# so that the vents have the heat to fight.
HEATED: Final = Schedule.of([Command(time_s=0.0, actuator_id="heater", level=1.0)])
# How closely a switch is found by halving the minute it falls in.
SWITCH_S: Final = 1e-6
# How close the air is to an edge at a switch so found.
AT_THE_EDGE_C: Final = 1e-4


def _day(
    control: Control | None = VENTED,
    schedule: Schedule = HEATED,
    thermostat: Thermostat | None = None,
    weather: ConstantWeather = MILD,
) -> ClimateDay:
    config = BOX.model_copy(update={"weather": weather})
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


@pytest.mark.parametrize(
    ("humidity_pct", "on", "then"),
    [(87.6, False, True), (87.4, False, False), (82.6, True, True), (82.4, True, False)],
)
def test_the_dehumidifier_runs_above_its_band_and_stops_below_it(
    humidity_pct: float, on: bool, then: bool
) -> None:
    drying = DehumidifyingLoop(actuator_id="dehumidifier", target_pct=85.0, band_pct=5.0)

    assert drying.on_at(humidity_pct, on) is then


def test_the_dehumidifier_switches_the_moment_the_air_reaches_its_humidity_edge() -> None:
    drying = DehumidifyingLoop(
        actuator_id="dehumidifier", target_pct=85.0, band_pct=5.0, vents_when_drier=False
    )
    house = _day(Control(dehumidifying=drying), Schedule(), weather=DAMP).house

    switches = _switches(house, "dehumidifier", 4 * HOUR_S)

    # On and off, more than once, each where the air's relative humidity
    # meets the edge it crossed.
    assert len(switches) >= 3
    for moment, level in switches:
        edge = 87.5 if level == ON else 82.5
        assert house.air_at(moment).relative_humidity_pct() == pytest.approx(edge, abs=1e-3)
    assert all(later - earlier > 1.0 for (earlier, _), (later, _) in pairwise(switches))


def _drying(
    weather: ConstantWeather,
    heating_c: float | None,
    schedule: Schedule | None = None,
    drying: DehumidifyingLoop | None = None,
) -> ClimateDay:
    """The box drying its air to 40 % under `weather`, venting for its
    heat only above 33 °C, and heating to `heating_c`, if given: so dry a
    target that its dehumidifier still runs once the heater has warmed the
    air."""
    venting = VENTING.model_copy(update={"day_c": 33.0, "night_c": 33.0})
    heating = (
        None
        if heating_c is None
        else HeatingLoop(actuator_id="heater", day_c=heating_c, night_c=heating_c)
    )
    control = Control(
        heating=heating,
        venting=venting,
        dehumidifying=drying or DehumidifyingLoop(actuator_id="dehumidifier", target_pct=40.0),
    )
    return _day(control, schedule or Schedule(), weather=weather)


def test_it_vents_for_the_airs_water_while_the_heater_is_off_and_the_air_outside_is_drier() -> None:
    crack = VENTING.stages[0].level
    at_s = 10 * 60.0

    drying = _drying(DRY, heating_c=None).house
    heating = _drying(DRY, heating_c=25.0).house
    wetter_outside = _drying(
        ConstantWeather(air_temperature_c=18.0, relative_humidity_pct=95.0), heating_c=None
    ).house

    # Its air starts at 75 %, above the band: the dehumidifier runs.
    assert drying.controlled_at(at_s)["dehumidifier"] == ON
    assert drying.air_at(at_s).vent_stage == 0
    assert drying.controlled_at(at_s)["roof_vent"] == crack
    # Heating, or under wetter air, it keeps the vents shut, its dehumidifier
    # running all the same.
    heated = heating.air_at(at_s)
    assert heated.heating and heated.dehumidifying and heated.drier
    assert heating.controlled_at(at_s)["roof_vent"] == 0.0
    assert not wetter_outside.air_at(at_s).drier
    assert wetter_outside.controlled_at(at_s)["roof_vent"] == 0.0


def test_a_checkpoint_whose_air_runs_a_dehumidifier_its_run_lacks_is_refused(
    simulator: Simulator,
) -> None:
    saved = checkpoints.save_checkpoint(simulator, RunRequest("reference_greenhouse"), time_s=DAY_S)
    kept = checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")
    drying = kept | {"house": kept["house"] | {"dehumidifying": True}}

    assert kept["house"]["dehumidifying"] is False
    with pytest.raises(InvalidRequest, match="runs a dehumidifying loop, and its run has none"):
        checkpoints.upload_checkpoint(simulator, drying)


def test_the_all_off_run_neither_vents_nor_runs_its_fans() -> None:
    warm = BOX.model_copy(
        update={"weather": ConstantWeather(air_temperature_c=25.0), "control": VENTED}
    )
    with Simulator(Catalogue(PACKAGED.with_config(warm))) as simulator:
        key, vented = climate_run(simulator, RunRequest("climate_box"))
        off = everything_off(simulator, key)

        # Its own run vents the warm air; with everything off, nothing does.
        assert vented.house.controlled_at(HOUR_S)["roof_vent"] > 0
        for minute in range(0, 3 * 60, 10):
            time_s = minute * 60.0
            assert off.house.controlled_at(time_s) == {}
            assert off.run.opening_levels_at(time_s)["roof_vent"] == 0.0
            assert off.run.levels_at(time_s)["fan"] == 0.0


def test_a_heating_target_that_would_heat_while_the_vents_open_is_refused() -> None:
    # By day the vents' first stage closes at 21 °C (22 + 0 - 1): the heater
    # switches off 1 °C below it at the most, at a setpoint of 19.5 °C.
    control = Control(
        heating=HeatingLoop(actuator_id="heater", day_c=18.0, night_c=16.0),
        venting=VENTING.model_copy(update={"day_c": 22.0, "night_c": 20.0}),
    )
    config = BOX.model_copy(update={"control": control})

    assert checked_targets(config, [(HOUR_S, "heating_day", 19.5)]) == (
        (HOUR_S, "heating_day", 19.5),
    )
    with pytest.raises(
        InvalidRequest,
        match=re.escape(
            "by day of 26 °C leaves less than the dead band of 1 °C below where the vents' "
            "first stage closes, 21 °C: at most 19.5 °C"
        ),
    ):
        checked_targets(config, [(HOUR_S, "heating_day", 26.0)])


def test_an_edge_the_air_stands_at_is_crossed_only_moving_through_it() -> None:
    # The vents' first stage opens above 18 °C, where the air starts, as it
    # cools: they stay shut.
    opening = VENTING.model_copy(update={"day_c": 18.0, "night_c": 18.0})
    cooling = _day(Control(venting=opening), Schedule(), weather=ConstantWeather()).house
    assert cooling.controlled_at(60.0)["roof_vent"] == 0.0

    # The heater switches off above 16.5 °C; on there, in a frost it cannot
    # hold the air against, it stays on.
    heating = HeatingLoop(actuator_id="heater", day_c=16.0, night_c=16.0)
    frost = ConstantWeather(air_temperature_c=-10.0)
    house = _day(Control(heating=heating), Schedule(), weather=frost).house
    start = house.air_at(0.0)
    house.seed(600.0, HouseAir(16.5, start.humidity_g_kg, start.co2_ppm, heating=True))
    assert house.air_at(630.0).heating

    # The first stage closes below 18 °C; open there, the heater warming the
    # air, it stays open.
    vented = _day().house
    start = vented.air_at(0.0)
    vented.seed(600.0, HouseAir(18.0, start.humidity_g_kg, start.co2_ppm, vent_stage=1))
    assert vented.air_at(630.0).vent_stage == 1


def test_the_air_outside_counts_drier_only_once_the_house_is_wetter_beyond_the_margin() -> None:
    # The house's air exactly at the margin above the outside's, 1 g/kg, and
    # drying: the outside does not count as drier.
    outside_g_kg = float(humidity_ratio_g_kg(12.0, 50.0))
    at_the_margin = outside_g_kg + 1.0
    house = _drying(DRY, heating_c=None).house
    start = house.air_at(0.0)
    house.seed(
        600.0,
        HouseAir(15.0, at_the_margin, start.co2_ppm, dehumidifying=True, vent_stage=0),
    )

    assert at_the_margin - outside_g_kg == 1.0
    assert not house.air_at(630.0).drier


def test_a_dehumidifier_a_command_takes_over_cracks_the_vents_no_more() -> None:
    switched_off = Schedule.of([Command(time_s=300.0, actuator_id="dehumidifier", level=0.0)])
    house = _drying(DRY, heating_c=None, schedule=switched_off).house

    assert house.controlled_at(200.0)["roof_vent"] == VENTING.stages[0].level
    assert "dehumidifier" not in house.controlled_at(600.0)
    assert house.controlled_at(600.0)["roof_vent"] == 0.0


def test_the_outside_stops_counting_drier_where_the_water_the_air_holds_reaches_its_edge() -> None:
    # Warm air near saturation in a box under cold damp air: as it cools,
    # its water condenses, and the outside soon counts as no drier, 1.5 g/kg
    # below the house's (a margin of 2 less a band of 0.5).
    damp = ConstantWeather(air_temperature_c=5.0, relative_humidity_pct=95.0)
    drying = DehumidifyingLoop(
        actuator_id="dehumidifier", target_pct=40.0, drier_by_g_kg=2.0, drier_band_g_kg=0.5
    )
    house = _drying(damp, heating_c=None, drying=drying).house
    start = house.air_at(0.0)
    warm = float(humidity_ratio_g_kg(20.0, 99.0))
    house.seed(600.0, HouseAir(20.0, warm, start.co2_ppm, dehumidifying=True, drier=True))
    outside_g_kg = float(humidity_ratio_g_kg(5.0, 95.0))

    def drier(time_s: float) -> bool:
        return house.air_at(time_s).drier

    minute = next(m for m in range(11, 60) if not drier(m * 60.0))
    low, high = (minute - 1) * 60.0, minute * 60.0
    while high - low > SWITCH_S:
        middle = (low + high) / 2
        low, high = (middle, high) if drier(middle) else (low, middle)

    switched = house.air_at(high)
    assert switched.condensed_kg > 0
    assert switched.humidity_g_kg - outside_g_kg == pytest.approx(1.5, abs=1e-3)
