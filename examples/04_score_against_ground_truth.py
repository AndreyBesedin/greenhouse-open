"""Score what a run's sensors and its crop walk reported against what was really true.

    python examples/04_score_against_ground_truth.py

Only a simulation knows the truth behind its observations. Ground truth
leaves the run through a separate, evaluation-only interface
(`greenhouse_sim.ground_truth`), never as an observation, so decision logic
cannot accidentally use it. Here it measures how noisy the sensing is, the
baseline any state reconstruction has to beat: each sensor's readings
against the air or the weather it truly sampled, and each day's walk
through the crop against each plant as its crop model measures it.

The run is the climate box's, through its first two days and up to the
third day's walk at noon.
"""

from datetime import timedelta
from typing import Final

from greenhouse_protocol.observation import Observation
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import ground_truth
from greenhouse_sim.services import sensors
from greenhouse_sim.services.crop_log import WALK_S, crop_records
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "climate_box"  # a small, shut house of 32 plants
DAYS: Final = 3
UNTIL_S: Final = (DAYS - 1) * DAY_S + WALK_S


def main() -> None:
    run = RunRequest(SCENARIO)
    with Simulator() as simulator:
        # The run's observation log, as its consumers are delivered it: its
        # sensors' readings, and each day's walk through its crop.
        log = sensors.observations(simulator, run, UNTIL_S, from_s=0.0)
        observations: list[Observation] = list(log.observations)
        for day in range(DAYS):
            walked, _ = crop_records(simulator, run, day, log.start, log.run_id)
            until = log.start + timedelta(seconds=UNTIL_S)
            observations += [o for o in walked if o.timestamp <= until]
        truth = ground_truth(simulator, run, UNTIL_S)

    report = observation_accuracy(observations, truth)
    print(f"scored {report.readings} readings of {report.run_id} over {DAYS} days")
    for entry in report.by_type:
        print(
            f"  {entry.observation_type.value:30} mean error {entry.mean_absolute_error:8.2f}"
            f"  ({entry.mean_relative_error:6.1%} of the average true value)"
        )


if __name__ == "__main__":
    main()
