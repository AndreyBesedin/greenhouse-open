"""Fixed objects inside the greenhouse: what they are, what they are made
of, and what they stand in the way of.

A fixture is one solid piece of the greenhouse's layout, such as a crop
gutter, a heating pipe or a path, placed in the greenhouse's frame (decision
0016) and shaped by one of the world's shapes. It carries a kind (what it
is), a material, and what it obstructs: movement, airflow or light. Robots,
airflow and radiation each collect their obstacles by what they obstruct,
not by their kind, so a new kind of fixture needs no change to them.

Fixtures are generated from primitives: a box, an upright cylinder, a pipe
between two points, a rail of two tubes, an open tray along a line, and a
walkway on the floor. Each primitive is a description, with an identifier,
its dimensions, a kind, a material and what it obstructs; the kind brings a
material and obstructions of its own unless the description says otherwise.
"""

import math
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

from greenhouse_sim.world.geometry import Box, Cylinder, Point2, Quaternion, Transform, Vector3
from greenhouse_sim.world.zones import Strip

# A walkway is drawn as a slab this thick on the floor: a path poured a little
# above it, which keeps the two apart for every viewer.
WALKWAY_THICKNESS_M: Final = 0.02

_UP: Final = Vector3(x=0.0, y=0.0, z=1.0)


class FixtureKind(StrEnum):
    """What a fixture is, for every consumer of its geometry."""

    # A trough the crop grows in, on stands or hung from the structure.
    CROP_GUTTER = "crop_gutter"
    # A bench or table that plants stand on, in pots or trays.
    BENCH = "bench"
    # Substrate the crop roots in, such as a stone wool or coir slab.
    SLAB = "slab"
    # A path on the floor, kept clear for people, trolleys and robots.
    WALKWAY = "walkway"
    # A rail that trolleys and robots run on.
    RAIL = "rail"
    # A pipe, such as a heating pipe.
    PIPE = "pipe"
    # Anything else in the way: a column, a tank, a cabinet.
    OBSTACLE = "obstacle"


class Material(StrEnum):
    """What a fixture, or a part of the envelope, is made of."""

    STEEL = "steel"
    ALUMINIUM = "aluminium"
    PLASTIC = "plastic"
    CONCRETE = "concrete"
    # A growing medium, such as stone wool or coir.
    SUBSTRATE = "substrate"


METALS: Final = frozenset({Material.STEEL, Material.ALUMINIUM})


class Obstruction(StrEnum):
    """What a fixture stands in the way of."""

    # Robots, trolleys and people cannot pass through it.
    MOVEMENT = "movement"
    # Air cannot flow through it.
    AIRFLOW = "airflow"
    # It casts a shadow.
    LIGHT = "light"


EVERYTHING: Final = frozenset(Obstruction)

# What each kind is made of, unless its description says otherwise.
DEFAULT_MATERIALS: Final = {
    FixtureKind.CROP_GUTTER: Material.STEEL,
    FixtureKind.BENCH: Material.ALUMINIUM,
    FixtureKind.SLAB: Material.SUBSTRATE,
    FixtureKind.WALKWAY: Material.CONCRETE,
    FixtureKind.RAIL: Material.STEEL,
    FixtureKind.PIPE: Material.STEEL,
    FixtureKind.OBSTACLE: Material.STEEL,
}
# What each kind obstructs, unless its description says otherwise. A walkway
# is walked on, and obstructs nothing. A pipe or rail is too thin to hold
# back the air around it, but it casts a shadow and cannot be driven through.
DEFAULT_OBSTRUCTIONS: Final = {
    FixtureKind.CROP_GUTTER: EVERYTHING,
    FixtureKind.BENCH: EVERYTHING,
    FixtureKind.SLAB: EVERYTHING,
    FixtureKind.WALKWAY: frozenset[Obstruction](),
    FixtureKind.RAIL: frozenset({Obstruction.MOVEMENT, Obstruction.LIGHT}),
    FixtureKind.PIPE: frozenset({Obstruction.MOVEMENT, Obstruction.LIGHT}),
    FixtureKind.OBSTACLE: EVERYTHING,
}


