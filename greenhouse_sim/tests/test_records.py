"""Simulated records are identified the way recorded ones are."""

import re
from datetime import UTC, datetime

from greenhouse_sim.records import event_id, observation_id
from greenhouse_sim.services import sensors
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S

SCENARIO = "climate_box"
TIMESTAMP = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_identifiers_key_records_by_the_instant_they_describe() -> None:
    assert observation_id("tomato_compartment_plant_001", TIMESTAMP, "soil_moisture_pct") == (
        "sim_tomato_compartment_plant_001_20261014T120000Z_soil_moisture_pct"
    )
    assert event_id("tomato_compartment_plant_001", TIMESTAMP, "watering") == (
        "sim_tomato_compartment_plant_001_20261014T120000Z_watering"
    )


def test_two_instants_of_the_same_reading_are_different_records() -> None:
    later = TIMESTAMP.replace(hour=13)

    assert observation_id("p1", TIMESTAMP, "k") != observation_id("p1", later, "k")


def test_published_records_carry_no_simulator_day_counter(simulator: Simulator) -> None:
    """The simulator's clock is its own metadata, not canonical chronology.

    A day counter in a record's identity is that clock crossing the
    boundary - and it would collide across two runs of the same scenario
    describing different instants. Here a run's sensors through its first
    hour and its first walks through the crop.
    """
    run = RunRequest(SCENARIO)
    log = sensors.observations(simulator, run, HOUR_S, from_s=0.0)
    walked = [
        observation
        for day in (0, 1)
        for observation in crop_records(simulator, run, day, log.start, log.run_id)[0]
    ]
    day_counter = re.compile(r"_d\d+_")

    assert log.observations and walked
    for observation in [*log.observations, *walked]:
        assert not day_counter.search(observation.observation_id), observation.observation_id
        stamp = observation.timestamp.strftime("%Y%m%dT%H%M%SZ")
        assert stamp in observation.observation_id, observation.observation_id
