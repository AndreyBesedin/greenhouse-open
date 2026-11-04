"""A house whose layout places no equipment has a climate run as any other
has: the climate field, its house's air, and the sun's light. A packaged one's
sensors and its run's identity stay its own airflow's (`test_run_identity`); a
built or uploaded one's are its climate run's."""

import json
import sys
from http import HTTPStatus
from pathlib import Path

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.scenario_files import export_scenario_file
from greenhouse_sim.services import fields, scenario_files
from greenhouse_sim.services.climate_readings import equipment_at, house_air_at
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.crop import scenario_crop
from greenhouse_sim.services.fields import climate_key
from greenhouse_sim.services.run_state import run_state
from greenhouse_sim.services.run_store import EpochManifest, EpochStore, FolderStore, Status
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.sensors import delivered_between
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.world.geometry import Vector3

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut, simulator_of

TOMATO = "tomato_compartment"
# A house not packaged, and the id its run had when it was named by its airflow.
BUILT = "built_lab"
OLD_ID = f"{BUILT}-gradient-0123abcd"
HOUR_S = 3600.0
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


def _lab() -> ScenarioConfig:
    """A house not packaged, with sensors and no equipment, whose configuration
    states a gradient: the sensor lab, under another name, for two days."""
    return cut("sensor_lab", days=2, season=True, greenhouse_id=BUILT)


def _reads_its_climate(simulator: Simulator) -> None:
    asked = RunRequest(BUILT)
    air_at, run_id = fields.air_through_a_run(simulator, asked)
    _, climate = climate_run(simulator, asked)
    at = Vector3(x=2.0, y=2.0, z=1.0)

    assert run_id.startswith(f"{BUILT}-climate-")
    for moment in (TEN_MINUTES_S, NOON_S):
        assert air_at(moment).sample(AirQuantity.TEMPERATURE, at) == climate.sampled(
            "climate", moment
        ).sample(AirQuantity.TEMPERATURE, at)
    assert air_at(TEN_MINUTES_S).sample(AirQuantity.TEMPERATURE, at) != air_at(NOON_S).sample(
        AirQuantity.TEMPERATURE, at
    )


def test_a_house_not_packaged_with_no_equipment_is_sensed_in_its_climate_run() -> None:
    with simulator_of(_lab()) as simulator:
        _reads_its_climate(simulator)
        delivered, run_id = delivered_between(simulator, RunRequest(BUILT), None, HOUR_S)

    assert delivered
    assert run_id.startswith(f"{BUILT}-climate-")


def test_a_file_that_states_a_gradient_is_sensed_in_its_climate_run_and_still_offers_it() -> None:
    with Simulator() as simulator:
        uploaded = respond(
            simulator, "POST", "/api/scenarios/upload", export_scenario_file(_lab()).encode()
        )
        assert uploaded.status == HTTPStatus.OK, uploaded.body
        entry = simulator.catalogue.entry(BUILT)
        assert entry is not None
        assert entry.config.airflow.kind == "gradient"

        _reads_its_climate(simulator)
        assert respond(simulator, "GET", _address(BUILT, "fields/gradient")).status == HTTPStatus.OK


def test_an_epoch_kept_under_the_id_a_built_house_had_is_listed_and_not_carried_on(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path / "runs")
    with Simulator(runs=objects) as simulator:
        uploaded = respond(
            simulator, "POST", "/api/scenarios/upload", export_scenario_file(_lab()).encode()
        )
        assert uploaded.status == HTTPStatus.OK, uploaded.body
        file = scenario_files.carry(simulator.catalogue, objects, BUILT)
        assert file is not None
        kept = EpochStore.create(
            objects,
            EpochManifest(
                run_id=OLD_ID,
                epoch=0,
                scenario_id=BUILT,
                layout="default",
                status=Status.INTERRUPTED,
                scenario_file=file,
            ),
        )
        simulator.scheduler = Scheduler(simulator, objects.root, limit=1)

        listed = respond(simulator, "GET", "/api/runs")
        assert listed.status == HTTPStatus.OK
        assert OLD_ID in json.dumps(listed.body)

        before = objects.get(f"{OLD_ID}/0/manifest.json")
        resumed = respond(simulator, "POST", f"/api/runs/{OLD_ID}/epochs/0/resume")

    assert resumed.status == HTTPStatus.CONFLICT
    assert "asked for again as a new epoch" in json.dumps(resumed.body)
    assert objects.get(f"{OLD_ID}/0/manifest.json") == before
    assert kept.manifest().status == Status.INTERRUPTED
