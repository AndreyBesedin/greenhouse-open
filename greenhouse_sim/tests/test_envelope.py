"""The greenhouse's envelope and its own frame (decision 0016): known points
of the greenhouse land where they should in the world."""

import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import SceneEntityKind, scene_snapshot
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Quaternion, Transform, Vector3

# A quarter turn about the world's z: x turns onto y, and y onto -x.
QUARTER_TURN_ABOUT_Z = Quaternion(w=math.sqrt(0.5), z=math.sqrt(0.5))
HOUSE = Envelope(length=24.0, width=12.8, height=5.5)


def _close(actual: Vector3, expected: Vector3) -> bool:
    return all(
        actual_value == pytest.approx(expected_value, abs=1e-12)
        for actual_value, expected_value in zip(
            (actual.x, actual.y, actual.z), (expected.x, expected.y, expected.z), strict=True
        )
    )


def test_a_rotation_turns_vectors_and_a_transform_moves_points() -> None:
    assert _close(QUARTER_TURN_ABOUT_Z.rotate(Vector3(x=1, y=0, z=0)), Vector3(x=0, y=1, z=0))
    assert _close(QUARTER_TURN_ABOUT_Z.rotate(Vector3(x=0, y=1, z=0)), Vector3(x=-1, y=0, z=0))
    assert _close(Quaternion().rotate(Vector3(x=1, y=2, z=3)), Vector3(x=1, y=2, z=3))

    moved = Transform(position=Vector3(x=10, y=0, z=0), rotation=QUARTER_TURN_ABOUT_Z)
    assert _close(moved.apply(Vector3(x=2, y=0, z=1)), Vector3(x=10, y=2, z=1))


def test_the_greenhouse_fills_the_positive_octant_of_its_frame() -> None:
    corner, far_corner = HOUSE.bounds()

    assert corner == Vector3(x=0, y=0, z=0)
    assert far_corner == Vector3(x=24.0, y=12.8, z=5.5)


def test_by_default_the_greenhouse_frame_is_the_world_frame() -> None:
    point = Vector3(x=3.0, y=4.0, z=1.5)

    assert _close(HOUSE.to_world(point), point)


def test_known_points_of_a_placed_greenhouse_land_where_they_should() -> None:
    placed = HOUSE.model_copy(
        update={
            "origin": Transform(
                position=Vector3(x=100.0, y=50.0, z=0.0), rotation=QUARTER_TURN_ABOUT_Z
            )
        }
    )

    # Its floor corner is its origin; its length now runs along the world's y,
    # and its width along the world's -x.
    assert _close(placed.to_world(Vector3(x=0, y=0, z=0)), Vector3(x=100, y=50, z=0))
    assert _close(placed.to_world(Vector3(x=24, y=0, z=0)), Vector3(x=100, y=74, z=0))
    assert _close(placed.to_world(Vector3(x=0, y=12.8, z=0)), Vector3(x=87.2, y=50, z=0))
    assert _close(placed.to_world(Vector3(x=24, y=12.8, z=5.5)), Vector3(x=87.2, y=74, z=5.5))


@pytest.mark.parametrize("field", ["length", "width", "height"])
@pytest.mark.parametrize("size", [0.0, -1.0])
def test_an_envelope_without_room_is_refused(field: str, size: float) -> None:
    sizes = {"length": 24.0, "width": 12.8, "height": 5.5, field: size}

    with pytest.raises(ValidationError):
        Envelope(**sizes)


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_every_scenario_keeps_its_ground_and_plants_inside_its_greenhouse(
    scenario_id: str,
) -> None:
    config = SCENARIO_REGISTRY[scenario_id]
    plant_ids = [f"{scenario_id}_plant_{i:03d}" for i in range(1, config.rows * config.columns + 1)]
    world = SimulationEngine(config).initialize(plant_ids, greenhouse_id=scenario_id)
    scene = scene_snapshot(world, config)
    _, far_corner = config.envelope.bounds()

    for entity in scene.entities:
        if entity.kind not in {SceneEntityKind.GROUND, SceneEntityKind.PLANT}:
            continue
        position = entity.transform.position
        half_x = entity.shape.size_x / 2 if entity.shape.shape == "plane" else 0.0
        half_y = entity.shape.size_y / 2 if entity.shape.shape == "plane" else 0.0
        assert 0.0 <= position.x - half_x and position.x + half_x <= far_corner.x, entity.entity_id
        assert 0.0 <= position.y - half_y and position.y + half_y <= far_corner.y, entity.entity_id
