"""A run's observation log, beyond its readings (P06.6): each point
sensor's freshness, and its cameras' frames.

The readings themselves are `greenhouse_sim.sensors.air.observe`'s: every
sensor's observations delivered by a moment, in the order delivered. The
log is append-only: up to a later moment it holds what it held up to an
earlier one, in the same order, and more after it.

**Freshness.** A sensor takes a sample every `cadence_s` from the run's
start, and each is due its latency after it was taken. A sensor is fresh
while the latest reading due from it by then has come, and stale once one
has not: a sample that dropped out leaves it stale until the next comes.
Before its first reading is due, it is waiting. A sensor whose quantity
nothing in the run gives, as no model gives PAR yet, is unavailable: it
will never read, which is not the same as having missed a reading.
Freshness is the log's to say, not a quality of any reading.

**Frames.** A camera takes a frame every `cadence_s` from the run's start.
The log records each frame as the protocol's `CameraFrame`, its metadata
and not its pixels: the moment, the camera's pose, its intrinsics, and what
a frame holds, an RGB picture and a depth image. A frame is drawn on demand
from the scene and the camera, so it needs storing nowhere, and refers to
no stored capture. A frame's instance pass is the simulator's truth, which
no camera records, and it stays out of the log.
"""

from collections.abc import Collection, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from greenhouse_protocol.enums import CaptureModality, SourceType
from greenhouse_protocol.media import CameraFrame, CameraPose
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.records import observation_id
from greenhouse_sim.sensors.air import samples
from greenhouse_sim.world.sensors import Camera, PointSensor

# What each of a camera's frames holds.
FRAME_MODALITIES: Final = (CaptureModality.RGB, CaptureModality.DEPTH)


class Freshness(StrEnum):
    """Where a point sensor stands, at a moment, with its readings."""

    # Its first reading is not due yet.
    WAITING = "waiting"
    # The latest reading due from it has come.
    FRESH = "fresh"
    # The latest reading due from it has not come.
    STALE = "stale"
    # Nothing in the run gives its quantity: it will never read.
    UNAVAILABLE = "unavailable"


class SensorFreshness(BaseModel):
    """Whether a point sensor's latest reading due by a moment has come."""

    model_config = ConfigDict(frozen=True)

    sensor_id: str
    state: Freshness
    # When the latest reading due by then was taken; None before the first
    # is due.
    due_at: datetime | None
    # When the latest reading delivered by then was taken; None before one
    # has been.
    latest_at: datetime | None


def due(sensor: PointSensor, until_s: float, latency_s: float) -> float | None:
    """When the latest reading due from a sensor by `until_s` was taken, in
    seconds from the run's start; None if none is due yet."""
    if until_s < latency_s:
        return None
    return samples(sensor, until_s - latency_s)[-1]


def _state(due_at: datetime | None, latest_at: datetime | None, available: bool) -> Freshness:
    if not available:
        return Freshness.UNAVAILABLE
    if due_at is None:
        return Freshness.WAITING
    if latest_at is None or latest_at < due_at:
        return Freshness.STALE
    return Freshness.FRESH


def freshness(
    sensors: Sequence[PointSensor],
    observations: Sequence[Observation],
    until_s: float,
    *,
    start: datetime,
    unavailable: Collection[str] = (),
    clean: bool = False,
) -> list[SensorFreshness]:
    """Each sensor's freshness at `until_s`, from its `observations`
    delivered by then; `unavailable` names the sensors whose quantity
    nothing in the run gives. Readings are a clean sensor's, on time, if
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
                state=_state(due_at, latest_at, sensor.sensor_id not in unavailable),
                due_at=due_at,
                latest_at=latest_at,
            )
        )
    return states


def _pose(camera: Camera) -> CameraPose:
    turn = camera.rotation()
    position = camera.position
    return CameraPose(
        x_m=position.x,
        y_m=position.y,
        z_m=position.z,
        qw=turn.w,
        qx=turn.x,
        qy=turn.y,
        qz=turn.z,
    )


def frames(
    cameras: Sequence[Camera],
    until_s: float,
    *,
    start: datetime,
    greenhouse_id: str,
    run_id: str,
) -> list[CameraFrame]:
    """Every frame `cameras` took up to `until_s`, in the order taken."""
    source = RecordSource(type=SourceType.SIMULATION, source_id=run_id)
    taken = [
        CameraFrame(
            frame_id=observation_id(camera.sensor_id, start + timedelta(seconds=moment), "frame"),
            greenhouse_id=greenhouse_id,
            sensor_id=camera.sensor_id,
            timestamp=start + timedelta(seconds=moment),
            pose=_pose(camera),
            intrinsics=camera.intrinsics,
            modalities=FRAME_MODALITIES,
            source=source,
        )
        for camera in cameras
        for moment in samples(camera, until_s)
    ]
    return sorted(taken, key=lambda frame: (frame.timestamp, frame.sensor_id))
