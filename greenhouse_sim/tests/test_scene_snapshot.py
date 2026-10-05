"""The scene a viewer is given: deterministic, serializable, and in world
coordinates (metres, right-handed, z up)."""

import json
from datetime import UTC, datetime

import pytest
from greenhouse_protocol.action import LowerPlantAction
from pydantic import ValidationError

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import (
    PLANT_PITCH_M,
    ROW_SPACING_M,
    SceneEntityKind,
    SceneSnapshot,
    scene_snapshot,
)
from greenhouse_sim.world import GreenhouseWorld
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Box, Cylinder, Plane, Quaternion, Transform, Vector3

CONFIG = SCENARIO_REGISTRY["gh_001"]
# More plants than one scenario row holds (10 columns), so the grid wraps.
PLANT_IDS = [f"gh_001_plant_{i:03d}" for i in range(1, 14)]
TIMESTAMP = datetime(2026, 1, 9, 12, 0, tzinfo=UTC)


def _world(days: int = 8) -> GreenhouseWorld:
    engine = SimulationEngine(CONFIG)
    world = engine.initialize(PLANT_IDS, greenhouse_id="gh_001")
    for day in range(1, days + 1):
        world = engine.advance(world, day=day, timestamp=TIMESTAMP, simulation_id="sim").world
    return world


def _plants(snapshot: SceneSnapshot) -> dict[str, tuple[float, float, float, float]]:
    """x, y, z and height of each plant entity, by identifier."""
    plants = {}
    for entity in snapshot.entities:
        if entity.kind == SceneEntityKind.PLANT:
            assert isinstance(entity.shape, Cylinder)
            position = entity.transform.position
            plants[entity.entity_id] = (position.x, position.y, position.z, entity.shape.height)
    return plants


def test_the_same_world_gives_the_same_scene() -> None:
    world = _world()

    assert (
        scene_snapshot(world, CONFIG).model_dump_json()
        == scene_snapshot(world, CONFIG).model_dump_json()
    )


def test_a_scene_survives_a_json_round_trip() -> None:
    snapshot = scene_snapshot(_world(), CONFIG)

    assert SceneSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


def test_a_scene_holds_the_ground_the_axes_and_every_plant() -> None:
    world = _world()
    snapshot = scene_snapshot(world, CONFIG)
    kinds = [entity.kind for entity in snapshot.entities]

    assert kinds.count(SceneEntityKind.GROUND) == 1
    assert kinds.count(SceneEntityKind.AXES) == 1
    assert list(_plants(snapshot)) == [plant.plant_id for plant in world.plants]
    assert len({entity.entity_id for entity in snapshot.entities}) == len(snapshot.entities)
    assert (snapshot.greenhouse_id, snapshot.simulated_day) == ("gh_001", 8)


def test_a_plant_is_as_tall_as_its_visible_stem_in_metres() -> None:
    world = _world()
    heights = {
        plant_id: height
        for plant_id, (_, _, _, height) in _plants(scene_snapshot(world, CONFIG)).items()
    }

    for plant in world.plants:
        visible_cm = plant.stem_length_cm - plant.lowered_length_cm
        assert heights[plant.plant_id] == pytest.approx(visible_cm / 100)


def test_plants_stand_on_the_ground_in_rows_along_x() -> None:
    """z is up and the ground is z = 0. Plants of one scenario row share y and
    step along +x; the next row starts further along +y."""
    snapshot = scene_snapshot(_world(), CONFIG)
    positions = [(x, y, z) for x, y, z, _ in _plants(snapshot).values()]
    ground = next(e for e in snapshot.entities if e.kind == SceneEntityKind.GROUND)
    assert isinstance(ground.shape, Plane)

    first_row, second_row = positions[: CONFIG.columns], positions[CONFIG.columns :]
    assert all(z == 0.0 for _, _, z in positions)
    assert len({y for _, y, _ in first_row}) == 1
    assert [x for x, _, _ in first_row] == pytest.approx(
        [PLANT_PITCH_M * (i + 1) for i in range(CONFIG.columns)]
    )
    assert second_row[0][1] == pytest.approx(first_row[0][1] + ROW_SPACING_M)
    assert all(0 < x < ground.shape.size_x and 0 < y < ground.shape.size_y for x, y, _ in positions)


def test_a_fully_lowered_plant_has_zero_height() -> None:
    world = _world()
    plant = world.plants[0]
    lowered = SimulationEngine(CONFIG).apply_actions(
        world,
        [LowerPlantAction(plant_id=plant.plant_id, amount_cm=plant.stem_length_cm)],
        day=8,
        timestamp=TIMESTAMP,
    )
    assert lowered.results[0].accepted

    assert _plants(scene_snapshot(lowered.world, CONFIG))[plant.plant_id][3] == 0.0


def test_an_unknown_kind_of_entity_is_refused() -> None:
    """A viewer must not have to guess what to draw."""
    document = json.loads(scene_snapshot(_world(), CONFIG).model_dump_json())
    document["entities"][0]["kind"] = "TREE"

    with pytest.raises(ValidationError):
        SceneSnapshot.model_validate(document)


def test_the_scene_schema_tells_a_viewer_exactly_what_it_may_receive() -> None:
    """What a viewer's own types will be generated from: shapes are a union
    tagged by `shape`, kinds are a closed list, and the units are stated."""
    schema = SceneSnapshot.model_json_schema()
    definitions = schema["$defs"]

    assert definitions["Shape"]["discriminator"]["propertyName"] == "shape"
    assert set(definitions["Shape"]["discriminator"]["mapping"]) == {
        "plane",
        "cylinder",
        "box",
        "axes",
    }
    assert definitions["SceneEntityKind"]["enum"] == [kind.value for kind in SceneEntityKind]
    assert "metres" in schema["description"] and "z up" in schema["description"]


def test_the_greenhouse_bounds_are_a_box_standing_on_the_middle_of_its_floor() -> None:
    envelope = CONFIG.envelope
    [bounds] = [
        entity
        for entity in scene_snapshot(_world(), CONFIG).entities
        if entity.kind == SceneEntityKind.GREENHOUSE_BOUNDS
    ]

    assert bounds.entity_id == "gh_001_bounds"
    assert bounds.shape == Box(
        size_x=envelope.length, size_y=envelope.width, size_z=envelope.height
    )
    assert bounds.transform.position == Vector3(x=envelope.length / 2, y=envelope.width / 2, z=0.0)


def test_the_bounds_follow_a_greenhouse_placed_elsewhere_in_the_world() -> None:
    # A quarter turn about z, so the greenhouse's length runs along the world's y.
    turned = Quaternion(w=0.5**0.5, z=0.5**0.5)
    placed = CONFIG.model_copy(
        update={
            "envelope": Envelope(
                length=8.0,
                width=4.0,
                height=3.0,
                origin=Transform(position=Vector3(x=10.0, y=0.0, z=0.0), rotation=turned),
            )
        }
    )
    [bounds] = [
        entity
        for entity in scene_snapshot(_world(), placed).entities
        if entity.kind == SceneEntityKind.GREENHOUSE_BOUNDS
    ]

    assert bounds.transform.rotation == turned
    assert bounds.transform.position.x == pytest.approx(10.0 - 2.0)
    assert bounds.transform.position.y == pytest.approx(4.0)
