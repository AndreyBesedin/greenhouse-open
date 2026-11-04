"""A house whose layout places no equipment has a climate run as any other
has: the climate field, its house's air, and the sun's light. Its sensors and
its run's identity stay its own airflow's (`test_run_identity`)."""

from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.services import fields
from greenhouse_sim.services.climate_readings import equipment_at, house_air_at
from greenhouse_sim.services.crop import scenario_crop
from greenhouse_sim.services.fields import climate_key
from greenhouse_sim.services.run_state import run_state
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator

TOMATO = "tomato_compartment"
# Every packaged layout that places no equipment.
BARE_RUNS = [
    "airflow_box",
    "airflow_box?layout=open",
    "sensor_lab",
    "sensor_lab?layout=blocked",
    TOMATO,
    f"{TOMATO}?layout=propagation",
]
# The compartment's first moments, and noon, the sun up over its site.
TEN_MINUTES_S = 600.0
NOON_S = DAY_S / 2


def _address(run: str, path: str, query: str = "") -> str:
    scenario_id, _, asked = run.partition("?")
    joined = "&".join(part for part in (asked, query) if part)
    return f"/api/scenarios/{scenario_id}/{path}" + (f"?{joined}" if joined else "")


def _climate(simulator: Simulator, run: str, time_s: float) -> EnvironmentField:
    answer = respond(simulator, "GET", _address(run, "fields/climate", f"t={time_s:g}"))
    assert answer.status == HTTPStatus.OK, answer.body
    return EnvironmentField.from_document(FieldDocument.model_validate(answer.body))


@pytest.mark.parametrize("run", BARE_RUNS)
def test_a_layout_without_equipment_offers_and_draws_its_climate(
    simulator: Simulator, run: str
) -> None:
    listed = respond(simulator, "GET", _address(run, "fields"))

    assert listed.status == HTTPStatus.OK
    assert "climate" in fields.FieldNames.model_validate(listed.body).fields
    assert _climate(simulator, run, 0.0).field_id.endswith("_climate")


@pytest.mark.parametrize(
    ("path", "query"),
    [
        ("climate/house", f"t={TEN_MINUTES_S:g}"),
        ("climate/probes", f"t={TEN_MINUTES_S:g}&probes=1:1:1"),
        ("climate/glazing", f"t={TEN_MINUTES_S:g}"),
        ("climate/openings", f"t={TEN_MINUTES_S:g}"),
        ("climate/equipment", f"t={TEN_MINUTES_S:g}"),
        ("climate/state", f"t={TEN_MINUTES_S:g}"),
    ],
    ids=["house", "probes", "glazing", "openings", "equipment", "state"],
)
def test_its_climate_is_read_as_any_other_house(
    simulator: Simulator, path: str, query: str
) -> None:
    answer = respond(simulator, "GET", _address("airflow_box", path, query))

    assert answer.status == HTTPStatus.OK, answer.body


def test_offering_the_climate_works_out_nothing() -> None:
    with Simulator(Catalogue(PACKAGED)) as fresh:
        assert "climate" in fields.field_names(fresh, TOMATO)

        assert list(fresh.climate_runs.values()) == []


def test_the_climate_is_lit_by_the_sun_under_its_weather(simulator: Simulator) -> None:
    sunny = f"{TOMATO}?weather=cold_spring_day"

    midnight = _climate(simulator, sunny, 0.0).channels[AirQuantity.PAR]
    noon = _climate(simulator, sunny, NOON_S).channels[AirQuantity.PAR]

    assert midnight.max() == 0.0
    assert noon.max() > 0.0


def test_its_house_air_is_the_climate_run_its_crop_lives_in() -> None:
    """What is reported is the run the crop already made, not a second one."""
    asked = RunRequest("airflow_box")
    with Simulator(Catalogue(PACKAGED)) as fresh:
        scenario_crop(fresh, asked)
        [(made, climate)] = list(fresh.climate_runs.values())

        air = house_air_at(fresh, asked, TEN_MINUTES_S)
        state = run_state(fresh, asked, until_s=TEN_MINUTES_S)

        assert [key for key, _ in fresh.climate_runs.values()] == [made]
        assert climate_key(fresh, asked) == made
        assert air == climate.house.air_at(TEN_MINUTES_S)
        assert state.house_air.temperature_c == air.temperature_c
        assert state.house_air.co2_ppm == air.co2_ppm


def test_it_runs_no_equipment(simulator: Simulator) -> None:
    worked = equipment_at(simulator, RunRequest(TOMATO), TEN_MINUTES_S)

    assert (worked.levels, worked.thermostat) == ({}, None)
