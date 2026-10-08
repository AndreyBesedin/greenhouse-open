"""What the air really was where each point sensor stands, for evaluation and
QA only (P06.2).

A sensor's observations are what leaves the simulator on the normal path
(`greenhouse_sim.sensors.air`). What it sampled, the air itself, leaves by
this one: at each of a sensor's sample moments, what a perfect sensor there
would read. Decision-making code must never read it, or a policy would be
scored on a shortcut that disappears the moment it meets a real greenhouse;
`tests/test_sensor_observations.py` checks that nothing on the observation
path imports it.
"""

from collections.abc import Sequence

from greenhouse_protocol.enums import ObservationType
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.sensors.air import OBSERVATION_TYPES, AirAt, reads, samples
from greenhouse_sim.world.sensors import PointSensor


class SensorTruth(BaseModel):
    """What a perfect sensor would have read at each of a sensor's sample
    moments, in seconds from the run's start: None where the air carries no
    such quantity."""

    model_config = ConfigDict(frozen=True)

    sensor_id: str
    observation_type: ObservationType
    unit: str
    times_s: list[float]
    values: list[float | None]


def sensor_truth(
    sensors: Sequence[PointSensor], air_at: AirAt, until_s: float
) -> list[SensorTruth]:
    """What each sensor sampled, truly, up to `until_s`."""
    truths = []
    for sensor in sensors:
        moments = samples(sensor, until_s)
        truths.append(
            SensorTruth(
                sensor_id=sensor.sensor_id,
                observation_type=OBSERVATION_TYPES[sensor.kind],
                unit=sensor.unit(),
                times_s=moments,
                values=[reads(sensor, air_at(moment)) for moment in moments],
            )
        )
    return truths
