"""A thermostat on a heater (P10.3): on below its setpoint by half its band,
off above it by as much, a setpoint by day and one by night; switched the
moment the house's air reaches its band's edge, which the grid run follows;
the heat it gives counted as it runs; a command to its heater taking it
over; and the same switching for the same run, however it is worked out."""

from itertools import pairwise
from typing import Final

import pytest
from pydantic import ValidationError

from greenhouse_sim.climate.commands import Command, DailyCommand, Schedule
from greenhouse_sim.climate.day import ClimateDay
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.thermostat import OFF, ON, Thermostat
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services import cfd
from greenhouse_sim.services.climate_readings import equipment_at, house_air
from greenhouse_sim.services.climate_runs import climate_run, off_levels
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.run_state import run_state
from greenhouse_sim.services.runs import RunPlan, RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.equipment import Heater

BOX: Final = SCENARIO_REGISTRY["climate_box"]
HOUR_S: Final = 3600.0
# Day and night alike, so that only the weather tells two runs apart.
AT_16: Final = Thermostat(actuator_id="heater", day_c=16.0, night_c=16.0)
COLD: Final = ConstantWeather(air_temperature_c=0.0)
MILD: Final = ConstantWeather(air_temperature_c=12.0)
POWER_W: Final = next(p.power_w for p in BOX.layout.equipment if isinstance(p, Heater))
# Its glass passing nothing, and its gaps leaking nothing.
SEALED: Final = {
    "glazing_u_w_m2k": 0.0,
    "infiltration_per_h": 0.0,
    "infiltration_per_h_per_m_s": 0.0,
}


def _day(
    weather: ConstantWeather = MILD,
    thermostat: Thermostat | None = AT_16,
    schedule: Schedule | None = None,
    sealed: bool = False,
) -> ClimateDay:
    config = BOX.model_copy(update={"weather": weather})
    return ClimateDay(
        ClimateRun(
            base=config.airflow,
            equipment=config.layout.equipment,
            schedule=schedule or Schedule(),
            settings=config.climate.model_copy(update=SEALED if sealed else {}),
            grid=air_grid(config),
            solid=cfd.geometry(PACKAGED, "climate_box").solid(),
            weather=config.run_weather(),
            thermostat=thermostat,
        )
    )


