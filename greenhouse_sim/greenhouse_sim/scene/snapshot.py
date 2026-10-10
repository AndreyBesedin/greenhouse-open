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
a box), its layout's planting positions, each marked by a disc on the floor,
its fixtures, each with what it is made of and what it obstructs, and its
service zones and keep-out volumes, as the boxes they keep, and an upright
cylinder per plant, as tall as its visible stem, at its planting position.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from greenhouse_sim.domain.crop import FruitStatus
from greenhouse_sim.domain.envelope import OpeningKind, SurfaceCategory
from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.domain.layout import FixtureKind, Material, Obstruction, ZoneKind
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import Envelope, Gutter, Member, OpeningPanel, Surface
from greenhouse_sim.world.equipment import Equipment
from greenhouse_sim.world.fixtures import Fixture
from greenhouse_sim.world.geometry import (
    Axes,
    Box,
    Cylinder,
    Quaternion,
    Shape,
    Transform,
    Vector3,
)
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import PlantingPosition
from greenhouse_sim.world.sensors import Camera, Sensor
from greenhouse_sim.world.state import GreenhouseWorld, PlantWorld
from greenhouse_sim.world.zones import Zone

# Bumped when a change to these types would break an existing viewer, as a new
# kind or shape does: a viewer that does not know it refuses the scene.
# 2: the greenhouse's bounds, drawn as a box.
# 3: the greenhouse's floor and walls, in place of the provisional ground.
# 4: its roof, gable end walls as polygons, and gutters.
# 5: its structural frames.
# 6: its doors and vents.
# 7: its layout's fixtures, and what entities are made of.
# 8: its planting positions.
# 9: benches and substrate slabs.
# 10: service zones and keep-out volumes.
# 11: crop wires.
# 12: plants organ by organ (internodes, leaves, trusses, flowers, fruits),
#     and the sphere shape.
# 13: plants' compound leaves, their leaflets drawn with the ellipsoid shape.
# 14: climate equipment: fans, heaters and dehumidifiers.
# 15: sensors and cameras.
SCHEMA_VERSION: Final = 15
# The JSON Schema dialect Pydantic generates, stated in the published schema.
JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"

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
FRAME_COLOR: Final = Color(r=0.66, g=0.68, b=0.7)
VENT_COLOR: Final = Color(r=0.55, g=0.74, b=0.86)
DOOR_COLOR: Final = Color(r=0.45, g=0.5, b=0.56)
AXES_COLOR: Final = Color(r=0.5, g=0.5, b=0.5)
PLANT_COLOR: Final = Color(r=0.2, g=0.55, b=0.24)
# A planting position is marked by a disc this wide and thick, wider than a
# stem, so that it shows around a plant standing on it.
PLANTING_MARKER_RADIUS_M: Final = 0.06
PLANTING_MARKER_HEIGHT_M: Final = 0.01
PLANTING_POSITION_COLOR: Final = Color(r=0.85, g=0.6, b=0.25)
SERVICE_ZONE_COLOR: Final = Color(r=0.45, g=0.7, b=0.85)
KEEP_OUT_COLOR: Final = Color(r=0.9, g=0.35, b=0.3)
GREENHOUSE_BOUNDS_COLOR: Final = Color(r=0.62, g=0.78, b=0.88)
# Equipment that is off is grey; running, it shows its kind's colour.
EQUIPMENT_OFF_COLOR: Final = Color(r=0.55, g=0.55, b=0.55)
# Sensors in Tol's bright yellow, cameras in its purple.
SENSOR_COLOR: Final = Color(r=0.8, g=0.73, b=0.27)
CAMERA_COLOR: Final = Color(r=0.67, g=0.2, b=0.47)
EQUIPMENT_COLORS: Final = {
    ActuatorKind.FAN: Color(r=0.27, g=0.47, b=0.67),
    ActuatorKind.HEATER: Color(r=0.93, g=0.4, b=0.47),
    ActuatorKind.DEHUMIDIFIER: Color(r=0.4, g=0.8, b=0.93),
}
# What the envelope's metal parts are made of.
GUTTER_MATERIAL: Final = Material.ALUMINIUM
FRAME_MATERIAL: Final = Material.STEEL
# A fixture is drawn in its material's colour.
MATERIAL_COLORS: Final = {
    Material.STEEL: Color(r=0.68, g=0.7, b=0.72),
    Material.ALUMINIUM: Color(r=0.8, g=0.82, b=0.85),
    Material.PLASTIC: Color(r=0.9, g=0.9, b=0.88),
    Material.CONCRETE: Color(r=0.64, g=0.63, b=0.6),
    Material.SUBSTRATE: Color(r=0.8, g=0.72, b=0.58),
}


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
    # Where a plant can stand.
    PLANTING_POSITION = "PLANTING_POSITION"
    # The layout's fixtures, one kind for each kind of fixture.
    CROP_GUTTER = "CROP_GUTTER"
    BENCH = "BENCH"
    SLAB = "SLAB"
    WALKWAY = "WALKWAY"
    # Areas kept for a purpose, as the volumes they keep.
    SERVICE_ZONE = "SERVICE_ZONE"
    KEEP_OUT = "KEEP_OUT"
    RAIL = "RAIL"
    PIPE = "PIPE"
    WIRE = "WIRE"
    OBSTACLE = "OBSTACLE"
    # Climate equipment, one kind for each kind of equipment.
    FAN = "FAN"
    HEATER = "HEATER"
    DEHUMIDIFIER = "DEHUMIDIFIER"
    # A point sensor, of any kind, and a camera.
    SENSOR = "SENSOR"
    CAMERA = "CAMERA"
    PLANT = "PLANT"
    # A plant organ by organ, as the organ-level model grows it.
    INTERNODE = "INTERNODE"
    LEAF = "LEAF"
    TRUSS = "TRUSS"
    FLOWER = "FLOWER"
    FRUIT = "FRUIT"


