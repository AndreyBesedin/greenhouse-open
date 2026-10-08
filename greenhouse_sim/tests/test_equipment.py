"""Climate equipment in a layout (P05.1): where each piece stands and which
way it faces, its rated capacity, and what of it is in the way of air and
robots."""

import math

import pytest
from pydantic import TypeAdapter, ValidationError

from greenhouse_sim.cfd.geometry import BoundaryCategory
from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.domain.layout import Obstruction, ZoneKind
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.equipment import Dehumidifier, Equipment, Fan, Heater
from greenhouse_sim.world.fixtures import BoxPrimitive, WalkwayPrimitive
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.layout import Layout, outside_the_greenhouse
from greenhouse_sim.world.zones import Strip, Zone

HOUSE = Envelope(length=12.0, width=6.4, eave_height=4.0, ridge_height=4.8)
FAN = Fan(
    actuator_id="fan",
    position=Vector3(x=1.0, y=3.2, z=2.8),
    diameter_m=0.5,
    flow_m3_s=1.0,
)
# Against the back wall, facing back down the house.
HEATER = Heater(
    actuator_id="heater",
    base=Vector3(x=11.2, y=0.7, z=0.0),
    heading=math.pi,
    size_x=0.6,
    size_y=0.8,
    size_z=1.2,
    power_w=10_000.0,
)
# Against the left side wall, facing across the house.
DEHUMIDIFIER = Dehumidifier(
    actuator_id="dehumidifier",
    base=Vector3(x=6.0, y=5.9, z=0.0),
    heading=-math.pi / 2,
    size_x=0.6,
    size_y=1.0,
    size_z=1.4,
    removal_kg_h=5.0,
    heat_w=4_500.0,
)
EQUIPMENT: TypeAdapter[Equipment] = TypeAdapter(Equipment)


def _rounded(point: Vector3) -> tuple[float, float, float]:
    return (round(point.x, 9), round(point.y, 9), round(point.z, 9))


def test_a_fan_hangs_centred_on_its_position_its_axis_along_its_heading() -> None:
    low, high = FAN.fixture().bounds()

    # 0.3 m deep along x, 0.5 m across in y and z.
    assert _rounded(low) == (0.85, 2.95, 2.55)
    assert _rounded(high) == (1.15, 3.45, 3.05)
    assert _rounded(FAN.facing()) == (1.0, 0.0, 0.0)


def test_a_fan_turned_blows_its_way_and_lies_along_it() -> None:
    turned = FAN.model_copy(update={"heading": math.pi / 2})
    low, high = turned.fixture().bounds()

    assert _rounded(turned.facing()) == (0.0, 1.0, 0.0)
    assert _rounded(low) == (0.75, 3.05, 2.55)
    assert _rounded(high) == (1.25, 3.35, 3.05)


def test_a_unit_stands_on_its_base_its_depth_along_its_heading() -> None:
    heater_low, heater_high = HEATER.fixture().bounds()
    unit_low, unit_high = DEHUMIDIFIER.fixture().bounds()

    assert _rounded(heater_low) == (10.9, 0.3, 0.0)
    assert _rounded(heater_high) == (11.5, 1.1, 1.2)
    # Turned a quarter, its 0.6 m depth runs across the house, its 1 m width
    # along it.
    assert _rounded(unit_low) == (5.5, 5.6, 0.0)
    assert _rounded(unit_high) == (6.5, 6.2, 1.4)


def test_each_piece_states_its_rated_capacity() -> None:
    assert FAN.rated() == {"diameter_m": 0.5, "flow_m3_s": 1.0}
    assert HEATER.rated() == {"power_w": 10_000.0}
    assert DEHUMIDIFIER.rated() == {"removal_kg_h": 5.0, "heat_w": 4_500.0}


