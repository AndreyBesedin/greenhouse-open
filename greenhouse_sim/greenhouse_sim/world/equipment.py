"""Climate equipment placed in a greenhouse: fans, heaters and dehumidifiers
(P05).

Equipment is placed in a scenario's layout file, beside its fixtures, each
piece by an identifier, where it stands and which way it faces, its size,
and its rated capacity: what it does at full power. How hard it runs is not
part of the layout: that is a level from 0 (off) to 1 (full), which
commands set (`greenhouse_sim.climate.commands`).

Each piece is also a fixture (`fixture`), for what checks a layout's
geometry: a heater or a dehumidifier stands on the floor and is in the way
of air and of robots, as an obstacle is, so it joins the layout's
obstructions; a fan hangs from the structure, small beside the air it moves,
and is in the way of nothing.
"""

import math
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat

from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.domain.layout import FixtureKind, Material, Obstruction
from greenhouse_sim.world.fixtures import Fixture
from greenhouse_sim.world.geometry import Box, Cylinder, Quaternion, Transform, Vector3

# A fan's housing, along its axis, in metres.
FAN_DEPTH_M: Final = 0.3
_UP: Final = Vector3(x=0.0, y=0.0, z=1.0)
_ACROSS: Final = Vector3(x=0.0, y=1.0, z=0.0)
# What a heater's or dehumidifier's body is in the way of; a fan, nothing.
_BODY_OBSTRUCTS: Final = frozenset({Obstruction.MOVEMENT, Obstruction.AIRFLOW})
_HANGING_OBSTRUCTS: Final[frozenset[Obstruction]] = frozenset()


class _Equipment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actuator_id: str
    # Which way it faces, a turn about the vertical from the greenhouse's x;
    # a fan blows that way.
    heading: float = 0.0

    def facing(self) -> Vector3:
        """The unit vector it faces along, level."""
        return Vector3(x=math.cos(self.heading), y=math.sin(self.heading), z=0.0)


class Fan(_Equipment):
    """A fan: a rotor of a diameter, centred on `position`, blowing its rated
    flow of air along its heading."""

    kind: Literal[ActuatorKind.FAN] = ActuatorKind.FAN
    position: Vector3
    diameter_m: PositiveFloat
    flow_m3_s: PositiveFloat

    def transform(self) -> Transform:
        """Its housing's frame: a cylinder on its back face, its axis laid
        down along the heading (a quarter turn about y takes +z to +x)."""
        lay_down = Quaternion.about(_ACROSS, math.pi / 2)
        turn = Quaternion.about(_UP, self.heading)
        facing = self.facing()
        half = FAN_DEPTH_M / 2
        back = Vector3(
            x=self.position.x - facing.x * half,
            y=self.position.y - facing.y * half,
            z=self.position.z,
        )
        return Transform(position=back, rotation=turn.after(lay_down))

    def shape(self) -> Cylinder:
        return Cylinder(radius=self.diameter_m / 2, height=FAN_DEPTH_M)

    def fixture(self) -> Fixture:
        """Its housing, in the way of nothing."""
        return Fixture(
            fixture_id=self.actuator_id,
            kind=FixtureKind.OBSTACLE,
            transform=self.transform(),
            shape=self.shape(),
            material=Material.STEEL,
            obstructs=_HANGING_OBSTRUCTS,
        )

    def rated(self) -> dict[str, float]:
        return {"diameter_m": self.diameter_m, "flow_m3_s": self.flow_m3_s}


class _Unit(_Equipment):
    """A unit standing on the floor or anything else: a box, its base centred
    on `base`."""

    base: Vector3
    size_x: PositiveFloat
    size_y: PositiveFloat
    size_z: PositiveFloat

    def transform(self) -> Transform:
        return Transform(position=self.base, rotation=Quaternion.about(_UP, self.heading))

    def shape(self) -> Box:
        return Box(size_x=self.size_x, size_y=self.size_y, size_z=self.size_z)

    def fixture(self) -> Fixture:
        """Its body, as an obstacle in the way of air and robots."""
        return Fixture(
            fixture_id=self.actuator_id,
            kind=FixtureKind.OBSTACLE,
            transform=self.transform(),
            shape=self.shape(),
            material=Material.STEEL,
            obstructs=_BODY_OBSTRUCTS,
        )


class Heater(_Unit):
    """A unit heater: its rated power, all of it given to the air as heat."""

    kind: Literal[ActuatorKind.HEATER] = ActuatorKind.HEATER
    power_w: PositiveFloat

    def rated(self) -> dict[str, float]:
        return {"power_w": self.power_w}


class Dehumidifier(_Unit):
    """A dehumidifier: the water it takes out of the air at full power, and
    the heat it gives the air while it does."""

    kind: Literal[ActuatorKind.DEHUMIDIFIER] = ActuatorKind.DEHUMIDIFIER
    removal_kg_h: PositiveFloat
    heat_w: PositiveFloat

    def rated(self) -> dict[str, float]:
        return {"removal_kg_h": self.removal_kg_h, "heat_w": self.heat_w}


type Equipment = Annotated[Fan | Heater | Dehumidifier, Field(discriminator="kind")]
