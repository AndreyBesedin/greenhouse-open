"""Climate equipment in the scene (P05.1): each piece drawn where it stands,
grey while it is off and in its kind's colour while it runs, with its level
and rated capacity; and a client setting its levels with `?set=`."""

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.equipment import ActuatorKind
from greenhouse_sim.scene.snapshot import (
    EQUIPMENT_COLORS,
    EQUIPMENT_OFF_COLOR,
    SceneEntity,
    SceneEntityKind,
    SceneSnapshot,
)
from greenhouse_sim.world.geometry import Box, Cylinder

EQUIPMENT_KINDS = {SceneEntityKind.FAN, SceneEntityKind.HEATER, SceneEntityKind.DEHUMIDIFIER}


def _scene(scenario_id: str, query: str = "") -> SceneSnapshot:
    response = respond("GET", f"/api/scenarios/{scenario_id}/scene{query}")
    assert response.status == 200, response.body
    return SceneSnapshot.model_validate(response.body)


def _equipment(scene: SceneSnapshot) -> dict[str, SceneEntity]:
    return {e.entity_id: e for e in scene.entities if e.kind in EQUIPMENT_KINDS}


def test_the_climate_box_draws_its_equipment_off_with_its_rated_capacity() -> None:
    equipment = _equipment(_scene("climate_box"))
    fan = equipment["climate_box_fan"]
    heater = equipment["climate_box_heater"]
    dehumidifier = equipment["climate_box_dehumidifier"]

    assert [e.kind for e in equipment.values()] == [
        SceneEntityKind.FAN,
        SceneEntityKind.HEATER,
        SceneEntityKind.DEHUMIDIFIER,
    ]
    assert {e.color for e in equipment.values()} == {EQUIPMENT_OFF_COLOR}
    assert fan.properties == {
        "actuator_id": "fan",
        "level": 0.0,
        "diameter_m": 0.5,
        "flow_m3_s": 1.0,
    }
    assert heater.properties == {"actuator_id": "heater", "level": 0.0, "power_w": 10_000.0}
    assert dehumidifier.properties == {
        "actuator_id": "dehumidifier",
        "level": 0.0,
        "removal_kg_h": 1.0,
        "heat_w": 1_200.0,
    }
    assert fan.label == "fan"


def test_a_piece_is_drawn_as_its_shape_where_it_stands() -> None:
    equipment = _equipment(_scene("climate_box"))
    fan = equipment["climate_box_fan"]
    heater = equipment["climate_box_heater"]

    # The fan's housing from its back face, 0.15 m behind its rotor.
    assert fan.shape == Cylinder(radius=0.25, height=0.3)
    assert fan.transform.position.x == pytest.approx(0.85)
    assert fan.transform.position.z == pytest.approx(2.8)
    assert heater.shape == Box(size_x=0.6, size_y=0.8, size_z=1.2)
    assert (heater.transform.position.x, heater.transform.position.y) == (11.2, 0.7)


def test_a_client_sets_levels_and_running_equipment_shows_its_kinds_colour() -> None:
    equipment = _equipment(_scene("climate_box", "?set=fan:1,heater:0.5"))
    fan = equipment["climate_box_fan"]
    heater = equipment["climate_box_heater"]
    dehumidifier = equipment["climate_box_dehumidifier"]

    assert (fan.properties["level"], fan.color) == (1.0, EQUIPMENT_COLORS[ActuatorKind.FAN])
    assert (heater.properties["level"], heater.color) == (
        0.5,
        EQUIPMENT_COLORS[ActuatorKind.HEATER],
    )
    assert (dehumidifier.properties["level"], dehumidifier.color) == (0.0, EQUIPMENT_OFF_COLOR)


@pytest.mark.parametrize(
    ("scenario_id", "query", "error"),
    [
        ("climate_box", "?set=boiler:1", "climate_box has no equipment 'boiler'"),
        ("climate_box", "?set=fan:1.5", "a level runs from 0 to 1: fan"),
        ("climate_box", "?set=heater:-0.1", "a level runs from 0 to 1: heater"),
        ("climate_box", "?set=fan:nan", "a level runs from 0 to 1: fan"),
        ("climate_box", "?set=fan:full", "set wants key:number pairs, not 'fan:full'"),
        ("tomato_compartment", "?set=fan:1", "tomato_compartment has no equipment 'fan'"),
    ],
    ids=["unknown", "above full", "below off", "not a number", "not a pair", "none there"],
)
def test_a_level_for_equipment_a_scenario_lacks_or_out_of_range_is_refused(
    scenario_id: str, query: str, error: str
) -> None:
    response = respond("GET", f"/api/scenarios/{scenario_id}/scene{query}")

    assert response.status == 400
    assert response.body == {"error": error}


def test_scenarios_without_equipment_draw_none() -> None:
    for scenario_id in ("tomato_compartment", "airflow_box"):
        assert _equipment(_scene(scenario_id)) == {}
