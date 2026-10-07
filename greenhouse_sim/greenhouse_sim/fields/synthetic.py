"""A synthetic field, made to check the field format.

Its values are simple functions of position, so its value anywhere is known
exactly. It is a shear: the air moves along the greenhouse's length, faster
with height, and warms with height and along the length. Trilinear
interpolation reproduces such linear functions exactly between the cells'
centres.
"""

from typing import Final

import numpy as np

from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import VECTOR_COMPONENTS, EnvironmentField, FieldGrid
from greenhouse_sim.world.geometry import Vector3

# The air moves along +x this much faster for every metre of height, in
# (m/s)/m, from still at the floor.
SHEAR_PER_M: Final = 0.25
# The air is this warm at the floor's front end, and warms this much for
# every metre up and along the length.
FLOOR_TEMPERATURE_C: Final = 18.0
WARMING_UP_C_PER_M: Final = 1.2
WARMING_ALONG_C_PER_M: Final = 0.1


def shear_velocity(point: Vector3) -> Vector3:
    """The shear's velocity at a point."""
    return Vector3(x=SHEAR_PER_M * point.z, y=0.0, z=0.0)


def shear_temperature(point: Vector3) -> float:
    """The shear's temperature at a point."""
    return FLOOR_TEMPERATURE_C + WARMING_UP_C_PER_M * point.z + WARMING_ALONG_C_PER_M * point.x


def shear_field(field_id: str, grid: FieldGrid) -> EnvironmentField:
    """The shear over a grid."""
    xs, ys, zs = grid.centres()
    z, _, x = np.meshgrid(zs, ys, xs, indexing="ij")
    velocity = np.zeros((*z.shape, VECTOR_COMPONENTS))
    velocity[..., 0] = SHEAR_PER_M * z
    temperature = FLOOR_TEMPERATURE_C + WARMING_UP_C_PER_M * z + WARMING_ALONG_C_PER_M * x
    return EnvironmentField(
        field_id=field_id,
        source="synthetic:shear",
        grid=grid,
        time_s=0.0,
        channels={AirQuantity.VELOCITY: velocity, AirQuantity.TEMPERATURE: temperature},
    )