class Fixture(BaseModel):
    """One fixed object, placed in the greenhouse's frame."""

    model_config = ConfigDict(frozen=True)

    fixture_id: str
    kind: FixtureKind
    transform: Transform
    shape: Box | Cylinder
    material: Material
    obstructs: frozenset[Obstruction]

    def corners(self) -> list[Vector3]:
        """The corners of the box around the shape in its own frame, placed in
        the greenhouse's frame: for a cylinder, the box around it."""
        shape = self.shape
        if isinstance(shape, Box):
            half_x, half_y, height = shape.size_x / 2, shape.size_y / 2, shape.size_z
        else:
            half_x = half_y = shape.radius
            height = shape.height
        return [
            self.transform.apply(Vector3(x=x, y=y, z=z))
            for x in (-half_x, half_x)
            for y in (-half_y, half_y)
            for z in (0.0, height)
        ]

    def bounds(self) -> tuple[Vector3, Vector3]:
        """The world-aligned box around the fixture, in the greenhouse's frame."""
        xs, ys, zs = zip(*((c.x, c.y, c.z) for c in self.corners()), strict=True)
        return (
            Vector3(x=min(xs), y=min(ys), z=min(zs)),
            Vector3(x=max(xs), y=max(ys), z=max(zs)),
        )


def _length(vector: Vector3) -> float:
    return math.hypot(vector.x, vector.y, vector.z)


def _between(start: Vector3, end: Vector3) -> tuple[Vector3, float]:
    """The unit direction from `start` to `end`, and the distance."""
    along = Vector3(x=end.x - start.x, y=end.y - start.y, z=end.z - start.z)
    length = _length(along)
    return Vector3(x=along.x / length, y=along.y / length, z=along.z / length), length


def _level_across(direction: Vector3) -> Vector3:
    """The level unit vector at right angles to `direction`, to its left as
    seen looking along it from above; for an upright direction, +y."""
    across = _UP.cross(direction)
    length = _length(across)
    if length == 0.0:
        return Vector3(x=0.0, y=1.0, z=0.0)
    return Vector3(x=across.x / length, y=across.y / length, z=across.z / length)


def _offset(point: Vector3, direction: Vector3, distance: float) -> Vector3:
    return Vector3(
        x=point.x + direction.x * distance,
        y=point.y + direction.y * distance,
        z=point.z + direction.z * distance,
    )


def _not_a_point(start: Vector3, end: Vector3) -> None:
    if start == end:
        raise ValueError("its start and end are the same point")


def _laid_between(start: Vector3, end: Vector3) -> tuple[Transform, float]:
    """A frame at the middle of a line, its x running along the line, its y
    level across it and its z up from both, and the line's length: a box
    standing in it lies along the line."""
    direction, length = _between(start, end)
    middle = Vector3(x=(start.x + end.x) / 2, y=(start.y + end.y) / 2, z=(start.z + end.z) / 2)
    rotation = Quaternion.from_axes(direction, _level_across(direction))
    return Transform(position=middle, rotation=rotation), length


def _pointing_between(start: Vector3, end: Vector3) -> tuple[Transform, float]:
    """A frame at `start` whose z runs to `end`, and the distance: a cylinder
    standing in it runs from one to the other."""
    direction, length = _between(start, end)
    # At right angles to the direction, so the frame's z is the direction.
    x_axis = _level_across(direction).cross(direction)
    return Transform(
        position=start, rotation=Quaternion.from_axes(x_axis, direction.cross(x_axis))
    ), length


class _Primitive(BaseModel):
    """What every primitive's description holds: its identifier, its kind,
    and, unless its kind's defaults do, its material and obstructions."""

    model_config = ConfigDict(frozen=True)

    fixture_id: str
    material: Material | None = None
    obstructs: list[Obstruction] | None = None

    def _fixture(
        self, fixture_id: str, kind: FixtureKind, transform: Transform, shape: Box | Cylinder
    ) -> Fixture:
        return Fixture(
            fixture_id=fixture_id,
            kind=kind,
            transform=transform,
            shape=shape,
            material=self.material or DEFAULT_MATERIALS[kind],
            obstructs=(
                DEFAULT_OBSTRUCTIONS[kind] if self.obstructs is None else frozenset(self.obstructs)
            ),
        )


class BoxPrimitive(_Primitive):
    """A box standing on the floor or anything else: its base centred on
    `base`, turned about the vertical by `heading` radians from the
    greenhouse's x."""

    primitive: Literal["box"] = "box"
    kind: FixtureKind = FixtureKind.OBSTACLE
    base: Vector3
    size_x: PositiveFloat
    size_y: PositiveFloat
    size_z: PositiveFloat
    heading: float = 0.0

    def fixtures(self) -> list[Fixture]:
        return [
            self._fixture(
                self.fixture_id,
                self.kind,
                Transform(position=self.base, rotation=Quaternion.about(_UP, self.heading)),
                Box(size_x=self.size_x, size_y=self.size_y, size_z=self.size_z),
            )
        ]


