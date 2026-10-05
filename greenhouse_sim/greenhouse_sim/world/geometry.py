"""Where things are in the simulated world, and what shape they have.

Conventions, fixed for every producer and consumer of geometry (decision
0007):

- SI units: positions and sizes in metres, angles in radians.
- World axes are right-handed with z up. The ground is the plane z = 0.
- Orientation is a unit quaternion with named components, so no consumer has
  to guess their order.

Shapes are described by their dimensions in their own frame, which a
`Transform` places in the world. Nothing here knows how a renderer draws them:
a viewer whose axes differ converts once, at the root of its scene.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat


class Vector3(BaseModel):
    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    x: float
    y: float
    z: float


class Quaternion(BaseModel):
    """A rotation as a unit quaternion; the default is no rotation."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def rotate(self, vector: Vector3) -> Vector3:
        """`vector`, turned by this rotation."""
        # v' = v + w t + q x t, with t = 2 (q x v), for the unit quaternion (w, q).
        tx = 2 * (self.y * vector.z - self.z * vector.y)
        ty = 2 * (self.z * vector.x - self.x * vector.z)
        tz = 2 * (self.x * vector.y - self.y * vector.x)
        return Vector3(
            x=vector.x + self.w * tx + (self.y * tz - self.z * ty),
            y=vector.y + self.w * ty + (self.z * tx - self.x * tz),
            z=vector.z + self.w * tz + (self.x * ty - self.y * tx),
        )


class Transform(BaseModel):
    """Places a shape's own frame in the world: rotate, then translate."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    position: Vector3
    rotation: Quaternion = Quaternion()

    def apply(self, point: Vector3) -> Vector3:
        """Where a point given in the shape's own frame lies in the world."""
        turned = self.rotation.rotate(point)
        return Vector3(
            x=turned.x + self.position.x,
            y=turned.y + self.position.y,
            z=turned.z + self.position.z,
        )


class Plane(BaseModel):
    """A flat rectangle in its frame's x-y plane, centred on its origin,
    facing +z."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["plane"] = "plane"
    size_x: PositiveFloat
    size_y: PositiveFloat


class Cylinder(BaseModel):
    """An upright cylinder: its base is centred on its frame's origin and it
    rises along +z. A height of zero is allowed: a plant can be lowered by its
    whole visible height."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["cylinder"] = "cylinder"
    radius: PositiveFloat
    height: NonNegativeFloat


class Box(BaseModel):
    """A rectangular box standing on its frame's origin: its base is centred
    on the origin, and it rises along +z."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["box"] = "box"
    size_x: PositiveFloat
    size_y: PositiveFloat
    size_z: PositiveFloat


class Axes(BaseModel):
    """A reference marker: one arrow from the origin along each of +x, +y and
    +z."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["axes"] = "axes"
    length: PositiveFloat


type Shape = Annotated[Plane | Cylinder | Box | Axes, Field(discriminator="shape")]
