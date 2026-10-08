"""A run's observation log, beyond its readings (P06.6): each point
sensor's freshness, and its cameras' frames.

The readings themselves are `greenhouse_sim.sensors.air.observe`'s: every
sensor's observations delivered by a moment, in the order delivered. The
log is append-only: up to a later moment it holds what it held up to an
earlier one, in the same order, and more after it.

**Freshness.** A sensor takes a sample every `cadence_s` from the run's
start, and each is due its latency after it was taken. A sensor is fresh
while the latest reading due from it by then has come, and stale once one
has not: a sample that dropped out leaves it stale until the next comes,
and a sensor whose quantity no model gives is stale from its first due
reading on. Before its first reading is due, it is neither. Staleness is
the log's to say, not a quality of any reading.

**Frames.** A camera takes a frame every `cadence_s` from the run's start.
The log records each frame's metadata, not its pixels: the moment, where
the camera stood and looked, its intrinsics, and what a frame holds, an RGB
picture and a depth image. A frame is drawn on demand from the scene and
the camera, so it needs storing nowhere. A frame's instance pass is the
simulator's truth, which no camera records, and it stays out of the log.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

from greenhouse_protocol.enums import CaptureModality
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.sensor import CameraIntrinsics
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.records import observation_id
from greenhouse_sim.sensors.air import samples
from greenhouse_sim.world.geometry import Quaternion, Vector3
from greenhouse_sim.world.sensors import Camera, PointSensor

# What each of a camera's frames holds.
FRAME_MODALITIES: Final = (CaptureModality.RGB, CaptureModality.DEPTH)


class SensorFreshness(BaseModel):
    """Whether a point sensor's latest reading due by a moment has come."""

    model_config = ConfigDict(frozen=True)

    sensor_id: str
    # When the latest reading due by then was taken; None before the first
    # is due.
    due_at: datetime | None
    # When the latest reading delivered by then was taken; None before one
    # has been.
    latest_at: datetime | None
    stale: bool


class CameraFrame(BaseModel):
    """A frame a camera took: when, from where, looking where, and with what
    intrinsics; what it holds, but not its pixels."""

    model_config = ConfigDict(frozen=True)

    frame_id: str
    sensor_id: str
    timestamp: datetime
    position: Vector3
    target: Vector3
    rotation: Quaternion
    intrinsics: CameraIntrinsics
    modalities: tuple[CaptureModality, ...] = FRAME_MODALITIES


def due(sensor: PointSensor, until_s: float, latency_s: float) -> float | None:
    """When the latest reading due from a sensor by `until_s` was taken, in
    seconds from the run's start; None if none is due yet."""
    if until_s < latency_s:
        return None
    return samples(sensor, until_s - latency_s)[-1]


def freshness(
    sensors: Sequence[PointSensor],
    observations: Sequence[Observation],
    until_s: float,
    *,
    start: datetime,
    clean: bool = False,
) -> list[SensorFreshness]:
    """Each sensor's freshness at `until_s`, from its `observations`
    delivered by then; its readings as a clean sensor's, on time, if
    `clean`."""
    latest: dict[str, datetime] = {}
    for observation in observations:
        if observation.sensor_id is not None:
            known = latest.get(observation.sensor_id, observation.timestamp)
            latest[observation.sensor_id] = max(known, observation.timestamp)
    states = []
    for sensor in sensors:
        latency = 0.0 if clean else sensor.imperfections.latency_s
        moment = due(sensor, until_s, latency)
        due_at = None if moment is None else start + timedelta(seconds=moment)
        latest_at = latest.get(sensor.sensor_id)
        states.append(
            SensorFreshness(
                sensor_id=sensor.sensor_id,
                due_at=due_at,
                latest_at=latest_at,
                stale=due_at is not None and (latest_at is None or latest_at < due_at),
            )
        )
    return states


def frames(cameras: Sequence[Camera], until_s: float, *, start: datetime) -> list[CameraFrame]:
    """Every frame `cameras` took up to `until_s`, in the order taken."""
    taken = [
        CameraFrame(
            frame_id=observation_id(camera.sensor_id, start + timedelta(seconds=moment), "frame"),
            sensor_id=camera.sensor_id,
            timestamp=start + timedelta(seconds=moment),
            position=camera.position,
            target=camera.target,
            rotation=camera.rotation(),
            intrinsics=camera.intrinsics,
        )
        for camera in cameras
        for moment in samples(camera, until_s)
    ]
    return sorted(taken, key=lambda frame: (frame.timestamp, frame.sensor_id))