class SceneEntity(BaseModel):
    model_config = ConfigDict(frozen=True, json_schema_serialization_defaults_required=True)

    entity_id: str
    kind: SceneEntityKind
    transform: Transform
    shape: Shape
    color: Color
    # What it is made of, where that is known.
    material: Material | None = None
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


def scene_snapshot(
    world: GreenhouseWorld,
    config: ScenarioConfig,
    levels: Mapping[str, float] | None = None,
) -> SceneSnapshot:
    """The scene a viewer draws for `world`: its greenhouse and layout, as
    `greenhouse_scene` draws them, with its equipment at `levels`, and one
    entity per plant, each at its planting position: the first plant at the
    first, and so on."""
    greenhouse = greenhouse_scene(
        world.greenhouse_id,
        config.envelope,
        world.simulated_day,
        layout=config.layout,
        levels=levels,
    )
    positions = config.layout.planting_positions()
    if len(world.plants) > len(positions):
        raise ValueError(
            f"{len(world.plants)} plants, but only {len(positions)} planting positions"
        )
    plants = [
        _plant_entity(plant, config.envelope, position)
        for plant, position in zip(world.plants, positions, strict=False)
    ]
    return greenhouse.model_copy(update={"entities": [*greenhouse.entities, *plants]})


def greenhouse_scene(
    greenhouse_id: str,
    envelope: Envelope,
    simulated_day: int = 0,
    *,
    layout: Layout | None = None,
    levels: Mapping[str, float] | None = None,
) -> SceneSnapshot:
    """A greenhouse on its own, without a crop: the world's axes, its floor,
    walls, roof, openings, gutters, frames and bounds, and the fixtures and
    equipment of its layout, if it has one, the equipment at `levels` (off
    unless given)."""
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
            *_planting_position_entities(greenhouse_id, envelope, layout or Layout()),
            *_fixture_entities(greenhouse_id, envelope, layout or Layout()),
            *_zone_entities(greenhouse_id, envelope, layout or Layout()),
            *_equipment_entities(greenhouse_id, envelope, layout or Layout(), levels or {}),
            *_sensor_entities(greenhouse_id, envelope, layout or Layout()),
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
    in_greenhouse, shape = gutter.solid()
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{gutter.gutter_id}",
        kind=SceneEntityKind.GUTTER,
        transform=envelope.origin.after(in_greenhouse),
        shape=shape,
        color=GUTTER_COLOR,
        material=GUTTER_MATERIAL,
        label=gutter.gutter_id.replace("_", " "),
    )


