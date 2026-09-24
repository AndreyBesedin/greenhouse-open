"""Score what the sensors reported against what was really true.

    python examples/04_score_against_ground_truth.py

Only a simulation knows the truth behind its observations. Ground truth
leaves the simulator through a separate, evaluation-only interface
(`greenhouse_sim.ground_truth`), never as an observation, so decision logic
cannot accidentally use it. Here it measures how noisy the sensing is: the
baseline any state reconstruction has to beat.
"""

from datetime import UTC, datetime, timedelta

from greenhouse_protocol.observation import Observation
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import GroundTruth, ground_truth
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

SCENARIO = SCENARIO_REGISTRY["gh_001"]
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def main() -> None:
    engine = SimulationEngine(SCENARIO)
    plant_ids = [f"{SCENARIO.greenhouse_id}_plant_{i:03d}" for i in range(1, 11)]
    world = engine.initialize(plant_ids, greenhouse_id=SCENARIO.greenhouse_id)

    observations: list[Observation] = []
    truth: list[GroundTruth] = []
    for day in range(1, 31):
        timestamp = START + timedelta(days=day - 1)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id="example")
        world = step.world
        observations.extend(step.observations)
        truth.append(
            ground_truth(world, timestamp=timestamp, water_capacity_ml=SCENARIO.water_capacity_ml)
        )

    # Nobody waters in this run, so soil moisture falls towards zero and its
    # error is large relative to what little water is left.
    report = observation_accuracy(observations, truth)
    print(f"scored {report.readings} readings from {len(plant_ids)} plants over 30 days")
    for entry in report.by_type:
        print(
            f"  {entry.observation_type.value:24} mean error {entry.mean_absolute_error:7.2f}"
            f"  ({entry.mean_relative_error:6.1%} of the average true value)"
        )


if __name__ == "__main__":
    main()
