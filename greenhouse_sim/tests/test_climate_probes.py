"""Probes through a climate run, beside the same run with everything off
(P05.7): their values are what the run's field reads at their points at
each moment, every minute up to the moment asked."""

import math

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.world.geometry import Vector3

# Beside the climate box's heater, and in the middle of the house.
CORNER = Vector3(x=10.5, y=1.0, z=0.75)
MIDDLE = Vector3(x=6.0, y=3.2, z=0.75)
PROBES = "10.5:1:0.75,6:3.2:0.75"


def _probes(query: str) -> dict:  # type: ignore[type-arg]
    response = respond("GET", f"/api/scenarios/climate_box/climate/probes{query}")
    assert response.status == 200, response.body
    assert isinstance(response.body, dict)
    return response.body


def _field(query: str) -> EnvironmentField:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _read(field: EnvironmentField, point: Vector3) -> tuple[float, float, float]:
    temperature = field.sample(AirQuantity.TEMPERATURE, point)
    humidity = field.sample(AirQuantity.HUMIDITY, point)
    velocity = field.sample(AirQuantity.VELOCITY, point)
    assert isinstance(temperature, float) and isinstance(humidity, float)
    assert isinstance(velocity, Vector3)
    return temperature, humidity, math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)


def test_probes_read_every_minute_up_to_the_moment_asked() -> None:
    assert _probes(f"?probes={PROBES}&t=150")["times_s"] == [0, 60, 120, 150]
    assert _probes(f"?probes={PROBES}")["times_s"] == [0]


def test_the_charts_values_are_the_probes_values_at_each_time() -> None:
    asked = "set=heater:1&schedule=120:fan:1,240:dehumidifier:1"
    series = _probes(f"?probes={PROBES}&{asked}&t=300")

    for index, time_s in enumerate(series["times_s"]):
        controlled = _field(f"?{asked}&t={time_s:g}")
        all_off = _field(f"?t={time_s:g}")
        for probe, point in zip(series["probes"], (CORNER, MIDDLE), strict=True):
            for readings, field in ((probe["controlled"], controlled), (probe["all_off"], all_off)):
                assert (
                    readings["temperature_c"][index],
                    readings["humidity_pct"][index],
                    readings["speed_m_s"][index],
                ) == _read(field, point)


def test_the_controlled_and_uncontrolled_runs_diverge_where_the_equipment_acts() -> None:
    series = _probes(f"?probes={PROBES}&set=heater:1&t=600")
    corner, middle = series["probes"]

    # At the start, both runs are the same air.
    assert corner["controlled"]["temperature_c"][0] == corner["all_off"]["temperature_c"][0]
    beside = corner["controlled"]["temperature_c"][-1] - corner["all_off"]["temperature_c"][-1]
    across = middle["controlled"]["temperature_c"][-1] - middle["all_off"]["temperature_c"][-1]
    assert beside > 20.0
    assert 3.0 < across < beside


def test_the_all_off_run_keeps_the_doors_and_vents_as_asked() -> None:
    shut = _probes(f"?probes={PROBES}&set=heater:1&t=600")
    venting = _probes(f"?probes={PROBES}&set=heater:1&open=roof_vent:1&t=600")

    assert venting["probes"][1]["all_off"] != shut["probes"][1]["all_off"]


@pytest.mark.parametrize(
    ("path", "status", "error"),
    [
        (
            "climate_box/climate/probes?probes=30:1:1",
            400,
            "a probe stands in the house's air, not at (30, 1, 1)",
        ),
        ("climate_box/climate/probes?probes=a:b", 400, "probes wants x:y:z points, not 'a:b'"),
        (
            "climate_box/climate/probes?probes=1:1:1&t=90000",
            400,
            "a climate run lasts from 0 to 86400 s, not 90000",
        ),
        (
            "climate_box/climate/probes?probes=1:1:1&set=boiler:1",
            400,
            "climate_box has no equipment 'boiler'",
        ),
        (
            "tomato_compartment/climate/probes?probes=1:1:1",
            404,
            "scenario 'tomato_compartment' has no climate: it has no equipment",
        ),
    ],
    ids=["outside", "not a point", "after the run", "unknown equipment", "no climate"],
)
def test_probes_a_run_cannot_read_are_refused(path: str, status: int, error: str) -> None:
    response = respond("GET", f"/api/scenarios/{path}")

    assert (response.status, response.body) == (status, {"error": error})
