"""A sensor and what is known about its optics.

A sensor belongs to the sensing layer, not to the greenhouse's physical
hierarchy: it is attached to a greenhouse and, when known, to the compartment
it observes. Only what the source states is recorded. Intrinsics come from calibration
files; where the source gives nothing but a verbal mounting description, that
text is kept and no numeric pose is invented."""

from pydantic import BaseModel, ConfigDict, Field

from greenhouse_protocol.enums import CaptureModality
from greenhouse_protocol.provenance import RecordSource


class CameraIntrinsics(BaseModel):
    """Pinhole intrinsics of one image stream, in pixels, with the
    calibration's distortion coefficients exactly as given."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fx: float = Field(gt=0)
    fy: float = Field(gt=0)
    ppx: float
    ppy: float
    distortion: tuple[float, ...] = ()


class Sensor(BaseModel):
    model_config = ConfigDict(frozen=True)

    sensor_id: str
    greenhouse_id: str
    # The compartment the sensor observes, when the greenhouse has them.
    compartment_id: str | None = None
    hardware_model: str
    # The hardware serial number, when the source records one.
    device_id: str | None = None
    # One entry per stream the sensor writes; empty for sensors without optics.
    intrinsics: dict[CaptureModality, CameraIntrinsics] = Field(default_factory=dict)
    # How the source describes the mounting, when that is all it gives.
    nominal_mounting: str | None = None
    source: RecordSource
