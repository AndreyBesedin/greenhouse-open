"""Pins the behaviour of a whole simulated run.

The run below drives `SimulationEngine` the way any caller would: create a
world, advance it and collect observations, with no database, server or
UI. The pinned numbers let a refactor of the simulator prove it is
behaviour-preserving rather than merely type-checking. A policy acts on the
run, not on the engine's day (P13.9): no action is applied here.

The pinned numbers are a snapshot of current behaviour, not a specification.
If a deliberate change to the dynamics moves them, update them in the same
commit and say so in the message.
"""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.observation import Observation

from greenhouse_sim.domain.crop import FruitStatus
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import GreenhouseWorld

CONFIG = SCENARIO_REGISTRY["tomato_compartment"]
PLANT_IDS = ["tomato_compartment_plant_001", "tomato_compartment_plant_002"]
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
DAYS = 30


def _run() -> tuple[GreenhouseWorld, list[Observation]]:
    """One complete run through the simulator's own API and no database."""
    engine = SimulationEngine(CONFIG)
    world = engine.initialize(PLANT_IDS, greenhouse_id=CONFIG.greenhouse_id)
    observations: list[Observation] = []

    for day in range(1, DAYS + 1):
        timestamp = START + timedelta(days=day - 1)
        step = engine.advance(
            world, day=day, timestamp=timestamp, simulation_id="sim_characterization"
        )
        world = step.world
        observations.extend(step.observations)

    return world, observations


def test_a_seeded_run_needs_no_database_and_is_reproducible() -> None:
    """Create a world, advance it and collect observations with no
    database, server or UI - twice, with identical results.
    """
    first_world, first_observations = _run()
    second_world, second_observations = _run()

    assert first_world == second_world
    assert first_observations == second_observations


def test_the_run_produces_the_recorded_shape() -> None:
    world, observations = _run()

    assert world.simulated_day == DAYS
    assert [plant.plant_id for plant in world.plants] == PLANT_IDS
    # One greenhouse-level air temperature reading plus a fixed set of
    # per-plant readings, every day, for the whole run.
    per_plant = _observations_per_plant(observations)
    assert len(observations) == DAYS * (1 + len(PLANT_IDS) * per_plant)
    assert all(o.source.source_id == "sim_characterization" for o in observations)


def _observations_per_plant(observations: list[Observation]) -> int:
    first_day = [o for o in observations if o.timestamp == START and o.plant_id == PLANT_IDS[0]]
    return len(first_day)


def test_the_run_reaches_the_recorded_growth_and_ripening_state() -> None:
    """Hidden-state values no consumer may see, pinned here because this is
    the simulator's own test."""
    world, _ = _run()

    assert [round(plant.stem_length_cm, 2) for plant in world.plants] == [49.18, 54.05]
    assert [len(plant.trusses) for plant in world.plants] == [5, 5]
    # Nothing waters them: both end in full water stress.
    assert [round(plant.water_reservoir_ml, 3) for plant in world.plants] == [0.0, 0.0]
    stress = [world.plant_model.plants[plant.plant_id].water_stress for plant in world.plants]
    assert [round(value, 3) for value in stress] == [1.0, 1.0]
    assert _fruit_counts(world) == {FruitStatus.RIPE: 9, FruitStatus.GROWING: 31}


def _fruit_counts(world: GreenhouseWorld) -> dict[FruitStatus, int]:
    counts: dict[FruitStatus, int] = {}
    for plant in world.plants:
        for truss in plant.trusses:
            for fruit in truss.fruits:
                counts[fruit.status] = counts.get(fruit.status, 0) + 1
    return counts
