"""Pins the behaviour of a whole simulated run.

The run below drives `SimulationEngine` the way any caller would: create a
world, advance it, apply actions and collect observations, with no
database, server or UI. The pinned numbers let a refactor of the simulator
prove it is behaviour-preserving rather than merely type-checking.

The run observes each day and then acts, which is the order a management
loop uses: it generates a day's observations, asks a policy, and executes
only after review. So the watered plant's soil-moisture reading on the
three watering days reports the moisture a policy would have seen when it
decided, not the moisture after the watering it asked for.

The pinned numbers are a snapshot of current behaviour, not a specification.
If a deliberate change to the dynamics moves them, update them in the same
commit and say so in the message.
"""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.action import RequestedAction, WaterPlantAction
from greenhouse_protocol.enums import EventType
from greenhouse_protocol.observation import Observation

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world import FruitStatus, GreenhouseWorld

CONFIG = SCENARIO_REGISTRY["gh_001"]
PLANT_IDS = ["gh_001_plant_001", "gh_001_plant_002"]
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
DAYS = 30
# Water the first plant on these days, so the action/event path is exercised
# by the characterization too rather than only growth and ripening.
WATERING_DAYS = frozenset({5, 12, 21})


def _run() -> tuple[GreenhouseWorld, list[Observation], list[tuple[int, EventType]]]:
    """One complete run through the simulator's own API and no database."""
    engine = SimulationEngine(CONFIG)
    world = engine.initialize(PLANT_IDS, greenhouse_id=CONFIG.greenhouse_id)
    observations: list[Observation] = []
    events: list[tuple[int, EventType]] = []

    for day in range(1, DAYS + 1):
        timestamp = START + timedelta(days=day - 1)
        step = engine.advance(
            world, day=day, timestamp=timestamp, simulation_id="sim_characterization"
        )
        world = step.world

        if day in WATERING_DAYS:
            action: RequestedAction = WaterPlantAction(plant_id=PLANT_IDS[0], amount_ml=700.0)
            execution = engine.apply_actions(world, [action], day=day, timestamp=timestamp)
            assert all(result.accepted for result in execution.results)
            world = execution.world
            events.extend((day, event.event_type) for event in execution.events)

        observations.extend(step.observations)

    return world, observations, events


def test_a_seeded_run_needs_no_database_and_is_reproducible() -> None:
    """Create a world, advance it, apply actions and collect observations
    with no database, server or UI - twice, with identical results.
    """
    first_world, first_observations, first_events = _run()
    second_world, second_observations, second_events = _run()

    assert first_world == second_world
    assert first_observations == second_observations
    assert first_events == second_events


def test_the_run_produces_the_recorded_shape() -> None:
    world, observations, events = _run()

    assert world.simulated_day == DAYS
    assert [plant.plant_id for plant in world.plants] == PLANT_IDS
    assert events == [(day, EventType.WATERING) for day in sorted(WATERING_DAYS)]
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
    world, _, _ = _run()
    watered, unwatered = world.plants

    # The watered plant ends taller: three irrigations are visible in the
    # hidden state even though no policy is attached to this run.
    assert [round(plant.stem_length_cm, 2) for plant in world.plants] == [58.25, 54.82]
    assert [len(plant.trusses) for plant in world.plants] == [5, 5]
    assert watered.stem_length_cm > unwatered.stem_length_cm
    # Three manual waterings over thirty days do not keep either plant out
    # of full water stress - the deterministic policy, absent here, is what
    # normally prevents that.
    assert [round(plant.water_reservoir_ml, 3) for plant in world.plants] == [0.0, 0.0]
    assert [round(plant.water_stress, 3) for plant in world.plants] == [1.0, 1.0]
    assert _fruit_counts(world) == {FruitStatus.RIPE: 12, FruitStatus.GROWING: 34}


def _fruit_counts(world: GreenhouseWorld) -> dict[FruitStatus, int]:
    counts: dict[FruitStatus, int] = {}
    for plant in world.plants:
        for truss in plant.trusses:
            for fruit in truss.fruits:
                counts[fruit.status] = counts.get(fruit.status, 0) + 1
    return counts
