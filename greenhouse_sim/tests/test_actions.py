from datetime import UTC, datetime

import pytest
from greenhouse_protocol.action import (
    HarvestPlantAction,
    LowerPlantAction,
    ScheduleInspectionAction,
    WaterPlantAction,
)
from greenhouse_protocol.enums import EventType

from greenhouse_sim.actions import apply_action
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import FruitStatus, GreenhouseWorld
from greenhouse_sim.world_builder import advance_world, initialize_world

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_ID = "gh_001_plant_001"
TIMESTAMP = datetime(2026, 1, 9, tzinfo=UTC)


def _grown_world(days: int = 60) -> GreenhouseWorld:
    world = initialize_world(CONFIG, [PLANT_ID])
    for day in range(1, days + 1):
        world = advance_world(world, CONFIG, day)
    return world


def test_water_action_increases_the_reservoir_and_records_an_event() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])
    plant_before = world.plant(PLANT_ID)

    updated_world, event = apply_action(
        world,
        WaterPlantAction(plant_id=PLANT_ID, amount_ml=200),
        CONFIG,
        day=1,
        timestamp=TIMESTAMP,
    )

    assert updated_world.plant(PLANT_ID).water_reservoir_ml == plant_before.water_reservoir_ml + 200
    assert event.event_type == EventType.WATERING
    assert event.parameters["amount_ml"] == 200


def test_water_action_does_not_exceed_capacity() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])

    updated_world, _ = apply_action(
        world,
        WaterPlantAction(plant_id=PLANT_ID, amount_ml=CONFIG.water_capacity_ml * 2),
        CONFIG,
        day=1,
        timestamp=TIMESTAMP,
    )

    assert updated_world.plant(PLANT_ID).water_reservoir_ml == CONFIG.water_capacity_ml


def test_harvest_action_removes_ripe_fruit_and_tracks_cumulative_mass() -> None:
    world = _grown_world()
    plant = world.plant(PLANT_ID)
    ripe_before = [f for t in plant.trusses for f in t.fruits if f.status == FruitStatus.RIPE]
    assert ripe_before, "test fixture needs at least one ripe fruit"
    expected_mass = sum(f.mass_g for f in ripe_before)

    updated_world, event = apply_action(
        world, HarvestPlantAction(plant_id=PLANT_ID), CONFIG, day=61, timestamp=TIMESTAMP
    )

    updated_plant = updated_world.plant(PLANT_ID)
    assert updated_plant.cumulative_harvest_g == pytest.approx(expected_mass)
    remaining_ripe = [
        f for t in updated_plant.trusses for f in t.fruits if f.status == FruitStatus.RIPE
    ]
    assert remaining_ripe == []
    assert event.event_type == EventType.HARVEST
    assert event.parameters["harvested_mass_g"] == pytest.approx(expected_mass)


def test_lower_action_increases_lowered_length() -> None:
    world = _grown_world()
    plant = world.plant(PLANT_ID)

    updated_world, event = apply_action(
        world,
        LowerPlantAction(plant_id=PLANT_ID, amount_cm=10),
        CONFIG,
        day=61,
        timestamp=TIMESTAMP,
    )

    assert updated_world.plant(PLANT_ID).lowered_length_cm == plant.lowered_length_cm + 10
    assert event.event_type == EventType.LOWERING


def test_schedule_inspection_records_an_event_without_mutating_the_world() -> None:
    world = initialize_world(CONFIG, [PLANT_ID])

    updated_world, event = apply_action(
        world,
        ScheduleInspectionAction(plant_id=PLANT_ID, reason="inconsistent moisture reading"),
        CONFIG,
        day=1,
        timestamp=TIMESTAMP,
    )

    assert updated_world == world
    assert event.event_type == EventType.MANUAL_INSPECTION
    assert event.parameters["reason"] == "inconsistent moisture reading"
