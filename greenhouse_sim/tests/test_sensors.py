"""Sensors and cameras in a layout (P06.1): where each stands, how often it
samples, how it errs, and a camera's pose and intrinsics."""

import math

import pytest
from greenhouse_protocol.sensor import CameraIntrinsics
from pydantic import TypeAdapter, ValidationError

from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scene.snapshot import (
    CAMERA_COLOR,
    SENSOR_COLOR,
    SceneEntityKind,
    greenhouse_scene,
)
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.layout import Layout, outside_the_greenhouse
from greenhouse_sim.world.sensors import Camera, Imperfections, PointSensor, Sensor

HOUSE = Envelope(length=12.0, width=6.4, eave_height=4.0, ridge_height=4.8)
THERMOMETER = PointSensor(
    sensor_id="t_1", kind=SensorKind.TEMPERATURE, position=Vector3(x=3.0, y=3.2, z=1.5)
)
# 640 by 480 pixels, a 60° horizontal field of view.
INTRINSICS = CameraIntrinsics(
    width=640,
    height=480,
    fx=320 / math.tan(math.radians(30)),
    fy=320 / math.tan(math.radians(30)),
    ppx=320,
    ppy=240,
)
# At the front of the house, 2 m up, looking down the house and a little down.
CAMERA = Camera(
    sensor_id="camera",
    position=Vector3(x=0.5, y=3.2, z=2.0),
    target=Vector3(x=6.0, y=3.2, z=1.0),
    intrinsics=INTRINSICS,
)
SENSORS: TypeAdapter[Sensor] = TypeAdapter(Sensor)


def _turned(camera: Camera, axis: Vector3) -> tuple[float, float, float]:
    turned = camera.rotation().rotate(axis)
    return (round(turned.x, 9), round(turned.y, 9), round(turned.z, 9))


def test_a_point_sensor_stands_where_it_is_placed_and_reports_in_its_unit() -> None:
    low, high = THERMOMETER.fixture().bounds()

    assert THERMOMETER.unit() == "°C"
    assert THERMOMETER.cadence_s == 60.0
    assert (round(low.x, 9), round(high.x, 9)) == (2.96, 3.04)
    assert (round(low.z, 9), round(high.z, 9)) == (1.46, 1.54)


def test_a_sensor_is_clean_unless_it_is_told_how_it_errs() -> None:
    noisy = Imperfections(noise_sd=0.2, latency_s=30)

    assert THERMOMETER.imperfections.clean()
    assert not noisy.clean()
    with pytest.raises(ValidationError):
        Imperfections(dropout=1.0)
    with pytest.raises(ValidationError):
        Imperfections(noise_sd=-0.1)


def test_sensors_are_read_by_their_kind() -> None:
    sensor = SENSORS.validate_python(
        {"sensor_id": "co2", "kind": "co2", "position": {"x": 1, "y": 1, "z": 1}}
    )
    camera = SENSORS.validate_python(CAMERA.model_dump())

    assert isinstance(sensor, PointSensor) and sensor.unit() == "ppm"
    assert camera == CAMERA
    with pytest.raises(ValidationError):
        SENSORS.validate_python({**THERMOMETER.model_dump(), "kind": "barometer"})


def test_a_camera_looks_at_its_target_its_picture_upright() -> None:
    dx, dy, dz = CAMERA.looking()
    length = math.sqrt(dx**2 + dy**2 + dz**2)
    forward = _turned(CAMERA, Vector3(x=1, y=0, z=0))
    up = _turned(CAMERA, Vector3(x=0, y=0, z=1))

    assert forward == pytest.approx((dx / length, dy / length, dz / length))
    # Its sideways axis stays level.
    assert _turned(CAMERA, Vector3(x=0, y=1, z=0))[2] == pytest.approx(0.0)
    assert up[2] > 0.9


def test_a_camera_cannot_look_at_the_point_it_stands_on() -> None:
    with pytest.raises(ValidationError, match="looks at the point it stands on"):
        Camera.model_validate({**CAMERA.model_dump(), "target": CAMERA.position.model_dump()})


def test_sensors_are_in_the_way_of_nothing() -> None:
    layout = Layout(sensors=[THERMOMETER, CAMERA])

    for obstruction in Obstruction:
        assert layout.obstructing(obstruction) == []


def test_a_sensor_has_an_identifier_of_its_own_and_stands_in_the_house() -> None:
    outside = THERMOMETER.model_copy(
        update={"sensor_id": "t_2", "position": Vector3(x=13, y=3, z=1)}
    )

    with pytest.raises(ValidationError, match="share an identifier: t_1"):
        Layout(sensors=[THERMOMETER, THERMOMETER])
    assert outside_the_greenhouse(Layout(sensors=[THERMOMETER, CAMERA]), HOUSE) == []
    assert outside_the_greenhouse(Layout(sensors=[THERMOMETER, outside]), HOUSE) == ["t_2"]


