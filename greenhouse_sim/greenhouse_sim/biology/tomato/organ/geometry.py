"""A plant's geometry, derived from its organs' state.

Every shape is placed in the plant's own frame: its base at the origin, its
stem rising along +z, in metres. Each shape is one part of one organ and says
which; an organ may be drawn with several shapes. Nothing here is stored:
the geometry follows the organs, so the drawn plant is always the simulated
one.

The stem is its internodes stacked up from the base, each a cylinder as long
and as thick as its internode. A leaf is a tomato's compound leaf, coarsely:
a petiole from its node, then a rachis bearing pairs of leaflets and ending
in a terminal leaflet, together as long as the leaf. It rises from its node
and bends down along its length, the more the longer it has grown, and
successive leaves turn about the stem by the golden angle. A truss is a stick
hanging opposite its phytomer's leaf, as long as its flowers need, each
flower at its place along it: a bud as a small sphere, an open flower a
larger one, a set flower as its fruit, of its diameter. An aborted flower or
fruit has dropped, and is not drawn.

How a plant's organs are proportioned and held comes from its crop's form
(`PlantForm`), the parameters its geometry is generated from, as the plant's
traits change it (`plant_form`): how steeply it holds its leaves, how far they
droop, and where its first leaf points about its stem.
"""

import math
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt

from greenhouse_sim.biology.tomato.organ.topology import (
    FlowerStage,
    FruitStage,
    Leaf,
    OrganKind,
    Plant,
    PlantTraits,
)
from greenhouse_sim.world.geometry import (
    Cylinder,
    Ellipsoid,
    Quaternion,
    Sphere,
    Transform,
    Vector3,
)

METRES_PER_CM: Final = 0.01
METRES_PER_MM: Final = 0.001
# Successive leaves turn about the stem by the golden angle.
GOLDEN_ANGLE_RAD: Final = math.pi * (3 - math.sqrt(5))
# Trusses hang below the horizontal, on the side opposite their phytomer's leaf.
TRUSS_ELEVATION_RAD: Final = math.radians(-20)
TRUSS_STICK_RADIUS_M: Final = 0.003
# Flowers sit this far apart along their truss, the first this far from the
# stem.
FLOWER_SPACING_M: Final = 0.02
BUD_RADIUS_M: Final = 0.004
FLOWER_RADIUS_M: Final = 0.007
# A leaflet is drawn as a flat ellipsoid this thick.
LEAFLET_THICKNESS_M: Final = 0.002

# The fruits still on the plant, and so drawn.
ATTACHED_FRUIT: Final = frozenset({FruitStage.ATTACHED})

_UP: Final = Vector3(x=0.0, y=0.0, z=1.0)

type Fraction = Annotated[float, Field(gt=0, lt=1)]
type Angle = Annotated[float, Field(ge=0, le=math.pi / 2)]


class PlantForm(BaseModel):
    """How a plant's organs are proportioned and held: the parameters its
    geometry is generated from, with a tomato's typical values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Pairs of lateral leaflets on a leaf, besides its terminal leaflet.
    leaflet_pairs: PositiveInt = 3
    # The terminal leaflet's share of the leaf's length.
    terminal_leaflet_fraction: Fraction = 0.3
    # The petiole's share of the rest, before the first pair of leaflets.
    petiole_fraction: Fraction = 0.25
    # The pair nearest the stem, as a fraction of the terminal leaflet's
    # length; pairs grow towards the tip.
    basal_leaflet_scale: Annotated[float, Field(gt=0, le=1)] = 0.6
    # A leaflet's width, as a fraction of its length.
    leaflet_aspect: Fraction = 0.5
    # Lateral leaflets spread from the rachis at this angle.
    leaflet_angle_rad: Angle = math.radians(55)
    # A leaf rises from its node at this angle above the horizontal.
    leaf_insertion_rad: Angle = math.radians(45)
    # A full-grown leaf bends down this far from its base to its tip; a
    # shorter one in proportion to its length.
    full_leaf_droop_rad: Angle = math.radians(75)
    full_leaf_length_cm: PositiveFloat = 45.0
    # The petiole and rachis's diameter, as a fraction of the leaf's length.
    rachis_diameter_fraction: Fraction = 0.012


def plant_form(form: PlantForm, traits: PlantTraits) -> PlantForm:
    """The crop's form as a plant of these traits holds its leaves."""
    return form.model_copy(
        update={
            "leaf_insertion_rad": form.leaf_insertion_rad * traits.leaf_insertion_scale,
            "full_leaf_droop_rad": form.full_leaf_droop_rad * traits.leaf_droop_scale,
        }
    )


