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

What a piece does to the air is its capabilities
(`greenhouse_sim.world.capabilities`): a fan moves air, a heater heats, a
dehumidifier dries and gives off heat. The climate, its loops and the heat
log read those, never the piece's kind (P14.5).

**A kind of equipment is registered** (`register_equipment`, decision
0055): a model of a piece, `EquipmentPiece`'s, named by its `kind`, which
says where it stands, its shape and body, its rated values and its
capabilities. A layout's equipment (`Equipment`) is read by the kind each
piece names, among those registered when it is read, so that a kind is a
module and its registration, the packaged ones and another package's
alike; a kind not registered is refused, naming those that are. The
published schema lists the kinds registered when it is written.
"""

import math
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    PlainSerializer,
    PlainValidator,
    PositiveFloat,
    TypeAdapter,
    ValidationError,
)
from pydantic.json_schema import JsonSchemaValue

from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.domain.layout import FixtureKind, Material, Obstruction
from greenhouse_sim.world.capabilities import (
    Capability,
    Device,
    Dries,
    Heats,
    MovesAir,
    Outlet,
    WasteHeat,
)
from greenhouse_sim.world.fixtures import Fixture
from greenhouse_sim.world.geometry import Box, Cylinder, Quaternion, Shape, Transform, Vector3
from greenhouse_sim.world.identifiers import ItemId

# A fan's housing, along its axis, in metres.
FAN_DEPTH_M: Final = 0.3
_UP: Final = Vector3(x=0.0, y=0.0, z=1.0)
_ACROSS: Final = Vector3(x=0.0, y=1.0, z=0.0)
# What a heater's or dehumidifier's body is in the way of; a fan, nothing.
_BODY_OBSTRUCTS: Final = frozenset({Obstruction.MOVEMENT, Obstruction.AIRFLOW})
_HANGING_OBSTRUCTS: Final[frozenset[Obstruction]] = frozenset()


class EquipmentPiece(BaseModel):
    """A piece of climate equipment of a kind, `kind`, registered: what every
    kind says of a piece, which the climate, the scene, moves and the
    builder ask of it whatever its kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actuator_id: ItemId
    # Which way it faces, a turn about the vertical from the greenhouse's x;
    # a fan blows that way.
    heading: float = 0.0
    if TYPE_CHECKING:
        # Its kind's name, as a layout writes it: each kind's own field, which
        # it declares after its own others, as its pieces are written.
        kind: str

    def facing(self) -> Vector3:
        """The unit vector it faces along, level."""
        return Vector3(x=math.cos(self.heading), y=math.sin(self.heading), z=0.0)

    def transform(self) -> Transform:
        """Its body's frame, placed in the greenhouse."""
        raise NotImplementedError

    def shape(self) -> Shape:
        """Its body's shape, in its frame."""
        raise NotImplementedError

    def fixture(self) -> Fixture:
        """Its body as a fixture, with what it is in the way of."""
        raise NotImplementedError

    def rated(self) -> dict[str, float]:
        """Its rated values, what it does at full level, by its own names."""
        raise NotImplementedError

    def capabilities(self) -> tuple[Capability, ...]:
        """What it does to the air, at full level."""
        raise NotImplementedError

    def anchor(self) -> Vector3:
        """Where it is placed."""
        raise NotImplementedError

    def displaced(self, by: Vector3) -> Self:
        """It placed `by` further."""
        raise NotImplementedError


def _plus(point: Vector3, by: Vector3, scale: float = 1.0) -> Vector3:
    return Vector3(x=point.x + by.x * scale, y=point.y + by.y * scale, z=point.z + by.z * scale)


class Fan(EquipmentPiece):
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

    def capabilities(self) -> tuple[Capability, ...]:
        """It moves air: its flow blown from its rotor, along its heading."""
        outlet = Outlet(centre=self.position, axis=self.facing(), diameter_m=self.diameter_m)
        return (MovesAir(outlet=outlet, flow_m3_s=self.flow_m3_s),)

    def anchor(self) -> Vector3:
        """Where it is placed: its rotor's centre."""
        return self.position

    def displaced(self, by: Vector3) -> Self:
        """It placed `by` further."""
        return self.model_copy(update={"position": _plus(self.position, by)})


class Unit(EquipmentPiece):
    """A unit standing on the floor or anything else: a box, its base centred
    on `base`, an obstacle in the way of air and robots. A kind of equipment
    that stands so is one."""

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

    def anchor(self) -> Vector3:
        """Where it is placed: its base's centre."""
        return self.base

    def displaced(self, by: Vector3) -> Self:
        """It placed `by` further."""
        return self.model_copy(update={"base": _plus(self.base, by)})