def _levels(house: WholeHouse, until_s: float) -> list[float]:
    """Its heater's level at the start of each minute up to `until_s`."""
    return [house.heater_level_at(m * 60.0) for m in range(int(until_s // 60))]


@pytest.mark.parametrize(
    ("temperature_c", "heating", "heats"),
    [
        (15.4, False, True),
        (15.6, False, False),
        (15.6, True, True),
        (16.4, True, True),
        (16.6, True, False),
        (16.4, False, False),
    ],
)
def test_it_switches_on_below_its_band_and_off_above_it_and_holds_between(
    temperature_c: float, heating: bool, heats: bool
) -> None:
    assert AT_16.heats(temperature_c, heating, 0.0) is heats


def test_its_setpoint_is_the_days_from_its_morning_and_the_nights_from_its_evening() -> None:
    thermostat = Thermostat(actuator_id="heater", day_c=18.0, night_c=16.0)

    assert [thermostat.setpoint_c(h * HOUR_S) for h in (0, 6.99, 7, 12, 18.99, 19, 23)] == [
        16.0,
        16.0,
        18.0,
        18.0,
        18.0,
        16.0,
        16.0,
    ]
    # Every day of a run alike.
    assert thermostat.setpoint_c(40 * 24 * HOUR_S + 12 * HOUR_S) == 18.0


def test_a_thermostat_whose_day_starts_after_its_night_or_off_the_minute_is_refused() -> None:
    with pytest.raises(ValidationError, match="day starts before its night"):
        Thermostat(actuator_id="heater", day_c=18.0, night_c=16.0, day_from_s=20 * HOUR_S)
    with pytest.raises(ValidationError, match="start on the minute"):
        Thermostat(actuator_id="heater", day_c=18.0, night_c=16.0, day_from_s=7 * HOUR_S + 30)


def test_in_the_cold_its_heater_runs_longer_than_in_mild_weather() -> None:
    cold, mild = _day(COLD).house, _day(MILD).house

    cold_j, mild_j = cold.heated_j(0.0, 6 * HOUR_S), mild.heated_j(0.0, 6 * HOUR_S)

    assert cold_j > 1.5 * mild_j > 0
    # In mild weather it switches on and off, more than once.
    levels = _levels(mild, 6 * HOUR_S)
    switches = sum(1 for a, b in pairwise(levels) if a != b)
    assert switches >= 4


def test_when_its_heater_can_it_holds_the_air_within_its_band() -> None:
    house = _day(MILD).house
    temperatures = [house.air_at(m * 60.0).temperature_c for m in range(360)]

    # Switched as the air reaches an edge, never past it.
    assert min(temperatures) == pytest.approx(15.5, abs=0.05)
    assert max(temperatures) == pytest.approx(16.5, abs=0.05)
    assert all(15.5 - 1e-9 <= t <= 16.5 + 1e-9 for t in temperatures)


def test_it_switches_its_heater_off_the_moment_the_air_reaches_the_top_of_its_band() -> None:
    # Shut off from the outside, the box keeps what it is given: from its
    # start at 16 °C, heated to 20 °C, it stops at the band's top.
    house = _day(
        thermostat=AT_16.model_copy(update={"day_c": 20.0, "night_c": 20.0}), sealed=True
    ).house
    start, later = house.air_at(0.0), house.air_at(HOUR_S)

    assert later.temperature_c == pytest.approx(20.5, abs=1e-9)
    assert house.heater_level_at(HOUR_S) == OFF
    assert house.heater_level_at(0.0) == ON
    # All the heat it gave is in the air: the heater's power for as long as
    # it took to warm it.
    assert later.heated_j == pytest.approx(house.heat_j(later) - house.heat_j(start), rel=1e-9)
    # Counted to the second, the heat is a second's at most from it.
    assert later.heated_j == pytest.approx(POWER_W * _on_until_s(house, HOUR_S), abs=POWER_W)


def test_the_grid_run_follows_the_houses_decisions() -> None:
    day = _day(MILD)

    for moment in (30.0, 600.0, 1830.0, 2 * HOUR_S + 45.0, 4 * HOUR_S):
        decided = day.house.heater_level_at(moment)
        assert day.run.levels_at(moment)["heater"] == decided
        assert day.window(moment).levels_at(moment)["heater"] == decided
    assert {day.house.heater_level_at(m * 60.0) for m in range(240)} == {ON, OFF}


def _on_until_s(house: WholeHouse, until_s: float) -> float:
    """How long its heater runs from the start to `until_s`, a second at a
    time."""
    return sum(house.heater_level_at(second + 0.5) for second in range(int(until_s)))


def test_the_heat_it_counts_is_the_heaters_power_for_as_long_as_it_runs() -> None:
    house = _day(MILD).house

    assert house.heated_j(0.0, HOUR_S) == pytest.approx(
        POWER_W * _on_until_s(house, HOUR_S), rel=1e-2
    )
    assert house.air_at(0.0).heated_j == 0.0


def test_a_command_to_its_heater_takes_it_over_from_that_moment() -> None:
    schedule = Schedule(commands=(Command(time_s=HOUR_S, actuator_id="heater", level=0.0),))
    day = _day(COLD, schedule=schedule)

    assert day.run.levels_at(HOUR_S - 60.0)["heater"] == ON
    assert day.run.levels_at(HOUR_S)["heater"] == OFF
    assert day.house.heated_j(HOUR_S, 3 * HOUR_S) == 0.0
    # Before then, it ran from the moment the air fell below its band.
    assert day.house.heated_j(0.0, HOUR_S) == pytest.approx(
        POWER_W * _on_until_s(day.house, HOUR_S), rel=1e-2
    )
    assert day.house.heated_j(0.0, HOUR_S) > POWER_W * (HOUR_S - 600.0)


def test_without_a_thermostat_its_heater_is_where_the_commands_put_it() -> None:
    day = _day(COLD, thermostat=None)

    assert day.run.levels_at(HOUR_S)["heater"] == 0.0
    assert day.house.heated_j(0.0, HOUR_S) == 0.0
    with pytest.raises(ValueError, match="without a thermostat"):
        day.house.heater_level_at(0.0)


def test_the_same_run_decides_the_same_however_it_is_worked_out() -> None:
    whole = _day(MILD).house
    levels = _levels(whole, 4 * HOUR_S)
    # Another house of the same run, carrying on from the air the first kept
    # at two hours, as one restored from a checkpoint does.
    later = _day(MILD).house
    later.seed(2 * HOUR_S, whole.air_at(2 * HOUR_S))

    assert _levels(_day(MILD).house, 4 * HOUR_S) == levels
    assert later.air_at(4 * HOUR_S) == whole.air_at(4 * HOUR_S)
    assert [later.heater_level_at(m * 60.0) for m in range(120, 240)] == levels[120:]


def test_a_thermostat_runs_one_of_the_scenarios_heaters_and_takes_no_daily_commands() -> None:
    """A scenario's thermostat is its control's heating loop (P11.1)."""

    def config(**changes: object) -> ScenarioConfig:
        return ScenarioConfig.model_validate(BOX.model_dump() | changes)

    heating = {"actuator_id": "heater", "day_c": 16.0, "night_c": 16.0}
    assert config(control={"heating": heating}).thermostat == AT_16
    with pytest.raises(ValidationError, match="runs one of its heaters, not 'fan'"):
        config(control={"heating": heating | {"actuator_id": "fan"}})
    daily = DailyCommand(time_of_day_s=0.0, actuator_id="heater", level=1.0)
    with pytest.raises(ValidationError, match="daily commands to it would take it over"):
        config(control={"heating": heating}, daily=[daily.model_dump()])


def test_the_reference_greenhouses_run_with_everything_off_runs_no_heater(
    simulator: Simulator,
) -> None:
    _, day = climate_run(simulator, RunRequest("reference_greenhouse"))
    _, off = climate_run(
        simulator,
        RunRequest(
            "reference_greenhouse",
            levels=off_levels(PACKAGED, "reference_greenhouse"),
            plan=RunPlan.requested(daily=()),
        ),
    )

    assert off_levels(PACKAGED, "reference_greenhouse") == {"heater": 0.0}
    assert off.house.heated_j(0.0, HOUR_S) == 0.0
    assert day.house.heated_j(0.0, HOUR_S) > 0.0
    trace = house_air(simulator, RunRequest("reference_greenhouse"), until_s=HOUR_S)
    assert trace.all_off.temperature_c[-1] < trace.controlled.temperature_c[-1]


def test_the_viewer_and_qa_mode_read_its_heater_as_the_thermostat_runs_it(
    simulator: Simulator,
) -> None:
    _, day = climate_run(simulator, RunRequest("reference_greenhouse"))

    state = run_state(simulator, RunRequest("reference_greenhouse"), until_s=HOUR_S)
    equipment = equipment_at(simulator, RunRequest("reference_greenhouse"), time_s=HOUR_S)

    assert state.levels["heater"] == day.house.heater_level_at(HOUR_S)
    assert equipment.levels == day.run.levels_at(HOUR_S)
    assert equipment.thermostat is not None
    assert (equipment.thermostat.setpoint_c, equipment.thermostat.runs) == (16.0, True)
    # A command to the heater takes it over, and the viewer is told.
    commanded = equipment_at(
        simulator,
        RunRequest(
            "reference_greenhouse", plan=RunPlan.requested(commands=((600.0, "heater", 0.0),))
        ),
        time_s=HOUR_S,
    )
    assert commanded.levels["heater"] == 0.0
    assert commanded.thermostat is not None
    assert not commanded.thermostat.runs
    # A scenario without one says so.
    assert equipment_at(simulator, RunRequest("climate_box"), time_s=HOUR_S).thermostat is None
