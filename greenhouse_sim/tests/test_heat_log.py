"""The heat a run's heaters give its house each day, as a record a consumer
reads (P10.3): one increment at the day's end, in MJ per square metre of
floor, modelled by the simulation and said to be, the same run's as the
viewer's; a cold spell's far above a summer day's."""

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


def _day(scenario_id: str, day: int) -> list[Observation]:
    _, run_id = air_through_a_run(scenario_id)
    return heat_records(scenario_id, day, run_start(scenario_id), run_id)


def test_a_days_heat_is_one_increment_at_its_end_from_the_runs_house() -> None:
    _, run_id = air_through_a_run(SCENARIO)
    house = climate_run(SCENARIO)[1].house

    [record] = _day(SCENARIO, 1)

    assert record.observation_type == ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2
    assert record.timestamp == run_start(SCENARIO) + timedelta(seconds=2 * DAY_S)
    assert record.value == round(house.heated_j(DAY_S, 2 * DAY_S) / 1e6 / FLOOR_M2, 3)
    # March: the heater runs half the day or more, never more than all of
    # it at its 30 kW.
    assert 30_000 * DAY_S / 2 / 1e6 / FLOOR_M2 < record.value <= 30_000 * DAY_S / 1e6 / FLOOR_M2
    # Modelled, by the run the viewer draws; no instrument took it.
    assert (record.source.type, record.source.source_id) == (SourceType.SIMULATION, run_id)
    assert (record.sensor_id, record.plant_id) == (None, None)
    assert check_observations([record]) == []


def test_a_heater_no_one_runs_gives_no_heat_and_a_house_without_one_no_record() -> None:
    # The climate box's heater is off until commanded; the airflow box has none.
    [record] = _day("climate_box", 0)

    assert record.value == 0.0
    assert _day("airflow_box", 0) == []


@pytest.mark.slow
def test_a_cold_spell_takes_far_more_heat_than_a_june_day() -> None:
    # From the kept opening day, as the viewer and a playback carry on.
    checkpoints.load_openings()
    march = [_day(SCENARIO, day)[0].value for day in range(3)]
    june = [_day(SCENARIO, day)[0].value for day in range(110, 113)]

    assert min(march) > 4 * max(june)
    # Every day differs: the heater follows the weather, not a schedule.
    assert len(set(march + june)) == 6
