"""A renderable description of the simulated world at one moment.

A `SceneSnapshot` lists entities, each with a stable identifier, a kind a
viewer dispatches on, a transform, a shape, a colour, and a label and
properties for an inspector. It uses the world's geometry conventions
(`greenhouse_sim.world.geometry`) and nothing of any renderer.

The viewer is a tool for looking at the simulation, so a snapshot shows the
simulated truth, as the world does. It is not an observation: decision-making
code works from observations, never from a snapshot.

A snapshot holds a reference axes marker at the origin, the greenhouse's
envelope (its floor, walls and roof, its doors and vents as they stand open,
its gutters, its structural frames, and its bounds: the space it encloses, as
a box), and an upright cylinder per plant, as tall as its visible stem. Until
planting positions become part of the world (P02), plants stand on a
provisional grid built from the scenario's rows and columns.
"""

import math
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import (
    Envelope,
    Gutter,
    Member,
    MemberKind,
    OpeningKind,
    OpeningPanel,
    Surface,
    SurfaceCategory,
)
from greenhouse_sim.world.geometry import (
    Axes,
    Box,
    Cylinder,
    Quaternion,
    Shape,
    Transform,
    Vector3,
)
from greenhouse_sim.world.state import FruitStatus, GreenhouseWorld, PlantWorld

# Bumped when a change to these types would break an existing viewer, as a new
# kind or shape does: a viewer that does not know it refuses the scene.
# 2: the greenhouse's bounds, drawn as a box.
# 3: the greenhouse's floor and walls, in place of the provisional ground.
# 4: its roof, gable end walls as polygons, and gutters.
# 5: its structural frames.
# 6: its doors and vents.
SCHEMA_VERSION: Final = 6
# The JSON Schema dialect Pydantic generates, stated in the published schema.
JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"

# Provisional layout until planting positions are part of the world (P02).
# Plants of one scenario row stand along +x at this pitch, and rows follow one
# another along +y at this spacing.
PLANT_PITCH_M: Final = 0.5
ROW_SPACING_M: Final = 1.6

PLANT_STEM_RADIUS_M: Final = 0.02
AXES_LENGTH_M: Final = 1.0
METRES_PER_CENTIMETRE: Final = 0.01