def test_equipment_is_read_by_its_kind() -> None:
    piece = EQUIPMENT.validate_python(
        {
            "actuator_id": "heater",
            "kind": "heater",
            "base": {"x": 1.0, "y": 1.0, "z": 0.0},
            "size_x": 0.6,
            "size_y": 0.8,
            "size_z": 1.2,
            "power_w": 5_000.0,
        }
    )

    assert isinstance(piece, Heater)
    assert piece.kind is ActuatorKind.HEATER
    with pytest.raises(ValidationError):
        EQUIPMENT.validate_python({**FAN.model_dump(), "kind": "boiler"})


@pytest.mark.parametrize(
    "change",
    [{"flow_m3_s": 0.0}, {"diameter_m": -0.5}, {"speed": 3.0}],
    ids=["no flow", "negative diameter", "unknown field"],
)
def test_a_fan_without_a_capacity_or_with_an_unknown_field_is_refused(
    change: dict[str, float],
) -> None:
    with pytest.raises(ValidationError):
        Fan.model_validate({**FAN.model_dump(), **change})


def test_heaters_and_dehumidifiers_are_in_the_way_of_air_and_robots_but_a_fan_is_not() -> None:
    layout = Layout(equipment=[FAN, HEATER, DEHUMIDIFIER])

    for obstruction in (Obstruction.AIRFLOW, Obstruction.MOVEMENT):
        names = [fixture.fixture_id for fixture in layout.obstructing(obstruction)]
        assert names == ["heater", "dehumidifier"]
    assert layout.obstructing(Obstruction.LIGHT) == []


def test_a_piece_of_equipment_has_an_identifier_of_its_own() -> None:
    block = BoxPrimitive(
        fixture_id="heater", base=Vector3(x=2.0, y=2.0, z=0.0), size_x=1.0, size_y=1.0, size_z=1.0
    )
    zone = Zone(
        zone_id="fan",
        kind=ZoneKind.SERVICE,
        area=Strip(start=Point2(x=1.0, y=1.0), end=Point2(x=2.0, y=1.0), width=1.0),
        height=2.0,
    )

    with pytest.raises(ValidationError, match="share an identifier: heater"):
        Layout(placed=[block], equipment=[HEATER])
    with pytest.raises(ValidationError, match="share an identifier: fan"):
        Layout(zones=[zone], equipment=[FAN])
    with pytest.raises(ValidationError, match="share an identifier: fan"):
        Layout(equipment=[FAN, FAN.model_copy(update={"position": Vector3(x=5, y=3, z=3)})])


def test_a_unit_on_a_walkway_is_refused_but_a_fan_over_one_is_not() -> None:
    walkway = WalkwayPrimitive(
        fixture_id="path", start=Point2(x=0.0, y=0.7), end=Point2(x=12.0, y=0.7), width=1.0
    )

    with pytest.raises(ValidationError, match="heater"):
        Layout(placed=[walkway], equipment=[HEATER])
    over = FAN.model_copy(update={"position": Vector3(x=6.0, y=0.7, z=2.8)})
    assert Layout(placed=[walkway], equipment=[over]).equipment == [over]


def test_equipment_outside_the_greenhouse_is_named() -> None:
    outside = HEATER.model_copy(update={"base": Vector3(x=12.2, y=0.7, z=0.0)})

    assert outside_the_greenhouse(Layout(equipment=[FAN, HEATER]), HOUSE) == []
    assert outside_the_greenhouse(Layout(equipment=[FAN, outside]), HOUSE) == ["heater"]


def test_the_climate_box_holds_a_fan_a_heater_and_a_dehumidifier() -> None:
    equipment = SCENARIO_REGISTRY["climate_box"].layout.equipment

    assert equipment == [FAN, HEATER, DEHUMIDIFIER]


def test_the_climate_box_meshes_its_units_as_obstacles_but_not_its_fan() -> None:
    geometry = cfd.geometry("climate_box")
    obstacles = {
        boundary.name: boundary.mesh_faces for boundary in geometry.of(BoundaryCategory.OBSTACLE)
    }

    # Its 0.5 m cells: the heater's body holds two of their centres, the
    # dehumidifier's twelve.
    assert obstacles == {"obstacle_heater": 2, "obstacle_dehumidifier": 12}
    assert not {"heater", "dehumidifier", "fan"} & set(geometry.too_small)