class CylinderPrimitive(_Primitive):
    """An upright cylinder, its base centred on `base`."""

    primitive: Literal["cylinder"] = "cylinder"
    kind: FixtureKind = FixtureKind.OBSTACLE
    base: Vector3
    radius: PositiveFloat
    height: PositiveFloat

    def fixtures(self) -> list[Fixture]:
        return [
            self._fixture(
                self.fixture_id,
                self.kind,
                Transform(position=self.base),
                Cylinder(radius=self.radius, height=self.height),
            )
        ]


class PipePrimitive(_Primitive):
    """A straight pipe, its axis from `start` to `end`."""

    primitive: Literal["pipe"] = "pipe"
    kind: FixtureKind = FixtureKind.PIPE
    start: Vector3
    end: Vector3
    radius: PositiveFloat

    @model_validator(mode="after")
    def _has_a_length(self) -> Self:
        _not_a_point(self.start, self.end)
        return self

    def fixtures(self) -> list[Fixture]:
        transform, length = _pointing_between(self.start, self.end)
        return [
            self._fixture(
                self.fixture_id,
                self.kind,
                transform,
                Cylinder(radius=self.radius, height=length),
            )
        ]


class RailPrimitive(_Primitive):
    """A rail of two parallel tubes, `gauge` apart from axis to axis, either
    side of its centre line from `start` to `end`. Its tubes are
    `<fixture_id>_right` and `<fixture_id>_left`, as seen looking along it."""

    primitive: Literal["rail"] = "rail"
    kind: FixtureKind = FixtureKind.RAIL
    start: Vector3
    end: Vector3
    gauge: PositiveFloat
    tube_radius: PositiveFloat

    @model_validator(mode="after")
    def _has_a_length_and_room(self) -> Self:
        _not_a_point(self.start, self.end)
        if self.gauge <= 2 * self.tube_radius:
            raise ValueError(f"{self.fixture_id}'s tubes overlap: its gauge is too narrow")
        return self

    def fixtures(self) -> list[Fixture]:
        direction, _ = _between(self.start, self.end)
        across = _level_across(direction)
        tubes = []
        for side, sign in (("right", -1), ("left", 1)):
            start = _offset(self.start, across, sign * self.gauge / 2)
            end = _offset(self.end, across, sign * self.gauge / 2)
            transform, length = _pointing_between(start, end)
            tubes.append(
                self._fixture(
                    f"{self.fixture_id}_{side}",
                    self.kind,
                    transform,
                    Cylinder(radius=self.tube_radius, height=length),
                )
            )
        return tubes


class TrayPrimitive(_Primitive):
    """An open tray, such as a crop gutter: `width` across and `depth` deep,
    its bottom's centre line from `start` to `end`. It may slope, as gutters
    do to drain; it stays level across."""

    primitive: Literal["tray"] = "tray"
    kind: FixtureKind = FixtureKind.CROP_GUTTER
    start: Vector3
    end: Vector3
    width: PositiveFloat
    depth: PositiveFloat

    @model_validator(mode="after")
    def _has_a_length(self) -> Self:
        _not_a_point(self.start, self.end)
        return self

    def fixtures(self) -> list[Fixture]:
        transform, length = _laid_between(self.start, self.end)
        return [
            self._fixture(
                self.fixture_id,
                self.kind,
                transform,
                Box(size_x=length, size_y=self.width, size_z=self.depth),
            )
        ]


class WalkwayPrimitive(_Primitive):
    """A path on the floor, `width` wide, its centre line from `start` to
    `end`."""

    primitive: Literal["walkway"] = "walkway"
    kind: FixtureKind = FixtureKind.WALKWAY
    start: Point2
    end: Point2
    width: PositiveFloat

    @model_validator(mode="after")
    def _has_a_length(self) -> Self:
        _not_a_point(*self._ends())
        return self

    def _ends(self) -> tuple[Vector3, Vector3]:
        return (
            Vector3(x=self.start.x, y=self.start.y, z=0.0),
            Vector3(x=self.end.x, y=self.end.y, z=0.0),
        )

    @property
    def area(self) -> Strip:
        """The floor it covers."""
        return Strip(start=self.start, end=self.end, width=self.width)

    def fixtures(self) -> list[Fixture]:
        transform, length = _laid_between(*self._ends())
        return [
            self._fixture(
                self.fixture_id,
                self.kind,
                transform,
                Box(size_x=length, size_y=self.width, size_z=WALKWAY_THICKNESS_M),
            )
        ]


type Primitive = Annotated[
    BoxPrimitive
    | CylinderPrimitive
    | PipePrimitive
    | RailPrimitive
    | TrayPrimitive
    | WalkwayPrimitive,
    Field(discriminator="primitive"),
]