class Heater(Unit):
    """A unit heater: its rated power, all of it given to the air as heat."""

    kind: Literal[ActuatorKind.HEATER] = ActuatorKind.HEATER
    power_w: PositiveFloat

    def rated(self) -> dict[str, float]:
        return {"power_w": self.power_w}

    def capabilities(self) -> tuple[Capability, ...]:
        """It heats: its power blown out of the middle of its front, along
        its heading, from an outlet as wide as its front is high or wide,
        whichever is less."""
        axis = self.facing()
        front = _plus(self.base, axis, self.size_x / 2)
        outlet = Outlet(
            centre=Vector3(x=front.x, y=front.y, z=self.base.z + self.size_z / 2),
            axis=axis,
            diameter_m=min(self.size_y, self.size_z),
        )
        return (Heats(power_w=self.power_w, outlet=outlet),)


class Dehumidifier(Unit):
    """A dehumidifier: the water it takes out of the air at full power, and
    the heat it gives the air while it does."""

    kind: Literal[ActuatorKind.DEHUMIDIFIER] = ActuatorKind.DEHUMIDIFIER
    removal_kg_h: PositiveFloat
    heat_w: PositiveFloat

    def rated(self) -> dict[str, float]:
        return {"removal_kg_h": self.removal_kg_h, "heat_w": self.heat_w}

    def capabilities(self) -> tuple[Capability, ...]:
        """It dries the air around its body, and gives off heat as it does."""
        return (Dries(removal_kg_h=self.removal_kg_h), WasteHeat(heat_w=self.heat_w))


# Each kind of equipment registered, by its name.
EQUIPMENT_KINDS: Final[dict[str, type[EquipmentPiece]]] = {}


def register_equipment[Kind: type[EquipmentPiece]](kind: Kind) -> Kind:
    """Register a kind of equipment, by the name its `kind` field gives it, so
    that a layout reads a piece of it: refused if it names none, or another
    kind has its name."""
    model: type[EquipmentPiece] = kind
    field = model.model_fields.get("kind")
    name = None if field is None else field.default
    if not isinstance(name, str) or not name:
        raise ValueError(f"{kind.__name__} names no kind: its kind field has no default")
    known = EQUIPMENT_KINDS.get(name)
    if known is not None and known is not kind:
        raise ValueError(f"the kind {name!r} is {known.__name__}'s, not {kind.__name__}'s")
    EQUIPMENT_KINDS[str(name)] = kind
    return kind


for _packaged in (Fan, Heater, Dehumidifier):
    register_equipment(_packaged)


class _AsRegistered:
    """The JSON Schema of a layout's piece of equipment: one of the kinds
    registered when it is written, told apart by its `kind`."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _schema: Any, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        kinds = tuple(EQUIPMENT_KINDS.values())
        if len(kinds) == 1:
            return handler(TypeAdapter(kinds[0]).core_schema)
        # The union of the kinds registered now, which no annotation names.
        annotated: Any = Annotated
        union = annotated[_union(kinds), Field(discriminator="kind")]
        return handler(TypeAdapter[Any](union).core_schema)


def _union(kinds: tuple[type[EquipmentPiece], ...]) -> Any:
    union: Any = kinds[0]
    for kind in kinds[1:]:
        union = union | kind
    return union


def _read(given: Any) -> EquipmentPiece:
    if isinstance(given, EquipmentPiece):
        named = given.kind
        if EQUIPMENT_KINDS.get(named) is type(given):
            return given
        kinds = ", ".join(EQUIPMENT_KINDS)
        raise ValueError(f"no kind of equipment {named!r} for {type(given).__name__}: the kinds are {kinds}")
    named = given.get("kind") if isinstance(given, dict) else None
    kind = EQUIPMENT_KINDS.get(named) if isinstance(named, str) else None
    if kind is None:
        kinds = ", ".join(EQUIPMENT_KINDS)
        raise ValueError(f"no kind of equipment {named!r}: the kinds are {kinds}")
    try:
        return kind.model_validate(given)
    except ValidationError as error:
        # Its kind's own reasons, each where it found it.
        raise ValueError(
            "; ".join(
                f"{'.'.join(str(part) for part in found['loc'])}: {found['msg']}"
                for found in error.errors()
            )
        ) from None


# A piece of equipment of any kind registered, as a layout holds it: read by
# the kind it names, and written as its own kind writes it.
type Equipment = Annotated[
    EquipmentPiece,
    PlainValidator(_read),
    PlainSerializer(lambda piece: piece, return_type=Any),
    _AsRegistered,
]


def purpose(piece: Device) -> Capability | None:
    """What a piece of equipment is for: the first of its capabilities that
    is not the heat it gives off as it works; none if that is all it does."""
    return next((each for each in piece.capabilities() if not isinstance(each, WasteHeat)), None)


def can(piece: Device, capability: type[Capability]) -> bool:
    """Whether a piece of equipment can do what `capability` says: move air,
    heat or dry (`greenhouse_sim.world.capabilities`)."""
    return any(isinstance(each, capability) for each in piece.capabilities())