def test_the_climate_box_is_instrumented() -> None:
    sensors = SCENARIO_REGISTRY["climate_box"].layout.sensors

    assert [(s.sensor_id, s.kind) for s in sensors] == [
        ("temperature_front", SensorKind.TEMPERATURE),
        ("humidity_front", SensorKind.HUMIDITY),
        ("temperature_back", SensorKind.TEMPERATURE),
        ("humidity_back", SensorKind.HUMIDITY),
        ("anemometer", SensorKind.AIR_SPEED),
        ("co2", SensorKind.CO2),
        ("par", SensorKind.PAR),
        ("front_camera", SensorKind.CAMERA),
        # Its weather station, outside.
        ("station_temperature", SensorKind.OUTSIDE_TEMPERATURE),
        ("station_humidity", SensorKind.OUTSIDE_HUMIDITY),
        ("station_pressure", SensorKind.BAROMETRIC_PRESSURE),
        ("station_wind_speed", SensorKind.WIND_SPEED),
        ("station_wind_direction", SensorKind.WIND_DIRECTION),
    ]


def test_the_scene_draws_sensors_and_cameras_with_their_configuration() -> None:
    noisy = THERMOMETER.model_copy(update={"imperfections": Imperfections(noise_sd=0.2)})
    scene = greenhouse_scene("box", HOUSE, layout=Layout(sensors=[noisy, CAMERA]))
    sensor, camera = [
        e for e in scene.entities if e.kind in (SceneEntityKind.SENSOR, SceneEntityKind.CAMERA)
    ]

    assert (sensor.entity_id, sensor.kind, sensor.color) == (
        "box_t_1",
        SceneEntityKind.SENSOR,
        SENSOR_COLOR,
    )
    assert sensor.properties["sensor_kind"] == "temperature"
    assert sensor.properties["unit"] == "°C"
    assert sensor.properties["noise_sd"] == 0.2
    assert sensor.properties["latency_s"] == 0.0
    assert (camera.kind, camera.color) == (SceneEntityKind.CAMERA, CAMERA_COLOR)
    assert camera.properties["image_width_px"] == 640
    assert camera.properties["target_x"] == 6.0
    assert camera.transform.rotation == CAMERA.rotation()


# Level at 1 m, looking along x: 640 by 480 pixels, a 60° horizontal field.
LEVEL = Camera(
    sensor_id="level",
    position=Vector3(x=0.0, y=0.0, z=1.0),
    target=Vector3(x=10.0, y=0.0, z=1.0),
    intrinsics=INTRINSICS,
)


def test_a_camera_projects_a_known_point_onto_its_known_pixel() -> None:
    fx = INTRINSICS.fx

    assert LEVEL.project(Vector3(x=10, y=0, z=1)) == pytest.approx((320, 240))
    # A metre to its left at 10 m: a tenth of its focal length left of the
    # middle; a metre up: a tenth up.
    assert LEVEL.project(Vector3(x=10, y=1, z=1)) == pytest.approx((320 - fx / 10, 240))
    assert LEVEL.project(Vector3(x=10, y=0, z=2)) == pytest.approx((320, 240 - fx / 10))
    assert CAMERA.project(CAMERA.target) == pytest.approx((320, 240))


def test_a_camera_sees_only_what_lands_on_its_picture() -> None:
    assert LEVEL.sees(Vector3(x=10, y=-3, z=0))
    assert LEVEL.project(Vector3(x=-1, y=0, z=1)) is None
    assert not LEVEL.sees(Vector3(x=-1, y=0, z=1))
    # 45° to its side: beyond its 30° half field.
    assert not LEVEL.sees(Vector3(x=10, y=10, z=1))


def test_the_climate_boxs_camera_looks_down_the_house_at_its_units() -> None:
    layout = SCENARIO_REGISTRY["climate_box"].layout
    (camera,) = [s for s in layout.sensors if isinstance(s, Camera)]
    bodies = {piece.actuator_id: piece.fixture().bounds() for piece in layout.equipment}

    def middle(name: str) -> Vector3:
        low, high = bodies[name]
        return Vector3(x=(low.x + high.x) / 2, y=(low.y + high.y) / 2, z=(low.z + high.z) / 2)

    # The heater and the dehumidifier on the floor; the fan hangs above and
    # just ahead of it, out of its view.
    assert camera.sees(middle("heater"))
    assert camera.sees(middle("dehumidifier"))
    assert not camera.sees(middle("fan"))