def _member_entities(greenhouse_id: str, envelope: Envelope) -> list[SceneEntity]:
    return [_member_entity(greenhouse_id, envelope, member) for member in envelope.members()]


def _member_entity(greenhouse_id: str, envelope: Envelope, member: Member) -> SceneEntity:
    """A structural member as a cylinder from its foot to its head."""
    in_greenhouse, shape = member.solid()
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{member.member_id}",
        kind=SceneEntityKind.FRAME,
        transform=envelope.origin.after(in_greenhouse),
        shape=shape,
        color=FRAME_COLOR,
        material=FRAME_MATERIAL,
        label=member.member_id.replace("_", " "),
    )


def _planting_position_entities(
    greenhouse_id: str, envelope: Envelope, layout: Layout
) -> list[SceneEntity]:
    """A disc on the floor at each planting position, with its row and its
    place along it."""
    return [
        SceneEntity(
            entity_id=f"{greenhouse_id}_{position.position_id}",
            kind=SceneEntityKind.PLANTING_POSITION,
            transform=envelope.origin.after(Transform(position=position.point)),
            shape=Cylinder(radius=PLANTING_MARKER_RADIUS_M, height=PLANTING_MARKER_HEIGHT_M),
            color=PLANTING_POSITION_COLOR,
            label=position.position_id.replace("_", " "),
            properties={"row": position.row, "position_in_row": position.index},
        )
        for position in layout.planting_positions()
    ]


_FIXTURE_KINDS: Final = {
    FixtureKind.CROP_GUTTER: SceneEntityKind.CROP_GUTTER,
    FixtureKind.BENCH: SceneEntityKind.BENCH,
    FixtureKind.SLAB: SceneEntityKind.SLAB,
    FixtureKind.WALKWAY: SceneEntityKind.WALKWAY,
    FixtureKind.RAIL: SceneEntityKind.RAIL,
    FixtureKind.PIPE: SceneEntityKind.PIPE,
    FixtureKind.WIRE: SceneEntityKind.WIRE,
    FixtureKind.OBSTACLE: SceneEntityKind.OBSTACLE,
}


def _fixture_entities(greenhouse_id: str, envelope: Envelope, layout: Layout) -> list[SceneEntity]:
    return [_fixture_entity(greenhouse_id, envelope, fixture) for fixture in layout.fixtures()]


def _fixture_entity(greenhouse_id: str, envelope: Envelope, fixture: Fixture) -> SceneEntity:
    """A fixture, placed in the world, in its material's colour, with what it
    obstructs."""
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{fixture.fixture_id}",
        kind=_FIXTURE_KINDS[fixture.kind],
        transform=envelope.origin.after(fixture.transform),
        shape=fixture.shape,
        color=MATERIAL_COLORS[fixture.material],
        material=fixture.material,
        label=fixture.fixture_id.replace("_", " "),
        properties={
            f"obstructs_{obstruction.value}": obstruction in fixture.obstructs
            for obstruction in Obstruction
        },
    )


_EQUIPMENT_KINDS: Final = {
    ActuatorKind.FAN: SceneEntityKind.FAN,
    ActuatorKind.HEATER: SceneEntityKind.HEATER,
    ActuatorKind.DEHUMIDIFIER: SceneEntityKind.DEHUMIDIFIER,
}


def _equipment_entities(
    greenhouse_id: str, envelope: Envelope, layout: Layout, levels: Mapping[str, float]
) -> list[SceneEntity]:
    return [
        _equipment_entity(greenhouse_id, envelope, piece, levels.get(piece.actuator_id, 0.0))
        for piece in layout.equipment
    ]


def _equipment_entity(
    greenhouse_id: str, envelope: Envelope, piece: Equipment, level: float
) -> SceneEntity:
    """A piece of equipment, placed in the world: grey while it is off, in its
    kind's colour while it runs, with its rated capacity and its level."""
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{piece.actuator_id}",
        kind=_EQUIPMENT_KINDS[piece.kind],
        transform=envelope.origin.after(piece.transform()),
        shape=piece.shape(),
        color=EQUIPMENT_COLORS[piece.kind] if level > 0 else EQUIPMENT_OFF_COLOR,
        material=Material.STEEL,
        label=piece.actuator_id.replace("_", " "),
        properties={"actuator_id": piece.actuator_id, "level": level, **piece.rated()},
    )


