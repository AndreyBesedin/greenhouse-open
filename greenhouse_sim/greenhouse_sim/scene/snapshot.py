"""A renderable description of the simulated world at one moment.

A `SceneSnapshot` lists entities, each with a stable identifier, a kind a
viewer dispatches on, a transform, a shape, a colour, and a label and
properties for an inspector. It uses the world's geometry conventions
(`greenhouse_sim.world.geometry`) and nothing of any renderer.

The viewer is a tool for looking at the simulation, so a snapshot shows the
simulated truth, as the world does. It is not an observation: decision-making
code works from observations, never from a snapshot.

This first snapshot holds the ground, a reference axes marker at the origin,
and an upright cylinder per plant, as tall as its visible stem. Until
planting positions become part of the world (P02), plants stand on a
provisional grid built from the scenario's rows and columns.
"""

import math
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.geometry import Axes, Cylinder, Plane, Shape, Transform, Vector3
from greenhouse_sim.world.state import FruitStatus, GreenhouseWorld, PlantWorld

# Bumped when a change to these types would break an existing viewer.
SCHEMA_VERSION: Final = 1
# The JSON Schema dialect Pydantic generates, stated in the published schema.
JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"

# Provisional layout until planting positions are part of the world (P02).
# Plants of one scenario row stand along +x at this pitch, rows follow one
# another along +y at this spacing, and the ground extends one pitch and one
# row spacing beyond the outermost plants.
PLANT_PITCH_M: Final = 0.5
ROW_SPACING_M: Final = 1.6

PLANT_STEM_RADIUS_M: Final = 0.02
AXES_LENGTH_M: Final = 1.0
METRES_PER_CENTIMETRE: Final = 0.01


class Color(BaseModel):
    """An sRGB colour, each channel from 0 to 1."""

    model_config = ConfigDict(frozen=True)

    r: float = Field(ge=0.0, le=1.0)
    g: float = Field(ge=0.0, le=1.0)
    b: float = Field(ge=0.0, le=1.0)


GROUND_COLOR: Final = Color(r=0.42, g=0.33, b=0.24)
AXES_COLOR: Final = Color(r=0.5, g=0.5, b=0.5)
PLANT_COLOR: Final = Color(r=0.2, g=0.55, b=0.24)


class SceneEntityKind(StrEnum):
    GROUND = "GROUND"
    AXES = "AXES"
    PLANT = "PLANT"


class SceneEntity(BaseModel):
    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    greenhouse_id: str
    simulated_day: int
    entities: list[SceneEntity]


def scene_snapshot(world: GreenhouseWorld, config: ScenarioConfig) -> SceneSnapshot:
    """The scene a viewer draws for `world`: ground, axes, one entity per plant."""
    columns = max(config.columns, 1)
    rows = max(config.rows, math.ceil(len(world.plants) / columns))
    ground_size_x = (columns + 1) * PLANT_PITCH_M
    ground_size_y = (rows + 1) * ROW_SPACING_M

    ground = SceneEntity(
        entity_id=f"{world.greenhouse_id}_ground",
        kind=SceneEntityKind.GROUND,
        transform=Transform(position=Vector3(x=ground_size_x / 2, y=ground_size_y / 2, z=0.0)),
        shape=Plane(size_x=ground_size_x, size_y=ground_size_y),
        color=GROUND_COLOR,
        label="ground",
    )
    axes = SceneEntity(
        entity_id=f"{world.greenhouse_id}_axes",
        kind=SceneEntityKind.AXES,
        transform=Transform(position=Vector3(x=0.0, y=0.0, z=0.0)),
        shape=Axes(length=AXES_LENGTH_M),
        color=AXES_COLOR,
        label="world axes",
    )
    plants = [
        _plant_entity(plant, _planting_position(index, columns))
        for index, plant in enumerate(world.plants)
    ]
    return SceneSnapshot(
        greenhouse_id=world.greenhouse_id,
        simulated_day=world.simulated_day,
        entities=[ground, axes, *plants],
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

    Pydantic marks tagged unions with OpenAPI's `discriminator` keyword, which
    is not JSON Schema. The `oneOf` and each shape's constant `shape` already
    say the same, so the published schema leaves the keyword out.
    """
    schema = _without_discriminators(SceneSnapshot.model_json_schema())
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
