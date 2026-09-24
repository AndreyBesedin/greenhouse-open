"""Observe, decide, act, observe again.

    python examples/03_close_the_loop.py

A decision rule reads only observations and proposes semantic actions
(`greenhouse_protocol.action`). The simulator validates each request against
its own world and executes the ones it accepts, returning an event for each.
The next day's observations show the effect. The rule below is deliberately
naive; the point is the shape of the loop, not the agronomy.
"""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.action import RequestedAction, WaterPlantAction
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

SCENARIO = SCENARIO_REGISTRY["gh_002"]
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
DRY_BELOW_PCT = 40.0


def decide(observations: list[Observation]) -> list[RequestedAction]:
    """Water any plant whose soil moisture reading is below a threshold."""
    return [
        WaterPlantAction(plant_id=o.plant_id, amount_ml=500.0)
        for o in observations
        if o.observation_type == ObservationType.SOIL_MOISTURE_PCT
        and o.plant_id is not None
        and o.value < DRY_BELOW_PCT
    ]


def main() -> None:
    engine = SimulationEngine(SCENARIO)
    plant_id = f"{SCENARIO.greenhouse_id}_plant_001"
    world = engine.initialize([plant_id], greenhouse_id=SCENARIO.greenhouse_id)

    for day in range(1, 21):
        timestamp = START + timedelta(days=day - 1)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id="example")
        moisture = next(
            o.value
            for o in step.observations
            if o.observation_type == ObservationType.SOIL_MOISTURE_PCT
        )
        actions = decide(step.observations)
        execution = engine.apply_actions(step.world, actions, day=day, timestamp=timestamp)
        world = execution.world
        done = ", ".join(e.event_type.value for e in execution.events) or "-"
        print(f"day {day:2}: soil moisture {moisture:5.1f}%  actions: {done}")


if __name__ == "__main__":
    main()