class Color(BaseModel):
    """An sRGB colour, each channel from 0 to 1."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    r: float = Field(ge=0.0, le=1.0)
    g: float = Field(ge=0.0, le=1.0)
    b: float = Field(ge=0.0, le=1.0)


FLOOR_COLOR: Final = Color(r=0.42, g=0.33, b=0.24)
WALL_COLOR: Final = Color(r=0.74, g=0.86, b=0.92)
ROOF_COLOR: Final = Color(r=0.7, g=0.83, b=0.9)
GUTTER_COLOR: Final = Color(r=0.55, g=0.57, b=0.6)
# A gutter is drawn as a channel of this cross-section, its top at the eaves,
# until gutters have a profile of their own.
GUTTER_WIDTH_M: Final = 0.2
GUTTER_DEPTH_M: Final = 0.15
FRAME_COLOR: Final = Color(r=0.66, g=0.68, b=0.7)
VENT_COLOR: Final = Color(r=0.55, g=0.74, b=0.86)
DOOR_COLOR: Final = Color(r=0.45, g=0.5, b=0.56)
# Structural members are drawn as round bars of these radii, until they have
# profiles of their own.
MEMBER_RADII_M: Final = {MemberKind.POST: 0.05, MemberKind.RAFTER: 0.03}
AXES_COLOR: Final = Color(r=0.5, g=0.5, b=0.5)
PLANT_COLOR: Final = Color(r=0.2, g=0.55, b=0.24)
GREENHOUSE_BOUNDS_COLOR: Final = Color(r=0.62, g=0.78, b=0.88)


class SceneEntityKind(StrEnum):
    # Open ground, as scenes built by a viewer use; a greenhouse has a floor.
    GROUND = "GROUND"
    AXES = "AXES"
    GREENHOUSE_BOUNDS = "GREENHOUSE_BOUNDS"
    FLOOR = "FLOOR"
    WALL = "WALL"
    ROOF = "ROOF"
    GUTTER = "GUTTER"
    FRAME = "FRAME"
    VENT = "VENT"
    DOOR = "DOOR"
    PLANT = "PLANT"


class SceneEntity(BaseModel):
    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    entity_id: str
    kind: SceneEntityKind
    transform: Transform
    shape: Shape
    color: Color
    label: str | None = None
    properties: dict[str, str | int | float | bool] = {}


class SceneSnapshot(BaseModel):
    """One greenhouse at one simulated day, as a viewer draws it. Positions
    and sizes are in metres, in right-handed world axes with z up."""

    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    schema_version: int = SCHEMA_VERSION
    greenhouse_id: str
    simulated_day: int
    entities: list[SceneEntity]


def scene_snapshot(world: GreenhouseWorld, config: ScenarioConfig) -> SceneSnapshot:
    """The scene a viewer draws for `world`: its greenhouse, as
    `greenhouse_scene` draws it, and one entity per plant."""
    columns = max(config.columns, 1)
    greenhouse = greenhouse_scene(world.greenhouse_id, config.envelope, world.simulated_day)
    plants = [
        _plant_entity(plant, _planting_position(index, columns))
        for index, plant in enumerate(world.plants)
    ]
    return greenhouse.model_copy(update={"entities": [*greenhouse.entities, *plants]})


def greenhouse_scene(
    greenhouse_id: str, envelope: Envelope, simulated_day: int = 0
) -> SceneSnapshot:
    """A greenhouse on its own, without a crop: the world's axes, and its
    floor, walls, roof, openings, gutters, frames and bounds."""
    axes = SceneEntity(
        entity_id=f"{greenhouse_id}_axes",
        kind=SceneEntityKind.AXES,
        transform=Transform(position=Vector3(x=0.0, y=0.0, z=0.0)),
        shape=Axes(length=AXES_LENGTH_M),
        color=AXES_COLOR,
        label="world axes",
    )
    return SceneSnapshot(
        greenhouse_id=greenhouse_id,
        simulated_day=simulated_day,
        entities=[
            *_surface_entities(greenhouse_id, envelope),
            *_opening_entities(greenhouse_id, envelope),
            *_gutter_entities(greenhouse_id, envelope),
            *_member_entities(greenhouse_id, envelope),
            axes,
            _bounds_entity(greenhouse_id, envelope),
        ],
    )


_SURFACE_KINDS: Final = {
    SurfaceCategory.FLOOR: (SceneEntityKind.FLOOR, FLOOR_COLOR),
    SurfaceCategory.WALL: (SceneEntityKind.WALL, WALL_COLOR),
    SurfaceCategory.ROOF: (SceneEntityKind.ROOF, ROOF_COLOR),
}


def _surface_entities(greenhouse_id: str, envelope: Envelope) -> list[SceneEntity]:
    """Each surface of the envelope, placed in the world, as an entity of its category."""
    return [_surface_entity(greenhouse_id, surface) for surface in envelope.surfaces_in_world()]


def _surface_entity(greenhouse_id: str, surface: Surface) -> SceneEntity:
    kind, color = _SURFACE_KINDS[surface.category]
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{surface.surface_id}",
        kind=kind,
        transform=surface.transform,
        shape=surface.shape,
        color=color,
        label=surface.surface_id.replace("_", " "),
    )


def _opening_entities(greenhouse_id: str, envelope: Envelope) -> list[SceneEntity]:
    return [_opening_entity(greenhouse_id, envelope, panel) for panel in envelope.opening_panels()]


def _opening_entity(greenhouse_id: str, envelope: Envelope, panel: OpeningPanel) -> SceneEntity:
    """A door or vent's panel as it stands, with how far it is open and the
    aperture it exposes."""
    opening = panel.opening
    is_door = opening.kind == OpeningKind.DOOR
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{opening.opening_id}",
        kind=SceneEntityKind.DOOR if is_door else SceneEntityKind.VENT,
        transform=envelope.origin.after(panel.transform),
        shape=panel.shape,
        color=DOOR_COLOR if is_door else VENT_COLOR,
        label=opening.opening_id.replace("_", " "),
        properties={
            "opening_id": opening.opening_id,
            "opening_kind": opening.kind.value,
            "on_surface": opening.surface_id,
            "open_fraction": opening.opening,
            "aperture_m2": opening.aperture_area(),
        },
    )


def _gutter_entities(greenhouse_id: str, envelope: Envelope) -> list[SceneEntity]:
    return [_gutter_entity(greenhouse_id, envelope, gutter) for gutter in envelope.gutters()]


def _gutter_entity(greenhouse_id: str, envelope: Envelope, gutter: Gutter) -> SceneEntity:
    """A gutter as a channel along its line, its top at the line."""
    along = Vector3(
        x=gutter.end.x - gutter.start.x,
        y=gutter.end.y - gutter.start.y,
        z=gutter.end.z - gutter.start.z,
    )
    length = math.hypot(along.x, along.y, along.z)
    direction = Vector3(x=along.x / length, y=along.y / length, z=along.z / length)
    level = Vector3(x=0.0, y=0.0, z=1.0).cross(direction)
    base_middle = Vector3(
        x=(gutter.start.x + gutter.end.x) / 2,
        y=(gutter.start.y + gutter.end.y) / 2,
        z=(gutter.start.z + gutter.end.z) / 2 - GUTTER_DEPTH_M,
    )
    in_greenhouse = Transform(position=base_middle, rotation=Quaternion.from_axes(direction, level))
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{gutter.gutter_id}",
        kind=SceneEntityKind.GUTTER,
        transform=envelope.origin.after(in_greenhouse),
        shape=Box(size_x=length, size_y=GUTTER_WIDTH_M, size_z=GUTTER_DEPTH_M),
        color=GUTTER_COLOR,
        label=gutter.gutter_id.replace("_", " "),
    )


def _member_entities(greenhouse_id: str, envelope: Envelope) -> list[SceneEntity]:
    return [_member_entity(greenhouse_id, envelope, member) for member in envelope.members()]


def _member_entity(greenhouse_id: str, envelope: Envelope, member: Member) -> SceneEntity:
    """A structural member as a cylinder from its foot to its head. Members lie
    across the length, so the length's direction stays square to each."""
    along = Vector3(
        x=member.end.x - member.start.x,
        y=member.end.y - member.start.y,
        z=member.end.z - member.start.z,
    )
    length = math.hypot(along.x, along.y, along.z)
    direction = Vector3(x=along.x / length, y=along.y / length, z=along.z / length)
    across = Vector3(x=1.0, y=0.0, z=0.0)
    # A cylinder rises along its +z: turn that onto the member's direction.
    in_greenhouse = Transform(
        position=member.start,
        rotation=Quaternion.from_axes(across, direction.cross(across)),
    )
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{member.member_id}",
        kind=SceneEntityKind.FRAME,
        transform=envelope.origin.after(in_greenhouse),
        shape=Cylinder(radius=MEMBER_RADII_M[member.kind], height=length),
        color=FRAME_COLOR,
        label=member.member_id.replace("_", " "),
    )


