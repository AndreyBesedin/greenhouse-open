"""The air as a scenario's equipment drives it (P05.2, P05.3): its `climate`
field, its own airflow plus what its running equipment adds through its
source terms, made to conserve mass, and its temperature through a climate
run, served with the equipment's levels at a moment of the run."""

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.projection import conserving, face_flows
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd, fields
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.world.geometry import Vector3

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
WEATHER = CONFIG.run_weather()
# The fan's axis, 2.8 m up along the middle of the house, from its rotor at
# x = 1 m.
FAN_AT = Vector3(x=1.0, y=3.2, z=2.8)


def _climate(query: str = "") -> EnvironmentField:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _speed_along(
    field: EnvironmentField, x: float, y: float = FAN_AT.y, z: float = FAN_AT.z
) -> float:
    velocity = field.sample(AirQuantity.VELOCITY, Vector3(x=x, y=y, z=z))
    assert isinstance(velocity, Vector3)
    return velocity.x


def _temperature(field: EnvironmentField, x: float, y: float, z: float) -> float:
    temperature = field.sample(AirQuantity.TEMPERATURE, Vector3(x=x, y=y, z=z))
    assert isinstance(temperature, float)
    return temperature


def _run(levels: dict[str, float]) -> ClimateRun:
    return ClimateRun(
        base=CONFIG.airflow,
        equipment=CONFIG.layout.equipment,
        schedule=Schedule.from_start(levels),
        settings=CONFIG.climate,
        grid=GRID,
        solid=cfd.geometry("climate_box").solid(),
        weather=WEATHER,
    )


def test_a_scenario_with_equipment_offers_its_climate_and_others_do_not() -> None:
    assert fields.field_names("climate_box") == [
        "uniform",
        "buoyancy",
        "vortex",
        "climate",
        "shear",
    ]
    assert "climate" not in fields.field_names("tomato_compartment")
    assert "climate" not in fields.field_names("airflow_box")


def test_at_its_start_with_everything_off_the_air_is_still_at_its_starting_temperature() -> None:
    climate = _climate()

    assert climate.source == "climate:prescribed:uniform"
    assert climate.time_s == 0.0
    assert not climate.channels[AirQuantity.VELOCITY].any()
    assert (climate.channels[AirQuantity.TEMPERATURE] == 16.0).all()


def test_with_the_fan_on_the_air_speeds_up_downstream_along_its_axis() -> None:
    off, on = _climate(), _climate("?set=fan:1")
    downstream = [_speed_along(on, x) for x in (2.0, 4.0, 6.0, 9.0, 11.5)]

    assert [_speed_along(off, x) for x in (2.0, 4.0, 6.0, 9.0, 11.5)] == [0.0] * 5
    # Its core, 3 m long, then slower and slower.
    assert downstream[0] > 4.0
    assert downstream[1:] == sorted(downstream[1:], reverse=True)
    assert downstream[-1] > 0.3
    # It draws the air it blows from behind it, and the house sends it back
    # along the floor.
    assert _speed_along(on, 0.4) > 0.1
    assert _speed_along(on, 6.0, z=0.25) < -0.03


def test_the_fans_level_sets_how_much_it_adds() -> None:
    off = _climate().channels[AirQuantity.VELOCITY]
    full = _climate("?set=fan:1").channels[AirQuantity.VELOCITY]
    half = _climate("?set=fan:0.5").channels[AirQuantity.VELOCITY]

    np.testing.assert_allclose(half - off, (full - off) / 2, atol=1e-6)


def test_the_equipment_reaches_the_air_only_through_its_source_terms() -> None:
    run = _run({"fan": 1.0, "heater": 1.0, "dehumidifier": 1.0})
    solid = cfd.geometry("climate_box").solid()
    field = run.field("climate_box_climate", GRID)
    base = CONFIG.airflow.field("climate_box_uniform", GRID).channels[AirQuantity.VELOCITY]
    flow = conserving(face_flows(GRID, base + run.terms_at(0.0).velocity, solid), solid)

    np.testing.assert_array_equal(field.channels[AirQuantity.VELOCITY], flow.velocity())
    # A heater and a dehumidifier move no air.
    units = _climate("?set=heater:1,dehumidifier:1")
    assert not units.channels[AirQuantity.VELOCITY].any()


def test_through_the_run_the_heater_warms_its_corner_and_the_unheated_house_cools() -> None:
    heated = _climate("?set=heater:1&t=600")
    unheated = _climate("?t=600")
    corner = (10.5, 1.0, 0.75)

    assert heated.time_s == unheated.time_s == 600.0
    # 8 °C outside: unheated, the house has cooled most of the way to it.
    assert _temperature(unheated, 6.0, 3.2, 1.5) < 10.0
    assert _temperature(heated, *corner) > 25.0
    assert _temperature(heated, 6.0, 3.2, 1.5) > _temperature(unheated, 6.0, 3.2, 1.5) + 3.0


def test_obstacles_show_the_air_beside_them() -> None:
    temperature = _climate("?t=600").channels[AirQuantity.TEMPERATURE]

    # Not the 16 °C they started at: the air beside them has cooled.
    assert temperature.max() < 12.0


def test_a_run_on_another_grid_or_solid_cells_is_refused() -> None:
    with pytest.raises(ValueError, match="solid cells"):
        ClimateRun(
            base=CONFIG.airflow,
            equipment=CONFIG.layout.equipment,
            schedule=Schedule(),
            settings=CONFIG.climate,
            grid=GRID,
            solid=np.zeros((1, 1, 1), dtype=bool),
            weather=WEATHER,
        )
    other = air_grid(SCENARIO_REGISTRY["airflow_box"])
    with pytest.raises(ValueError, match="its own grid"):
        _run({}).field("climate_box_climate", other)


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("climate_box/fields/climate?set=boiler:1", "climate_box has no equipment 'boiler'"),
        ("climate_box/fields/climate?set=fan:2", "a level runs from 0 to 1: fan"),
        ("tomato_compartment/fields/shear?set=fan:1", "tomato_compartment has no equipment 'fan'"),
        ("tomato_compartment/fields/climate", None),
        ("climate_box/fields/climate?t=-1", "a climate run lasts from 0 to 3600 s, not -1"),
        ("climate_box/fields/climate?t=4000", "a climate run lasts from 0 to 3600 s, not 4000"),
        ("climate_box/fields/climate?t=soon", "t wants seconds, not 'soon'"),
    ],
    ids=["unknown", "above full", "none there", "no climate", "before", "after", "not a time"],
)
def test_levels_a_scenario_cannot_run_are_refused(path: str, error: str | None) -> None:
    response = respond("GET", f"/api/scenarios/{path}")

    if error is None:
        assert response.status == 404
    else:
        assert (response.status, response.body) == (400, {"error": error})


def test_the_service_refuses_levels_as_the_api_does() -> None:
    with pytest.raises(InvalidRequest):
        fields.field("climate_box", "climate", levels={"fan": -1.0})
