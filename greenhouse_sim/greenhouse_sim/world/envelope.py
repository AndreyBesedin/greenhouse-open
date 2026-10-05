"""The greenhouse's envelope: where the greenhouse stands, and the space it encloses.

The greenhouse has a frame of its own (decision 0016). Its origin is a corner of
the floor; x runs along the greenhouse's length, y across its width, and z up,
so the greenhouse fills the positive octant of its frame. `origin` places that
frame in the world, by default at the world's origin, unrotated. Everything the
envelope describes is given in the greenhouse's frame, and `to_world` places it.

The envelope is a description, not geometry: viewers, and later physics and
airflow, build their geometry from it, so a scenario, or later an editor,
changes the greenhouse by changing this description. P01 grows it from the
enclosed space to the floor, walls, roof, bays and openings.
"""

from pydantic import BaseModel, ConfigDict, PositiveFloat

from greenhouse_sim.world.geometry import Transform, Vector3

# Where a greenhouse stands unless a scenario says otherwise: its floor corner
# at the world's origin, its axes along the world's.
AT_WORLD_ORIGIN = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))


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
