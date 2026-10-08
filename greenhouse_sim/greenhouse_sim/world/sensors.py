"""Sensors placed in a greenhouse: point sensors, which read one quantity of
the air where they stand, and cameras, which see the scene (P06).

Sensors are placed in a scenario's layout file, beside its fixtures and
equipment, each by an identifier, where it stands, how often it takes a
sample, and how it errs (`Imperfections`). A camera adds the point it looks
at and its intrinsics, as the protocol describes a real camera's
(`greenhouse_protocol.sensor.CameraIntrinsics`).

Each sensor is also a fixture (`fixture`), for what checks a layout's
geometry: a small housing, in the way of nothing.

A camera projects a point by plain pinhole geometry (`project`): in its own
frame, x along the way it looks, y to its left and z up, a point at
(x, y, z) lands on pixel (ppx − fx y / x, ppy − fy z / x), u to the right
and v down its picture, as image pixels are counted. The viewer draws its
picture with the same projection.
"""

import math
from typing import Annotated, Final, Literal, Self

from greenhouse_protocol.sensor import CameraIntrinsics
from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat, model_validator

from greenhouse_sim.domain.layout import FixtureKind, Material, Obstruction
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.world.fixtures import Fixture
from greenhouse_sim.world.geometry import Box, Quaternion, Transform, Vector3

# A point sensor's housing, a cube this wide, in metres.
SENSOR_SIZE_M: Final = 0.08
# A camera's body: its length along the way it looks, its width and height.
CAMERA_BODY_M: Final = (0.12, 0.08, 0.08)
_UP: Final = Vector3(x=0.0, y=0.0, z=1.0)
_ACROSS: Final = Vector3(x=0.0, y=1.0, z=0.0)
_NOTHING: Final[frozenset[Obstruction]] = frozenset()
# What each kind of point sensor reports its quantity in.
UNITS: Final = {
    SensorKind.TEMPERATURE: "°C",
    SensorKind.HUMIDITY: "%",
    SensorKind.CO2: "ppm",
    SensorKind.AIR_SPEED: "m/s",
    SensorKind.PAR: "µmol/m²/s",
}

type PointKind = Literal[
    SensorKind.TEMPERATURE,
    SensorKind.HUMIDITY,
    SensorKind.CO2,
    SensorKind.AIR_SPEED,
    SensorKind.PAR,
]


class Imperfections(BaseModel):
    """How a sensor errs, each in its own unit; all nothing for a clean one.

    Noise is Gaussian, of a standard deviation; a reading is rounded to the
    quantization step; a fixed bias is added, and a drift that grows linearly
    with time since the run's start; a sample drops out with a probability;
    and a reading is delivered a fixed time after its sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    noise_sd: NonNegativeFloat = 0.0
    quantization: NonNegativeFloat = 0.0
    bias: float = 0.0
    drift_per_hour: float = 0.0
    dropout: Annotated[float, Field(ge=0.0, lt=1.0)] = 0.0
    latency_s: NonNegativeFloat = 0.0

    def clean(self) -> bool:
        return self == Imperfections()


class _Sensor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sensor_id: str
    position: Vector3
    # A sample every so many seconds of a run.
    cadence_s: PositiveFloat = 60.0


class PointSensor(_Sensor):
    """A sensor reading one quantity of the air at its position."""

    kind: PointKind
    imperfections: Imperfections = Imperfections()

    def unit(self) -> str:
        return UNITS[self.kind]

    def fixture(self) -> Fixture:
        """Its housing, centred on its position, in the way of nothing."""
        half = SENSOR_SIZE_M / 2
        return Fixture(
            fixture_id=self.sensor_id,
            kind=FixtureKind.OBSTACLE,
            transform=Transform(
                position=Vector3(x=self.position.x, y=self.position.y, z=self.position.z - half)
            ),
            shape=Box(size_x=SENSOR_SIZE_M, size_y=SENSOR_SIZE_M, size_z=SENSOR_SIZE_M),
            material=Material.PLASTIC,
            obstructs=_NOTHING,
        )


class Camera(_Sensor):
    """A camera at its position, looking at `target`, with its intrinsics."""

    kind: Literal[SensorKind.CAMERA] = SensorKind.CAMERA
    target: Vector3
    intrinsics: CameraIntrinsics

    @model_validator(mode="after")
    def _looks_somewhere(self) -> Self:
        if self.looking() == (0.0, 0.0, 0.0):
            raise ValueError(f"camera {self.sensor_id!r} looks at the point it stands on")
        return self

    def looking(self) -> tuple[float, float, float]:
        """Where it looks, from where it stands."""
        return (
            self.target.x - self.position.x,
            self.target.y - self.position.y,
            self.target.z - self.position.z,
        )

    def rotation(self) -> Quaternion:
        """Its frame's turn: its x along the way it looks, its y level, so
        that its picture is upright."""
        dx, dy, dz = self.looking()
        heading = math.atan2(dy, dx)
        pitch = math.atan2(dz, math.hypot(dx, dy))
        # Pitching x up towards +z is a negative turn about y.
        return Quaternion.about(_UP, heading).after(Quaternion.about(_ACROSS, -pitch))

    def in_frame(self, point: Vector3) -> Vector3:
        """A point of the world in the camera's own frame: x along the way it
        looks, y to its left, z up."""
        q = self.rotation()
        back = Quaternion(w=q.w, x=-q.x, y=-q.y, z=-q.z)
        return back.rotate(
            Vector3(
                x=point.x - self.position.x,
                y=point.y - self.position.y,
                z=point.z - self.position.z,
            )
        )

    def project(self, point: Vector3) -> tuple[float, float] | None:
        """Where a point lands on the camera's picture, in pixels from its
        top left corner, u to the right and v down; None if it lies behind
        the camera. A point may land outside the picture (`sees`)."""
        seen = self.in_frame(point)
        if seen.x <= 0:
            return None
        intrinsics = self.intrinsics
        return (
            intrinsics.ppx - intrinsics.fx * seen.y / seen.x,
            intrinsics.ppy - intrinsics.fy * seen.z / seen.x,
        )

    def sees(self, point: Vector3) -> bool:
        """Whether a point lands on the camera's picture, ignoring what may
        hide it."""
        pixel = self.project(point)
        if pixel is None:
            return False
        u, v = pixel
        return 0 <= u < self.intrinsics.width and 0 <= v < self.intrinsics.height

    def transform(self) -> Transform:
        """Its body's frame: its base centred under its position."""
        _, _, height = CAMERA_BODY_M
        return Transform(
            position=Vector3(x=self.position.x, y=self.position.y, z=self.position.z - height / 2),
            rotation=self.rotation(),
        )

    def shape(self) -> Box:
        length, width, height = CAMERA_BODY_M
        return Box(size_x=length, size_y=width, size_z=height)

    def fixture(self) -> Fixture:
        """Its body, in the way of nothing."""
        return Fixture(
            fixture_id=self.sensor_id,
            kind=FixtureKind.OBSTACLE,
            transform=self.transform(),
            shape=self.shape(),
            material=Material.PLASTIC,
            obstructs=_NOTHING,
        )


type Sensor = Annotated[PointSensor | Camera, Field(discriminator="kind")]