class OrganShape(BaseModel):
    """One shape of one organ, in the plant's frame."""

    model_config = ConfigDict(frozen=True)

    # Unique within the plant: the organ's identifier, or that and its part.
    shape_id: str
    organ_id: str
    kind: OrganKind
    # Which part of the organ: `internode`, `petiole`, `rachis`, `leaflet`,
    # `truss`, `flower` or `fruit`.
    part: str
    transform: Transform
    shape: Cylinder | Sphere | Ellipsoid


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


def _blend(first: Vector3, second: Vector3, angle: float) -> Vector3:
    """The unit vector `angle` from `first` towards `second`, which is at
    right angles to it."""
    return Vector3(
        x=first.x * math.cos(angle) + second.x * math.sin(angle),
        y=first.y * math.cos(angle) + second.y * math.sin(angle),
        z=first.z * math.cos(angle) + second.z * math.sin(angle),
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


def _laid(centre: Vector3, along: Vector3, normal: Vector3) -> Transform:
    """A frame at `centre` whose x runs along the unit `along` and whose z is
    the unit `normal`, at right angles to it: an ellipsoid in it lies flat
    across `normal`."""
    return Transform(position=centre, rotation=Quaternion.from_axes(along, normal.cross(along)))


def leaf_shapes(leaf: Leaf, node: Vector3, azimuth: float, form: PlantForm) -> list[OrganShape]:
    """A leaf's petiole, rachis and leaflets, from its node at this azimuth.

    The petiole and the rachis's segments are straight, each bent further down
    than the last, with a pair of leaflets where one segment meets the next
    and the terminal leaflet at the tip. The leaflets lie in the leaf's plane,
    which holds the rachis and the horizontal across it.
    """
    length = leaf.length_cm * METRES_PER_CM
    terminal = length * form.terminal_leaflet_fraction
    rachis = length - terminal
    petiole = rachis * form.petiole_fraction
    pairs = form.leaflet_pairs
    between = (rachis - petiole) / pairs
    droop = form.full_leaf_droop_rad * min(1.0, leaf.length_cm / form.full_leaf_length_cm)
    # Bent a step down at each pair, and once more for the terminal leaflet.
    step = droop / (pairs + 1)
    radius = length * form.rachis_diameter_fraction / 2
    # To the left of the leaf, seen from its node.
    left = Vector3(x=-math.sin(azimuth), y=math.cos(azimuth), z=0.0)

    def part(name: str, kind: str, transform: Transform, shape: Cylinder | Ellipsoid) -> OrganShape:
        return OrganShape(
            shape_id=f"{leaf.leaf_id}_{name}",
            organ_id=leaf.leaf_id,
            kind=OrganKind.LEAF,
            part=kind,
            transform=transform,
            shape=shape,
        )

    def leaflet(
        name: str, base: Vector3, toward: Vector3, normal: Vector3, size: float
    ) -> OrganShape:
        return part(
            name,
            "leaflet",
            _laid(_along(base, toward, size / 2), toward, normal),
            Ellipsoid(size_x=size, size_y=size * form.leaflet_aspect, size_z=LEAFLET_THICKNESS_M),
        )

    shapes: list[OrganShape] = []
    start = node
    for segment in range(pairs + 1):
        direction = _direction(azimuth, form.leaf_insertion_rad - step * segment)
        reach = petiole if segment == 0 else between
        kind = "petiole" if segment == 0 else "rachis"
        name = kind if segment == 0 else f"rachis{segment}"
        cylinder = Cylinder(radius=radius, height=reach)
        shapes.append(part(name, kind, _pointing(start, direction), cylinder))
        start = _along(start, direction, reach)
        normal = direction.cross(left)
        if segment < pairs:
            pair = segment + 1
            size = terminal * (
                form.basal_leaflet_scale + (1 - form.basal_leaflet_scale) * segment / pairs
            )
            for side, sign in (("left", 1.0), ("right", -1.0)):
                outward = Vector3(x=left.x * sign, y=left.y * sign, z=0.0)
                toward = _blend(direction, outward, form.leaflet_angle_rad)
                shapes.append(leaflet(f"leaflet{pair}_{side}", start, toward, normal, size))
    tip = _direction(azimuth, form.leaf_insertion_rad - droop)
    shapes.append(leaflet("terminal", start, tip, tip.cross(left), terminal))
    return shapes


def organ_geometry(plant: Plant, form: PlantForm | None = None) -> list[OrganShape]:
    """Every shape of the plant, from the stem's base up, as `form` (by
    default a typical tomato's) proportions its organs and the plant's traits
    change it."""
    form = plant_form(PlantForm() if form is None else form, plant.traits)
    shapes: list[OrganShape] = []
    height = 0.0
    for phytomer in plant.stem.phytomers:
        internode = phytomer.internode
        length = internode.length_cm * METRES_PER_CM
        shapes.append(
            OrganShape(
                shape_id=internode.internode_id,
                organ_id=internode.internode_id,
                kind=OrganKind.INTERNODE,
                part="internode",
                transform=Transform(position=Vector3(x=0.0, y=0.0, z=height)),
                shape=Cylinder(radius=internode.diameter_mm * METRES_PER_MM / 2, height=length),
            )
        )
        height += length
        node = Vector3(x=0.0, y=0.0, z=height)
        azimuth = plant.traits.rotation_rad + (phytomer.rank - 1) * GOLDEN_ANGLE_RAD
        shapes.extend(leaf_shapes(phytomer.leaf, node, azimuth, form))
        if phytomer.truss is None:
            continue
        truss = phytomer.truss
        hanging = _direction(azimuth + math.pi, TRUSS_ELEVATION_RAD)
        shapes.append(
            OrganShape(
                shape_id=truss.truss_id,
                organ_id=truss.truss_id,
                kind=OrganKind.TRUSS,
                part="truss",
                transform=_pointing(node, hanging),
                shape=Cylinder(
                    radius=TRUSS_STICK_RADIUS_M,
                    height=FLOWER_SPACING_M * truss.final_flower_count,
                ),
            )
        )
        for flower in truss.flowers:
            # At its place along the truss, the first nearest the stem.
            centre = _along(node, hanging, FLOWER_SPACING_M * flower.rank)
            fruit = flower.fruit
            if flower.stage in {FlowerStage.BUD, FlowerStage.OPEN}:
                radius = BUD_RADIUS_M if flower.stage == FlowerStage.BUD else FLOWER_RADIUS_M
                shapes.append(
                    OrganShape(
                        shape_id=flower.flower_id,
                        organ_id=flower.flower_id,
                        kind=OrganKind.FLOWER,
                        part="flower",
                        transform=Transform(position=centre),
                        shape=Sphere(radius=radius),
                    )
                )
            elif fruit is not None and fruit.stage in ATTACHED_FRUIT and fruit.diameter_mm > 0:
                shapes.append(
                    OrganShape(
                        shape_id=fruit.fruit_id,
                        organ_id=fruit.fruit_id,
                        kind=OrganKind.FRUIT,
                        part="fruit",
                        transform=Transform(position=centre),
                        shape=Sphere(radius=fruit.diameter_mm * METRES_PER_MM / 2),
                    )
                )
    return shapes
