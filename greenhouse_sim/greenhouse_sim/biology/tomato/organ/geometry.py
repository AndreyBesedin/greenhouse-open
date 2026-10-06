"""A plant's geometry, derived from its organs' state.

Every shape is placed in the plant's own frame: its base at the origin, its
stem rising along +z, in metres. Each shape belongs to one organ and says
which; an organ may be drawn with several shapes. Nothing here is stored:
the geometry follows the organs, so the drawn plant is always the simulated
one.

This is the schematic "stick plant" of P03.1: internodes stacked up the
stem, and each leaf and truss a stick from its node, turning about the stem
by the golden angle from one phytomer to the next. Flowers and fruits are
spheres along their truss. P03.2 replaces the sticks with procedural organs.
"""

import math
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.biology.tomato.organ.topology import OrganKind, Plant
from greenhouse_sim.world.geometry import Cylinder, Quaternion, Sphere, Transform, Vector3

METRES_PER_CM: Final = 0.01
METRES_PER_MM: Final = 0.001
# Successive leaves turn about the stem by the golden angle.
GOLDEN_ANGLE_RAD: Final = math.pi * (3 - math.sqrt(5))
# Leaves rise from their node at this angle above the horizontal; trusses
# hang below it, on the side opposite their phytomer's leaf.
LEAF_ELEVATION_RAD: Final = math.radians(30)
TRUSS_ELEVATION_RAD: Final = math.radians(-20)
LEAF_STICK_RADIUS_M: Final = 0.004
TRUSS_STICK_RADIUS_M: Final = 0.003
TRUSS_LENGTH_M: Final = 0.1
FLOWER_RADIUS_M: Final = 0.006

_UP: Final = Vector3(x=0.0, y=0.0, z=1.0)


class OrganShape(BaseModel):
    """One shape of one organ, in the plant's frame."""

    model_config = ConfigDict(frozen=True)

    # Unique within the plant: the organ's identifier, or that and a part.
    shape_id: str
    organ_id: str
    kind: OrganKind
    transform: Transform
    shape: Cylinder | Sphere


def _direction(azimuth: float, elevation: float) -> Vector3:
    """The unit vector at this azimuth about the stem (from +x) and this
    elevation above the horizontal."""
    return Vector3(
        x=math.cos(elevation) * math.cos(azimuth),
        y=math.cos(elevation) * math.sin(azimuth),
        z=math.sin(elevation),
    )


def _along(start: Vector3, direction: Vector3, distance: float) -> Vector3:
    return Vector3(
        x=start.x + direction.x * distance,
        y=start.y + direction.y * distance,
        z=start.z + direction.z * distance,
    )


def _pointing(start: Vector3, direction: Vector3) -> Transform:
    """A frame at `start` whose z runs along the unit `direction`: a cylinder
    standing in it runs that way."""
    across = _UP.cross(direction)
    length = math.hypot(across.x, across.y, across.z)
    level = (
        Vector3(x=0.0, y=1.0, z=0.0)
        if length == 0.0
        else Vector3(x=across.x / length, y=across.y / length, z=across.z / length)
    )
    x_axis = level.cross(direction)
    return Transform(position=start, rotation=Quaternion.from_axes(x_axis, direction.cross(x_axis)))


def organ_geometry(plant: Plant) -> list[OrganShape]:
    """Every shape of the plant, from the stem's base up."""
    shapes: list[OrganShape] = []
    height = 0.0
    for phytomer in plant.stem.phytomers:
        internode = phytomer.internode
        length = internode.length_cm * METRES_PER_CM
        base = Vector3(x=0.0, y=0.0, z=height)
        shapes.append(
            OrganShape(
                shape_id=internode.internode_id,
                organ_id=internode.internode_id,
                kind=OrganKind.INTERNODE,
                transform=Transform(position=base),
                shape=Cylinder(radius=internode.diameter_mm * METRES_PER_MM / 2, height=length),
            )
        )
        height += length
        node = Vector3(x=0.0, y=0.0, z=height)
        azimuth = phytomer.rank * GOLDEN_ANGLE_RAD
        leaf = phytomer.leaf
        shapes.append(
            OrganShape(
                shape_id=leaf.leaf_id,
                organ_id=leaf.leaf_id,
                kind=OrganKind.LEAF,
                transform=_pointing(node, _direction(azimuth, LEAF_ELEVATION_RAD)),
                shape=Cylinder(radius=LEAF_STICK_RADIUS_M, height=leaf.length_cm * METRES_PER_CM),
            )
        )
        if phytomer.truss is None:
            continue
        truss = phytomer.truss
        hanging = _direction(azimuth + math.pi, TRUSS_ELEVATION_RAD)
        shapes.append(
            OrganShape(
                shape_id=truss.truss_id,
                organ_id=truss.truss_id,
                kind=OrganKind.TRUSS,
                transform=_pointing(node, hanging),
                shape=Cylinder(radius=TRUSS_STICK_RADIUS_M, height=TRUSS_LENGTH_M),
            )
        )
        flowers = len(truss.flowers)
        for flower in truss.flowers:
            # Evenly along the truss, the first nearest the stem.
            centre = _along(node, hanging, TRUSS_LENGTH_M * flower.rank / flowers)
            fruit = flower.fruit
            if fruit is None:
                shapes.append(
                    OrganShape(
                        shape_id=flower.flower_id,
                        organ_id=flower.flower_id,
                        kind=OrganKind.FLOWER,
                        transform=Transform(position=centre),
                        shape=Sphere(radius=FLOWER_RADIUS_M),
                    )
                )
            elif fruit.diameter_mm > 0:
                shapes.append(
                    OrganShape(
                        shape_id=fruit.fruit_id,
                        organ_id=fruit.fruit_id,
                        kind=OrganKind.FRUIT,
                        transform=Transform(position=centre),
                        shape=Sphere(radius=fruit.diameter_mm * METRES_PER_MM / 2),
                    )
                )
    return shapes
