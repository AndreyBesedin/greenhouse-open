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

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat


class Vector3(BaseModel):
    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    x: float
    y: float
    z: float

    def cross(self, other: Vector3) -> Vector3:
        """The vector at right angles to both, right-handed: x cross y is z."""
        return Vector3(
            x=self.y * other.z - self.z * other.y,
            y=self.z * other.x - self.x * other.z,
            z=self.x * other.y - self.y * other.x,
        )


class Point2(BaseModel):
    """A point in a shape's own x-y plane."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    x: float
    y: float


class Quaternion(BaseModel):
    """A rotation as a unit quaternion; the default is no rotation."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def about(cls, axis: Vector3, angle: float) -> Quaternion:
        """A turn by `angle` radians about the unit vector `axis`, counter-clockwise
        when the axis points at the viewer."""
        half = angle / 2
        return cls(
            w=math.cos(half),
            x=axis.x * math.sin(half),
            y=axis.y * math.sin(half),
            z=axis.z * math.sin(half),
        )

    @classmethod
    def from_axes(cls, x_axis: Vector3, y_axis: Vector3) -> Quaternion:
        """The rotation that turns a frame's x and y axes onto `x_axis` and
        `y_axis`, two unit vectors at right angles; its z turns onto their cross
        product."""
        z_axis = x_axis.cross(y_axis)
        # The rotation matrix's columns are the turned axes.
        m00, m10, m20 = x_axis.x, x_axis.y, x_axis.z
        m01, m11, m21 = y_axis.x, y_axis.y, y_axis.z
        m02, m12, m22 = z_axis.x, z_axis.y, z_axis.z
        # From whichever diagonal term is largest, for numerical stability.
        trace = m00 + m11 + m22
        if trace > 0:
            root = math.sqrt(1 + trace)
            return cls(
                w=root / 2,
                x=(m21 - m12) / (2 * root),
                y=(m02 - m20) / (2 * root),
                z=(m10 - m01) / (2 * root),
            )
        if m00 > m11 and m00 > m22:
            root = math.sqrt(1 + m00 - m11 - m22)
            return cls(
                w=(m21 - m12) / (2 * root),
                x=root / 2,
                y=(m01 + m10) / (2 * root),
                z=(m02 + m20) / (2 * root),
            )
        if m11 > m22:
            root = math.sqrt(1 + m11 - m00 - m22)
            return cls(
                w=(m02 - m20) / (2 * root),
                x=(m01 + m10) / (2 * root),
                y=root / 2,
                z=(m12 + m21) / (2 * root),
            )
        root = math.sqrt(1 + m22 - m00 - m11)
        return cls(
            w=(m10 - m01) / (2 * root),
            x=(m02 + m20) / (2 * root),
            y=(m12 + m21) / (2 * root),
            z=root / 2,
        )

    def after(self, first: Quaternion) -> Quaternion:
        """The rotation that turns by `first`, then by this one."""
        return Quaternion(
            w=self.w * first.w - self.x * first.x - self.y * first.y - self.z * first.z,
            x=self.w * first.x + self.x * first.w + self.y * first.z - self.z * first.y,
            y=self.w * first.y - self.x * first.z + self.y * first.w + self.z * first.x,
            z=self.w * first.z + self.x * first.y - self.y * first.x + self.z * first.w,
        )

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

    def after(self, inner: Transform) -> Transform:
        """Places a frame given within this one: `inner`, then this transform."""
        return Transform(
            position=self.apply(inner.position), rotation=self.rotation.after(inner.rotation)
        )

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


class Polygon(BaseModel):
    """A flat polygon in its frame's x-y plane, facing +z: its corners in
    order, counter-clockwise as seen from its front, such as a greenhouse's
    gable end."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["polygon"] = "polygon"
    points: list[Point2] = Field(min_length=3)


class Sphere(BaseModel):
    """A sphere centred on its frame's origin, such as a flower bud or a
    fruit."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["sphere"] = "sphere"
    radius: PositiveFloat


class Axes(BaseModel):
    """A reference marker: one arrow from the origin along each of +x, +y and
    +z."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    shape: Literal["axes"] = "axes"
    length: PositiveFloat


type Shape = Annotated[
    Plane | Cylinder | Box | Polygon | Sphere | Axes, Field(discriminator="shape")
]
