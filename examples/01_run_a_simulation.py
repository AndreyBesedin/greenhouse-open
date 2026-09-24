"""Run a deterministic simulation and look at what its sensors report.

    python examples/01_run_a_simulation.py

The simulator keeps a hidden world (true plant state, latent growth rates)
and publishes only noisy observations of it, as a real greenhouse's sensors
would. Everything downstream works from those observations.
"""

from collections import Counter
from datetime import UTC, datetime, timedelta

from greenhouse_protocol.observation import Observation
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

SCENARIO = SCENARIO_REGISTRY["gh_002"]  # one plant, followed for 40 days
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def run(days: int) -> list[list[Observation]]:
    """Each day's observations of a fresh run."""
    engine = SimulationEngine(SCENARIO)
    plant_id = f"{SCENARIO.greenhouse_id}_plant_001"
    world = engine.initialize([plant_id], greenhouse_id=SCENARIO.greenhouse_id)
    per_day = []
    for day in range(1, days + 1):
        step = engine.advance(
            world,
            day=day,
            timestamp=START + timedelta(days=day - 1),
            simulation_id="example",
        )
        world = step.world
        per_day.append(step.observations)
    return per_day


def main() -> None:
    per_day = run(10)
    for day, observations in enumerate(per_day, start=1):
        kinds = Counter(o.observation_type.value for o in observations)
        height = next(
            o.value for o in observations if o.observation_type.value == "visible_height_cm"
        )
        print(f"day {day:2}: {len(observations)} observations, measured height {height:.1f} cm")
    print(f"observation types: {', '.join(sorted(kinds))}")

    # Same scenario, same seed: a second run produces identical records.
    assert run(10) == per_day
    print("a second run produced identical observations")


if __name__ == "__main__":
    main()
