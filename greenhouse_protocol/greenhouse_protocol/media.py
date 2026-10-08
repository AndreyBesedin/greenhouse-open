"""A recorded image, by reference: which sensor took it, when, in what
modality, and where its bytes live; and a camera's frame: when it was
taken, from where, turned how and with what intrinsics.

Pixels never enter a record store. Perception reads the artifact through
a storage layer and emits derived Observations that point back to the
capture they came from.

A frame says what a capture alone does not: the camera's pose and
intrinsics at that moment. Its images, when they are stored, are captures
of the same sensor and instant (`capture_ids`). A frame may also stand
alone, as a simulator's do: drawn on demand from the scene and the camera,
and stored nowhere.
"""

import math
from datetime import datetime
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from greenhouse_protocol.enums import CaptureModality
from greenhouse_protocol.provenance import RecordSource
from greenhouse_protocol.sensor import CameraIntrinsics

# How far a pose's quaternion's length may be from one.
UNIT_TOLERANCE: Final = 1e-6


class MediaCapture(BaseModel):
    model_config = ConfigDict(frozen=True)

    capture_id: str
    greenhouse_id: str
    # The compartment the sensor looks at, when the greenhouse has them.
    compartment_id: str | None = None
    sensor_id: str
    timestamp: datetime
    modality: CaptureModality
    # Where the bytes are: "<dataset id>/<artifact name>!<member path>" for a
    # member of a source archive. The storage layer resolves it; the domain
    # never opens it.
    artifact_uri: str
    source: RecordSource

    @field_validator("timestamp")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("a capture timestamp must be timezone-aware")
        return value


class CameraPose(BaseModel):
    """Where a camera stood, and how it was turned, in its greenhouse's
    frame: x along the house, y across it and z up, in metres, from a corner
    of its floor. The rotation, a unit quaternion (w, x, y, z), turns the
    camera's own frame into the greenhouse's. In the camera's frame x runs
    along the way it looks, y to its left and z up, so its picture's u runs
    against y and its v against z. The optical convention, z along the way
    it looks, x right and y down, is a fixed turn away."""

    model_config = ConfigDict(frozen=True)

    x_m: float
    y_m: float
    z_m: float
    qw: float
    qx: float
    qy: float
    qz: float

    @model_validator(mode="after")
    def _a_turn(self) -> Self:
        length = math.sqrt(self.qw**2 + self.qx**2 + self.qy**2 + self.qz**2)
        if abs(length - 1.0) > UNIT_TOLERANCE:
            raise ValueError(f"a pose's rotation must be a unit quaternion, not of length {length}")
        return self


class CameraFrame(BaseModel):
    """A frame a camera took: when, from where, turned how, with what
    intrinsics, and what images it holds."""

    model_config = ConfigDict(frozen=True)

    frame_id: str
    greenhouse_id: str
    # The compartment the camera looks at, when the greenhouse has them.
    compartment_id: str | None = None
    sensor_id: str
    timestamp: datetime
    pose: CameraPose
    intrinsics: CameraIntrinsics
    # What the frame holds, such as an RGB image and a depth image aligned
    # to it.
    modalities: tuple[CaptureModality, ...] = Field(min_length=1)
    source: RecordSource
    # When the frame was delivered, if after it was taken (`timestamp`).
    delivered_at: datetime | None = None
    # The captures holding its images, when they are stored.
    capture_ids: tuple[str, ...] = ()
