"""Equipment and sensors moved across the floor (#209): by a displacement in
the world's axes, turned into the greenhouse's own, heights kept, a camera
looking the same way; written in a layout's name, refused when they do not
fit, and another run when they do."""

import math
from http import HTTPStatus
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.scenarios import SceneChanges, changed, layout_name
from greenhouse_sim.world.equipment import Fan, Heater
from greenhouse_sim.world.geometry import Quaternion, Transform, Vector3
from greenhouse_sim.world.moves import Move, moved
from greenhouse_sim.world.sensors import Camera, PointSensor

REFERENCE = SCENARIO_REGISTRY["reference_greenhouse"]
# 12 m long, its heater's base at x = 11.2 m, its box reaching 11.5 m.
BOX = SCENARIO_REGISTRY["climate_box"]
AT_THE_ORIGIN = Transform(position=Vector3(x=0.0, y=0.0, z=0.0))
# A greenhouse turned a quarter turn anticlockwise in the world, and set
# aside: the world's x runs along its -y.
TURNED = Transform(
    position=Vector3(x=100.0, y=50.0, z=0.0),
    rotation=Quaternion.about(Vector3(x=0.0, y=0.0, z=1.0), math.pi / 2),
)


def _item(layout_name: str, item_id: str) -> object:
    config = changed(REFERENCE, SceneChanges(layout=layout_name))
    return next(
        item
        for item in [*config.layout.equipment, *config.layout.sensors]
        if getattr(item, "actuator_id", None) == item_id
        or getattr(item, "sensor_id", None) == item_id
    )


def test_a_unit_a_fan_and_a_sensor_move_along_the_floor_their_heights_kept() -> None:
    layout = REFERENCE.layout
    heater = next(p for p in layout.equipment if isinstance(p, Heater))
    fan = next(p for p in layout.equipment if isinstance(p, Fan))
    sensor = next(s for s in layout.sensors if isinstance(s, PointSensor))

    after = moved(
        layout,
        AT_THE_ORIGIN,
        [
            Move(heater.actuator_id, -1.0, 0.5),
            Move(fan.actuator_id, 0.25, 0.0),
            Move(sensor.sensor_id, 0.0, 1.0),
        ],
    )

    by_id = {p.actuator_id: p for p in after.equipment}
    moved_heater, moved_fan = by_id[heater.actuator_id], by_id[fan.actuator_id]
    assert isinstance(moved_heater, Heater) and isinstance(moved_fan, Fan)
    assert moved_heater.base == Vector3(
        x=heater.base.x - 1.0, y=heater.base.y + 0.5, z=heater.base.z
    )
    assert moved_fan.position == Vector3(
        x=fan.position.x + 0.25, y=fan.position.y, z=fan.position.z
    )
    moved_sensor = next(s for s in after.sensors if s.sensor_id == sensor.sensor_id)
    assert moved_sensor.position == Vector3(
        x=sensor.position.x, y=sensor.position.y + 1.0, z=sensor.position.z
    )
    # Nothing else moved.
    assert [p for p in after.equipment if p.actuator_id not in by_id] == []
    assert after.placed == layout.placed


def test_a_move_is_in_the_worlds_axes_whichever_way_the_greenhouse_is_turned() -> None:
    heater = next(p for p in REFERENCE.layout.equipment if isinstance(p, Heater))

    after = moved(REFERENCE.layout, TURNED, [Move(heater.actuator_id, 1.0, 0.0)])

    # A metre along the world's x is a metre along the turned greenhouse's -y.
    turned = next(p for p in after.equipment if p.actuator_id == heater.actuator_id)
    assert isinstance(turned, Heater)
    base = turned.base
    assert (base.x, base.y, base.z) == pytest.approx((heater.base.x, heater.base.y - 1.0, 0.0))
    # Where it stands in the world moved by exactly that.
    before_world, after_world = TURNED.apply(heater.base), TURNED.apply(base)
    assert (after_world.x - before_world.x, after_world.y - before_world.y) == pytest.approx(
        (1.0, 0.0)
    )


def test_a_camera_moves_with_its_target_looking_the_same_way() -> None:
    camera = next(s for s in REFERENCE.layout.sensors if isinstance(s, Camera))

    after = moved(REFERENCE.layout, AT_THE_ORIGIN, [Move(camera.sensor_id, 0.5, -0.5)])

    moved_camera = next(s for s in after.sensors if s.sensor_id == camera.sensor_id)
    assert isinstance(moved_camera, Camera)
    assert moved_camera.position.x - camera.position.x == pytest.approx(0.5)
    assert moved_camera.target.x - camera.target.x == pytest.approx(0.5)
    assert moved_camera.target.y - camera.target.y == pytest.approx(-0.5)


