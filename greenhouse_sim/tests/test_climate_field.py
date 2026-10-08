"""The air as a scenario's equipment drives it (P05.2): its `climate` field,
its own airflow plus what its running equipment adds through its source
terms, served with the equipment's levels."""

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.field import ClimateAirflow
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd, fields
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.world.geometry import Vector3

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
# The fan's axis, 2.8 m up along the middle of the house, from its rotor at
# x = 1 m.
FAN_AT = Vector3(x=1.0, y=3.2, z=2.8)


def _climate(query: str = "") -> EnvironmentField:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _climate_of_own() -> EnvironmentField:
    response = respond("GET", "/api/scenarios/climate_box/fields/uniform")
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _speed_along(field: EnvironmentField, x: float, y: float = FAN_AT.y) -> float:
    velocity = field.sample(AirQuantity.VELOCITY, Vector3(x=x, y=y, z=FAN_AT.z))
    assert isinstance(velocity, Vector3)
    return velocity.x


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


def test_with_everything_off_the_climate_is_the_scenarios_own_air() -> None:
    climate = _climate()
    own = _climate_of_own()

    assert climate.source == "climate:prescribed:uniform"
    for quantity, values in own.channels.items():
        np.testing.assert_array_equal(climate.channels[quantity], values)


def test_with_the_fan_on_the_air_speeds_up_downstream_along_its_axis() -> None:
    off, on = _climate(), _climate("?set=fan:1")
    downstream = [_speed_along(on, x) for x in (2.0, 4.0, 6.0, 9.0, 11.5)]

    assert [_speed_along(off, x) for x in (2.0, 4.0, 6.0, 9.0, 11.5)] == [0.0] * 5
    # Its core, 3 m long, then slower and slower.
    assert downstream[0] > 4.0
    assert downstream[1:] == sorted(downstream[1:], reverse=True)
    assert downstream[-1] > 1.0
    # Nothing behind its rotor, or 2.5 m beside its axis.
    assert _speed_along(on, 0.4) == 0.0
    assert _speed_along(on, 4.0, y=FAN_AT.y + 2.5) == 0.0


def test_the_fans_level_sets_how_much_it_adds() -> None:
    off = _climate().channels[AirQuantity.VELOCITY]
    full = _climate("?set=fan:1").channels[AirQuantity.VELOCITY]
    half = _climate("?set=fan:0.5").channels[AirQuantity.VELOCITY]

    np.testing.assert_allclose(half - off, (full - off) / 2, atol=1e-6)


def test_the_equipment_reaches_the_air_only_through_its_source_terms() -> None:
    levels = {"fan": 1.0, "heater": 1.0, "dehumidifier": 1.0}
    climate = ClimateAirflow(
        base=CONFIG.airflow,
        equipment=CONFIG.layout.equipment,
        levels=levels,
        solid=cfd.geometry("climate_box").solid(),
    )
    field = climate.field("climate_box_climate", GRID)
    base = CONFIG.airflow.field("climate_box_uniform", GRID)

    np.testing.assert_array_equal(
        field.channels[AirQuantity.VELOCITY],
        base.channels[AirQuantity.VELOCITY] + climate.terms(GRID).velocity,
    )
    # A heater and a dehumidifier add no velocity, and the air's temperature
    # is its own until it is carried.
    units = _climate("?set=heater:1,dehumidifier:1")
    assert not units.channels[AirQuantity.VELOCITY].any()
    np.testing.assert_array_equal(
        field.channels[AirQuantity.TEMPERATURE], base.channels[AirQuantity.TEMPERATURE]
    )


def test_the_solid_cells_must_be_the_grids() -> None:
    climate = ClimateAirflow(
        base=CONFIG.airflow,
        equipment=CONFIG.layout.equipment,
        levels={},
        solid=np.zeros((1, 1, 1), dtype=bool),
    )

    with pytest.raises(ValueError, match="solid cells"):
        climate.field("climate_box_climate", GRID)


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("climate_box/fields/climate?set=boiler:1", "climate_box has no equipment 'boiler'"),
        ("climate_box/fields/climate?set=fan:2", "a level runs from 0 to 1: fan"),
        ("tomato_compartment/fields/shear?set=fan:1", "tomato_compartment has no equipment 'fan'"),
        ("tomato_compartment/fields/climate", None),
    ],
    ids=["unknown", "above full", "none there", "no climate"],
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