def _bounds_entity(greenhouse_id: str, envelope: Envelope) -> SceneEntity:
    """The space the envelope encloses, as a box standing on the middle of the floor."""
    middle_of_floor = Vector3(x=envelope.length / 2, y=envelope.width / 2, z=0.0)
    height = envelope.ridge_height
    return SceneEntity(
        entity_id=f"{greenhouse_id}_bounds",
        kind=SceneEntityKind.GREENHOUSE_BOUNDS,
        transform=Transform(
            position=envelope.to_world(middle_of_floor), rotation=envelope.origin.rotation
        ),
        shape=Box(size_x=envelope.length, size_y=envelope.width, size_z=height),
        color=GREENHOUSE_BOUNDS_COLOR,
        label="greenhouse bounds",
    )


def _planting_position(index: int, columns: int) -> Vector3:
    row, column = divmod(index, columns)
    return Vector3(x=(column + 1) * PLANT_PITCH_M, y=(row + 1) * ROW_SPACING_M, z=0.0)


def _plant_entity(plant: PlantWorld, position: Vector3) -> SceneEntity:
    visible_height_cm = plant.stem_length_cm - plant.lowered_length_cm
    fruits = [fruit for truss in plant.trusses for fruit in truss.fruits]
    on_plant = [fruit for fruit in fruits if fruit.status != FruitStatus.HARVESTED]
    return SceneEntity(
        entity_id=plant.plant_id,
        kind=SceneEntityKind.PLANT,
        transform=Transform(position=position),
        shape=Cylinder(
            radius=PLANT_STEM_RADIUS_M,
            height=max(0.0, visible_height_cm * METRES_PER_CENTIMETRE),
        ),
        color=PLANT_COLOR,
        label=plant.plant_id,
        properties={
            "age_days": plant.age_days,
            "visible_height_cm": visible_height_cm,
            "trusses": len(plant.trusses),
            "fruits_on_plant": len(on_plant),
            "ripe_fruits": sum(fruit.status == FruitStatus.RIPE for fruit in on_plant),
            "cumulative_harvest_g": plant.cumulative_harvest_g,
        },
    )


def snapshot_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema a viewer validates snapshots against, published as
    `snapshot.schema.json` next to this module.

    It describes snapshots as the simulator sends them, so every field with a
    default is still required: a viewer never has to supply one. Pydantic
    marks tagged unions with OpenAPI's `discriminator` keyword, which is not
    JSON Schema. The `oneOf` and each shape's constant `shape` already say the
    same, so the published schema leaves the keyword out.
    """
    schema = _without_discriminators(SceneSnapshot.model_json_schema(mode="serialization"))
    assert isinstance(schema, dict)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def _without_discriminators(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: _without_discriminators(item)
            for key, item in value.items()
            if not (key == "discriminator" and isinstance(item, dict) and "propertyName" in item)
        }
    if isinstance(value, list):
        return [_without_discriminators(item) for item in value]
    return value