def _sensor_entities(greenhouse_id: str, envelope: Envelope, layout: Layout) -> list[SceneEntity]:
    return [_sensor_entity(greenhouse_id, envelope, sensor) for sensor in layout.sensors]


def _sensor_entity(greenhouse_id: str, envelope: Envelope, sensor: Sensor) -> SceneEntity:
    """A sensor's housing or a camera's body, placed in the world, with its
    configuration as properties."""
    properties: dict[str, JsonValue] = {
        "sensor_id": sensor.sensor_id,
        "sensor_kind": sensor.kind.value,
        "cadence_s": sensor.cadence_s,
    }
    kind, color = SceneEntityKind.SENSOR, SENSOR_COLOR
    if isinstance(sensor, Camera):
        kind, color = SceneEntityKind.CAMERA, CAMERA_COLOR
        intrinsics = sensor.intrinsics
        properties |= {
            "image_width_px": intrinsics.width,
            "image_height_px": intrinsics.height,
            "fx_px": intrinsics.fx,
            "fy_px": intrinsics.fy,
            "ppx_px": intrinsics.ppx,
            "ppy_px": intrinsics.ppy,
            "eye_x": sensor.position.x,
            "eye_y": sensor.position.y,
            "eye_z": sensor.position.z,
            "target_x": sensor.target.x,
            "target_y": sensor.target.y,
            "target_z": sensor.target.z,
        }
    else:
        properties |= {"unit": sensor.unit(), **sensor.imperfections.model_dump()}
    fixture = sensor.fixture()
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{sensor.sensor_id}",
        kind=kind,
        transform=envelope.origin.after(fixture.transform),
        shape=fixture.shape,
        color=color,
        material=Material.PLASTIC,
        label=sensor.sensor_id.replace("_", " "),
        properties=properties,
    )


_ZONE_KINDS: Final = {
    ZoneKind.SERVICE: (SceneEntityKind.SERVICE_ZONE, SERVICE_ZONE_COLOR),
    ZoneKind.KEEP_OUT: (SceneEntityKind.KEEP_OUT, KEEP_OUT_COLOR),
}


def _zone_entities(greenhouse_id: str, envelope: Envelope, layout: Layout) -> list[SceneEntity]:
    return [_zone_entity(greenhouse_id, envelope, zone) for zone in layout.zones]


def _zone_entity(greenhouse_id: str, envelope: Envelope, zone: Zone) -> SceneEntity:
    """A zone as the box it keeps, standing on the floor."""
    kind, color = _ZONE_KINDS[zone.kind]
    area = zone.area
    in_greenhouse = Transform(
        position=Vector3(x=area.middle.x, y=area.middle.y, z=0.0),
        rotation=Quaternion.about(Vector3(x=0.0, y=0.0, z=1.0), area.heading),
    )
    return SceneEntity(
        entity_id=f"{greenhouse_id}_{zone.zone_id}",
        kind=kind,
        transform=envelope.origin.after(in_greenhouse),
        shape=Box(size_x=area.length, size_y=area.width, size_z=zone.height),
        color=color,
        label=zone.zone_id.replace("_", " "),
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


def _plant_entity(plant: PlantWorld, envelope: Envelope, position: PlantingPosition) -> SceneEntity:
    visible_height_cm = plant.stem_length_cm - plant.lowered_length_cm
    fruits = [fruit for truss in plant.trusses for fruit in truss.fruits]
    on_plant = [fruit for fruit in fruits if fruit.status != FruitStatus.HARVESTED]
    return SceneEntity(
        entity_id=plant.plant_id,
        kind=SceneEntityKind.PLANT,
        transform=envelope.origin.after(Transform(position=position.point)),
        shape=Cylinder(
            radius=PLANT_STEM_RADIUS_M,
            height=max(0.0, visible_height_cm * METRES_PER_CENTIMETRE),
        ),
        color=PLANT_COLOR,
        label=plant.plant_id,
        properties={
            "planting_position": position.position_id,
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
