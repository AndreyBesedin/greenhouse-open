"""The heat a run's heaters give its house, as records a consumer reads
(P10.3): an increment at the end of each hour, in MJ per square metre of
floor, modelled by the simulation and said to be, the same run's as the
viewer's; a cold spell's day far above a summer day's."""

from datetime import timedelta
from typing import Final

import pytest
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.fields import air_through_a_run, climate_run
from greenhouse_sim.services.heat_log import heat_records
from greenhouse_sim.services.sensors import run_start

SCENARIO: Final = "reference_greenhouse"
# Its floor, 12 m by 9.6 m.
FLOOR_M2: Final = 115.2
HOUR_S: Final = 3600.0
# Its heater's rated power, in W.
HEATER_W: Final = 30_000.0


def _day(scenario_id: str, day: int) -> list[Observation]:
    _, run_id = air_through_a_run(scenario_id)
    return heat_records(scenario_id, day, run_start(scenario_id), run_id)


def _mj_m2(joules: float) -> float:
    return joules / 1e6 / FLOOR_M2


def test_an_hours_heat_is_an_increment_at_its_end_from_the_runs_house() -> None:
    _, run_id = air_through_a_run(SCENARIO)
    house = climate_run(SCENARIO)[1].house
    start = run_start(SCENARIO)

    records = _day(SCENARIO, 1)

    assert {r.observation_type for r in records} == {ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2}
    assert [r.timestamp for r in records] == [
        start + timedelta(seconds=DAY_S + hour * HOUR_S) for hour in range(1, 25)
    ]
    fourth = house.heated_j(DAY_S + 3 * HOUR_S, DAY_S + 4 * HOUR_S)
    assert records[3].value == round(_mj_m2(fourth), 3)
    # The day's sum is its heat, each hour's kept to a kilojoule.
    day = _mj_m2(house.heated_j(DAY_S, 2 * DAY_S))
    assert sum(r.value for r in records) == pytest.approx(day, abs=24 * 0.0005)
    # March: the heater runs half the day or more, never more than all of
    # it; an hour, no more than an hour of it.
    assert _mj_m2(HEATER_W * DAY_S / 2) < day <= _mj_m2(HEATER_W * DAY_S)
    assert max(r.value for r in records) <= round(_mj_m2(HEATER_W * HOUR_S), 3)
    # Modelled, by the run the viewer draws; no instrument took it.
    assert {(r.source.type, r.source.source_id) for r in records} == {
        (SourceType.SIMULATION, run_id)
    }
    assert {(r.sensor_id, r.plant_id) for r in records} == {(None, None)}
    assert check_observations(records) == []


def test_a_heater_no_one_runs_gives_no_heat_and_a_house_without_one_no_record() -> None:
    # The climate box's heater is off until commanded; the airflow box has none.
    assert [r.value for r in _day("climate_box", 0)] == [0.0] * 24
    assert _day("airflow_box", 0) == []


@pytest.mark.slow
def test_a_cold_spell_takes_far_more_heat_than_a_june_day() -> None:
    # From the kept opening day, as the viewer and a playback carry on.
    checkpoints.load_openings()
    march = [sum(r.value for r in _day(SCENARIO, day)) for day in range(3)]
    june = [sum(r.value for r in _day(SCENARIO, day)) for day in range(110, 113)]

    assert min(march) > 4 * max(june)
    # Every day differs: the heater follows the weather, not a schedule.
    assert len({round(day, 3) for day in march + june}) == 6
