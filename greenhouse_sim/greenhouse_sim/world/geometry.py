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
    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    z: float


class Quaternion(BaseModel):
    """A rotation as a unit quaternion; the default is no rotation."""

    model_config = ConfigDict(frozen=True)

    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Transform(BaseModel):
    """Places a shape's own frame in the world: rotate, then translate."""

    model_config = ConfigDict(frozen=True)

    position: Vector3
    rotation: Quaternion = Quaternion()


class Plane(BaseModel):
    """A flat rectangle in its frame's x-y plane, centred on its origin,
    facing +z."""

    model_config = ConfigDict(frozen=True)

    shape: Literal["plane"] = "plane"
    size_x: PositiveFloat
    size_y: PositiveFloat


class Cylinder(BaseModel):
    """An upright cylinder: its base is centred on its frame's origin and it
    rises along +z. A height of zero is allowed: a plant can be lowered by its
    whole visible height."""

    model_config = ConfigDict(frozen=True)

    shape: Literal["cylinder"] = "cylinder"
    radius: PositiveFloat
    height: NonNegativeFloat


class Axes(BaseModel):
    """A reference marker: one arrow from the origin along each of +x, +y and
    +z."""

    model_config = ConfigDict(frozen=True)

    shape: Literal["axes"] = "axes"
    length: PositiveFloat


type Shape = Annotated[Plane | Cylinder | Axes, Field(discriminator="shape")]
