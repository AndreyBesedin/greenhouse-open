"""The greenhouse's envelope: where the greenhouse stands, and the space it encloses.

The greenhouse has a frame of its own (decision 0016). Its origin is a corner of
the floor; x runs along the greenhouse's length, y across its width, and z up,
so the greenhouse fills the positive octant of its frame. `origin` places that
frame in the world, by default at the world's origin, unrotated. Everything the
envelope describes is given in the greenhouse's frame, and `to_world` places it.

The envelope is a description, not geometry: its surfaces are generated from
it, for viewers now and for physics and airflow later, so a scenario, or later
an editor, changes the greenhouse by changing this description. P01 grows it
from the enclosed space to the floor, walls, roof, bays and openings.

Each surface is a rectangle that faces into the greenhouse, and carries a
semantic category. Walls are named as seen from the greenhouse's origin,
looking along its length (+x): the right side wall stands along y = 0, the
left along y = width, the front end wall at x = 0 and the back at x = length.
"""

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, PositiveFloat

from greenhouse_sim.world.geometry import Plane, Quaternion, Transform, Vector3

# Where a greenhouse stands unless a scenario says otherwise: its floor corner
# at the world's origin, its axes along the world's.
AT_WORLD_ORIGIN = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))


class SurfaceCategory(StrEnum):
    """What a surface of the envelope is, for every consumer of its geometry."""

    FLOOR = "floor"
    WALL = "wall"


class Surface(BaseModel):
    """One flat piece of the envelope: a rectangle placed in the greenhouse's
    frame, with its front (the plane's +z) facing into the greenhouse."""

    model_config = ConfigDict(frozen=True)

    surface_id: str
    category: SurfaceCategory
    transform: Transform
    shape: Plane


# Quarter turns that stand a plane facing +z up as a wall facing into the house.
_X_AXIS = Vector3(x=1.0, y=0.0, z=0.0)
_Y_AXIS = Vector3(x=0.0, y=1.0, z=0.0)
_FACING_PLUS_Y = Quaternion.about(_X_AXIS, -math.pi / 2)
_FACING_MINUS_Y = Quaternion.about(_X_AXIS, math.pi / 2)
_FACING_PLUS_X = Quaternion.about(_Y_AXIS, math.pi / 2)
_FACING_MINUS_X = Quaternion.about(_Y_AXIS, -math.pi / 2)


class Envelope(BaseModel):
    """A greenhouse's envelope, in metres."""

    model_config = ConfigDict(frozen=True)

    # Along the greenhouse's x.
    length: PositiveFloat
    # Along the greenhouse's y.
    width: PositiveFloat
    # From the floor to the highest point of the envelope.
    height: PositiveFloat
    # Places the greenhouse's frame in the world.
    origin: Transform = AT_WORLD_ORIGIN

    def bounds(self) -> tuple[Vector3, Vector3]:
        """The enclosed space's opposite corners, in the greenhouse's frame."""
        return (
            Vector3(x=0.0, y=0.0, z=0.0),
            Vector3(x=self.length, y=self.width, z=self.height),
        )

    def to_world(self, point: Vector3) -> Vector3:
        """Where a point given in the greenhouse's frame lies in the world."""
        return self.origin.apply(point)

    def surfaces(self) -> list[Surface]:
        """The floor and the four walls, in the greenhouse's frame. The walls
        rise from the floor's edges to the envelope's height; the roof comes
        with P01.3."""
        length, width, height = self.length, self.width, self.height

        def wall(surface_id: str, centre: Vector3, facing: Quaternion, size: Plane) -> Surface:
            return Surface(
                surface_id=surface_id,
                category=SurfaceCategory.WALL,
                transform=Transform(position=centre, rotation=facing),
                shape=size,
            )

        floor = Surface(
            surface_id="floor",
            category=SurfaceCategory.FLOOR,
            transform=Transform(position=Vector3(x=length / 2, y=width / 2, z=0.0)),
            shape=Plane(size_x=length, size_y=width),
        )
        # A side wall's plane keeps x along the length and turns y upright; an
        # end wall's turns x upright and keeps y across the width.
        side = Plane(size_x=length, size_y=height)
        end = Plane(size_x=height, size_y=width)
        return [
            floor,
            wall(
                "side_wall_right", Vector3(x=length / 2, y=0.0, z=height / 2), _FACING_PLUS_Y, side
            ),
            wall(
                "side_wall_left",
                Vector3(x=length / 2, y=width, z=height / 2),
                _FACING_MINUS_Y,
                side,
            ),
            wall("end_wall_front", Vector3(x=0.0, y=width / 2, z=height / 2), _FACING_PLUS_X, end),
            wall(
                "end_wall_back", Vector3(x=length, y=width / 2, z=height / 2), _FACING_MINUS_X, end
            ),
        ]

    def surfaces_in_world(self) -> list[Surface]:
        """The same surfaces, placed in the world by the greenhouse's origin."""
        return [
            surface.model_copy(update={"transform": self.origin.after(surface.transform)})
            for surface in self.surfaces()
        ]