def test_moves_are_written_in_a_layouts_name_and_refused_when_they_cannot_be() -> None:
    heater = _item("default~heater:-1:0.5", "heater")
    assert isinstance(heater, Heater)
    assert (heater.base.x, heater.base.y) == pytest.approx((10.2, 1.2))

    for name, refused in [
        ("default~heater:1", "item:dx:dy"),
        ("default~heater:x:0", "item:dx:dy"),
        ("default~heater:inf:0", "item:dx:dy"),
        ("default~boiler:1:0", "no equipment or sensor to move: boiler"),
        ("default~heater:1:0,heater:1:0", "heater is moved twice"),
        ("default~heater:99:0", "moved so, outside the greenhouse: heater"),
    ]:
        with pytest.raises(InvalidRequest, match=refused):
            changed(REFERENCE, SceneChanges(layout=name))


def test_a_moved_layout_is_another_run_and_the_api_draws_it() -> None:
    _, own = air_through_a_run("climate_box")
    _, moved_run = air_through_a_run("climate_box", layout="default~temperature_front:0.5:0")
    assert moved_run != own

    response = respond(
        "GET", "/api/scenarios/reference_greenhouse/scene?layout=default~heater:-1:0.5"
    )
    assert response.status == HTTPStatus.OK
    assert isinstance(response.body, dict)
    scene: dict[str, Any] = response.body
    heater = next(e for e in scene["entities"] if e["entity_id"].endswith("_heater"))
    assert heater["transform"]["position"] == {"x": 10.2, "y": 1.2, "z": 0.0}
    refused = respond("GET", "/api/scenarios/reference_greenhouse/scene?layout=default~heater:99:0")
    assert refused.status == HTTPStatus.BAD_REQUEST


def test_moves_are_checked_in_the_greenhouse_as_its_dimensions_change_it() -> None:
    def heater_x(name: str, length_m: float) -> float:
        config = changed(BOX, SceneChanges(layout=name, envelope={"length": length_m}))
        heater = next(p for p in config.layout.equipment if isinstance(p, Heater))
        return heater.base.x

    # Into the room 2 m more make, and out of the metre fewer take.
    assert heater_x("default~heater:1.5:0", 14.0) == pytest.approx(12.7)
    assert heater_x("default~heater:-2:0", 11.0) == pytest.approx(9.2)
    with pytest.raises(InvalidRequest, match="moved so, outside the greenhouse: heater"):
        heater_x("default~heater:1.5:0", 12.0)
    with pytest.raises(InvalidRequest, match="no such greenhouse"):
        heater_x("default", 11.0)
    # The layout route serves a moved layout, as its own file would be.
    served = respond("GET", "/api/scenarios/climate_box/layout?layout=default~heater:-1:0.5")
    assert served.status == HTTPStatus.OK
    assert isinstance(served.body, dict)
    document: dict[str, Any] = served.body
    heater = next(p for p in document["equipment"] if p["actuator_id"] == "heater")
    assert (heater["base"]["x"], heater["base"]["y"]) == pytest.approx((10.2, 1.2))


def test_the_same_moves_however_written_are_the_same_run() -> None:
    assert layout_name("default") == "default"
    assert layout_name("default~heater:-1:0.50,co2:0:1") == "default~co2:0.0:1.0,heater:-1.0:0.5"
    # A move of nought is none, and no moves left is the layout itself.
    assert layout_name("default~heater:-0:0,co2:0:1") == "default~co2:0.0:1.0"
    assert layout_name("benches~heater:0:-0.0") == "benches"
    assert layout_name(layout_name("default~heater:-1:0.5")) == "default~heater:-1.0:0.5"

    runs = {
        air_through_a_run("climate_box", layout=name)[1]
        for name in [
            "default~heater:-1:0,temperature_front:0.5:0",
            "default~temperature_front:0.5:0,heater:-1:0",
            "default~heater:-1.0:0.0,temperature_front:0.50:-0",
        ]
    }
    assert len(runs) == 1
    # No moves at all is the scenario's own run.
    assert (
        air_through_a_run("climate_box", layout="default~heater:0:0")[1]
        == (air_through_a_run("climate_box")[1])
    )
