"""What was truly the case in a run, for evaluation only.

A run publishes noisy observations of what it works out, as a real
greenhouse's instruments and the people walking its crop would: each point
sensor's readings of the air or the weather where it stands, with its
imperfections (`greenhouse_sim.sensors.air`), and each day's walk through
the crop, with its miscounts and its measuring errors
(`greenhouse_sim.services.crop_log`). A consumer reconstructs its picture
from them. That gap is the whole value of simulation for evaluation: it is
the only setting where a prediction can be scored against what was really
the case.

Truth leaves the run by a separate path from observations:

    run -- observations --> canonical records --> consumer
     |
     +-- ground truth ---------------------> evaluation only

So this is a separate interface, not a richer observation. Decision-making
code must never read it, or a policy would be scored on a shortcut that
disappears the moment it meets a real greenhouse. Within this package only
`greenhouse_sim.evaluation` imports it, which `tests/test_dependencies.py`
enforces.

Each true reading is what a perfect instrument would have read in place of
one of the run's observations: a sensor's, at its sample's moment, the air
or the weather it sampled (`greenhouse_sim.evaluation.sensor_truth`); the
walk's, a plant as its crop model measures it
(`CropRegistration.measured`). Values no observation measures, such as a
plant's growth multiplier, stay inside the run (decision 0059).
"""

from datetime import datetime, timedelta

from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import crop, sensors
from greenhouse_sim.services.crop_log import WALK_S, walk_moment, walked_truly
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.simulator import Simulator

# What tells one reading of a run from another: the sensor that took it or
# the plant it is of, what it measures, and when it was taken.
type Reading = tuple[str | None, str | None, ObservationType, datetime]


class TrueReading(BaseModel):
    """What a perfect instrument would have read in place of one of a run's
    observations: the point sensor `sensor_id`'s, of the air or the weather
    where it stands, at one of its sample moments; or the crop walk's, of
    the plant `plant_id`, on one day, as its crop model measures it."""

    model_config = ConfigDict(frozen=True)

    observation_type: ObservationType
    timestamp: datetime
    value: float
    sensor_id: str | None = None
    plant_id: str | None = None

    def reading(self) -> Reading:
        return (self.sensor_id, self.plant_id, self.observation_type, self.timestamp)


class GroundTruth(BaseModel):
    """What was truly the case in a run, reading by reading, up to a moment
    of it."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    greenhouse_id: str
    readings: list[TrueReading]


def reading(observation: Observation) -> Reading:
    """What tells an observation from another of its run, as a true
    reading's `reading` does."""
    return (
        observation.sensor_id,
        observation.plant_id,
        observation.observation_type,
        observation.timestamp,
    )


def ground_truth(simulator: Simulator, run: RunRequest, until_s: float) -> GroundTruth:
    """What a run's point sensors truly sampled from its start to `until_s`,
    and what its walks through the crop truly found on each day walked by
    then."""
    config = scenario(simulator.catalogue, run.scenario_id)
    start = sensors.run_start(simulator.catalogue, run.scenario_id)
    sampled = sensors.truth(simulator, run, until_s, from_s=0.0)
    readings = [
        TrueReading(
            sensor_id=each.sensor_id,
            observation_type=each.observation_type,
            timestamp=start + timedelta(seconds=moment),
            value=value,
        )
        for each in sampled.sensors
        for moment, value in zip(each.times_s, each.values, strict=True)
        if value is not None
    ]
    grown = crop.scenario_crop(simulator, run)
    measured = registration(config).measured
    walked = [day for day in range(config.duration_days) if day * DAY_S + WALK_S <= until_s]
    for day in walked:
        at = walk_moment(start, day)
        readings += [
            TrueReading(plant_id=plant.plant_id, observation_type=kind, timestamp=at, value=value)
            for plant in grown.plants_on(day)
            for kind, value in walked_truly(measured(plant)).items()
        ]
    return GroundTruth(run_id=sampled.run_id, greenhouse_id=config.greenhouse_id, readings=readings)
