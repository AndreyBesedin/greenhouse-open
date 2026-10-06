"""The greenhouse's layout: its fixtures, each with its own identifier,
inside the greenhouse, and in the scene a viewer draws."""

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import (
    _FIXTURE_KINDS,
    FRAME_MATERIAL,
    GUTTER_MATERIAL,
    MATERIAL_COLORS,
    SceneEntityKind,
    greenhouse_scene,
)
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.fixtures import (
    BoxPrimitive,
    CylinderPrimitive,
    FixtureKind,
    Material,
    PipePrimitive,
    RailPrimitive,
)
from greenhouse_sim.world.geometry import Quaternion, Transform, Vector3
from greenhouse_sim.world.layout import Layout, outside_the_greenhouse

HOUSE = Envelope(length=12.0, width=6.4, eave_height=3.0, ridge_height=3.65, spans=2)
TANK = CylinderPrimitive(
    fixture_id="tank",
    base=Vector3(x=2.0, y=2.0, z=0.0),
    radius=0.5,
    height=1.5,
    material=Material.PLASTIC,
)
RAIL = RailPrimitive(
    fixture_id="rail",
    start=Vector3(x=1.0, y=4.0, z=0.1),
    end=Vector3(x=11.0, y=4.0, z=0.1),
    gauge=0.55,
    tube_radius=0.0255,
)


def test_a_layout_lists_every_fixture_its_primitives_build() -> None:
    layout = Layout(placed=[TANK, RAIL])

    assert [fixture.fixture_id for fixture in layout.fixtures()] == [
        "tank",
        "rail_right",
        "rail_left",
    ]


def test_fixtures_sharing_an_identifier_are_refused() -> None:
    # The rail's right tube is called rail_right too.
    pipe = PipePrimitive(
        fixture_id="rail_right",
        start=Vector3(x=1.0, y=1.0, z=0.3),
        end=Vector3(x=5.0, y=1.0, z=0.3),
        radius=0.03,
    )
    with pytest.raises(ValidationError, match="share an identifier: rail_right"):
        Layout(placed=[RAIL, pipe])


@pytest.mark.parametrize(
    ("base", "height", "inside"),
    [
        (Vector3(x=2.0, y=2.0, z=0.0), 1.5, True),
        # Up to the roof over the valley at y = 3.2, where it is only 3 m high.
        (Vector3(x=2.0, y=3.2, z=0.0), 3.1, False),
        # Under the ridge, at 3.65 m, it fits.
        (Vector3(x=2.0, y=1.6, z=0.0), 3.1, True),
        # Through the front wall.
        (Vector3(x=0.2, y=2.0, z=0.0), 1.0, False),
        # Into the floor.
        (Vector3(x=2.0, y=2.0, z=-0.5), 1.0, False),
    ],
)
def test_a_fixture_must_fit_inside_the_greenhouse(
    base: Vector3, height: float, inside: bool
) -> None:
    layout = Layout(placed=[TANK.model_copy(update={"base": base, "height": height})])

    assert outside_the_greenhouse(layout, HOUSE) == ([] if inside else ["tank"])


def test_a_scenario_refuses_a_layout_that_does_not_fit() -> None:
    config = SCENARIO_REGISTRY["gh_demo"]
    outside = TANK.model_copy(update={"base": Vector3(x=50.0, y=2.0, z=0.0)})

    with pytest.raises(ValidationError, match="outside the greenhouse: tank"):
        config.model_validate({**config.model_dump(), "layout": Layout(placed=[outside])})


def test_every_kind_of_fixture_has_a_kind_in_the_scene() -> None:
    assert set(_FIXTURE_KINDS) == set(FixtureKind)
    assert {kind.value for kind in _FIXTURE_KINDS.values()} == {
        kind.value.upper() for kind in FixtureKind
    }


def test_the_scene_draws_each_fixture_in_its_material_with_what_it_obstructs() -> None:
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(placed=[TANK, RAIL]))
    by_id = {entity.entity_id: entity for entity in scene.entities}
    tank, tube = by_id["gh_tank"], by_id["gh_rail_left"]

    assert tank.kind == SceneEntityKind.OBSTACLE
    assert tank.material == Material.PLASTIC
    assert tank.color == MATERIAL_COLORS[Material.PLASTIC]
    assert tank.properties == {
        "obstructs_movement": True,
        "obstructs_airflow": True,
        "obstructs_light": True,
    }
    assert tube.kind == SceneEntityKind.RAIL
    assert tube.material == Material.STEEL
    assert tube.properties["obstructs_airflow"] is False


def test_the_scene_places_fixtures_with_the_greenhouse() -> None:
    quarter_turn = Quaternion(w=2**-0.5, x=0.0, y=0.0, z=2**-0.5)
    placed = HOUSE.model_copy(
        update={"origin": Transform(position=Vector3(x=100.0, y=0.0, z=0.0), rotation=quarter_turn)}
    )
    scene = greenhouse_scene("gh", placed, layout=Layout(placed=[TANK]))
    tank = next(entity for entity in scene.entities if entity.entity_id == "gh_tank")

    # Turned a quarter, the greenhouse's x runs along the world's y.
    assert tank.transform.position.x == pytest.approx(98.0)
    assert tank.transform.position.y == pytest.approx(2.0)


def test_the_envelopes_metal_parts_say_what_they_are_made_of() -> None:
    scene = greenhouse_scene("gh", HOUSE)
    materials = {
        entity.kind: entity.material
        for entity in scene.entities
        if entity.kind in (SceneEntityKind.GUTTER, SceneEntityKind.FRAME, SceneEntityKind.WALL)
    }

    assert materials == {
        SceneEntityKind.GUTTER: GUTTER_MATERIAL,
        SceneEntityKind.FRAME: FRAME_MATERIAL,
        SceneEntityKind.WALL: None,
    }


def test_a_greenhouse_without_a_layout_has_no_fixtures() -> None:
    kinds = {entity.kind for entity in greenhouse_scene("gh", HOUSE).entities}

    assert not kinds & set(_FIXTURE_KINDS.values())


def test_a_box_obstacle_keeps_its_place_in_the_scene() -> None:
    cabinet = BoxPrimitive(
        fixture_id="cabinet",
        base=Vector3(x=3.0, y=1.0, z=0.0),
        size_x=0.6,
        size_y=1.2,
        size_z=1.8,
    )
    scene = greenhouse_scene("gh", HOUSE, layout=Layout(placed=[cabinet]))
    entity = next(entity for entity in scene.entities if entity.entity_id == "gh_cabinet")

    assert entity.transform.position == Vector3(x=3.0, y=1.0, z=0.0)
    assert entity.label == "cabinet"
