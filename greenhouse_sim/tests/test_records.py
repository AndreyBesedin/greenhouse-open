"""Simulated records are identified the way recorded ones are."""

import re
from datetime import UTC, datetime

from greenhouse_protocol.action import WaterPlantAction

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.records import event_id, observation_id
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

CONFIG = SCENARIO_REGISTRY["gh_001"]
TIMESTAMP = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_identifiers_key_records_by_the_instant_they_describe() -> None:
    assert observation_id("gh_001_plant_001", TIMESTAMP, "soil_moisture_pct") == (
        "sim_gh_001_plant_001_20261014T120000Z_soil_moisture_pct"
    )
    assert event_id("gh_001_plant_001", TIMESTAMP, "watering") == (
        "sim_gh_001_plant_001_20261014T120000Z_watering"
    )


def test_two_instants_of_the_same_reading_are_different_records() -> None:
    later = TIMESTAMP.replace(hour=13)

    assert observation_id("p1", TIMESTAMP, "k") != observation_id("p1", later, "k")


def test_published_records_carry_no_simulator_day_counter() -> None:
    """The simulator's clock is its own metadata, not canonical chronology.

    A day counter in a record's identity is that clock crossing the
    boundary - and it would collide across two runs of the same scenario
    describing different instants.
    """
    engine = SimulationEngine(CONFIG)
    world = engine.initialize(["gh_001_plant_001"], greenhouse_id="gh_001")
    day_counter = re.compile(r"_d\d+_")

    for day in (1, 2, 3):
        timestamp = datetime(2026, 10, 12 + day, 12, 0, tzinfo=UTC)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id="sim")
        execution = engine.apply_actions(
            step.world,
            [WaterPlantAction(plant_id="gh_001_plant_001", amount_ml=100.0)],
            day=day,
            timestamp=timestamp,
        )
        world = execution.world

        for record_id in [o.observation_id for o in step.observations] + [
            e.event_id for e in execution.events
        ]:
            assert not day_counter.search(record_id), record_id
            assert timestamp.strftime("%Y%m%dT%H%M%SZ") in record_id
