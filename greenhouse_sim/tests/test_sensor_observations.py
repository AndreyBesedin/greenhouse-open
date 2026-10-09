"""Point sensors observing the air (P06.2): each reads, at its cadence, the
quantity the air's field samples at its position, and reports it as an
observation; what it truly sampled leaves by an evaluation path that nothing
on the observation path imports."""

import ast
from datetime import timedelta
from pathlib import Path

import pytest
from greenhouse_protocol.contracts.conformance import check_observations
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.observation import Observation

from greenhouse_sim.api.routes import respond
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.sensors import SensorKind
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.sensors.air import observe, reads, samples
from greenhouse_sim.services import sensors
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.sensors import PointSensor

PACKAGE = Path(__file__).resolve().parents[1] / "greenhouse_sim"
CONFIG = SCENARIO_REGISTRY["climate_box"]
START = CONFIG.run_start()
MOMENTS = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
HEATED = {"heater": 1.0, "fan": 1.0}


def _observed(sensor_id: str | None = None, *, clean: bool = False) -> list[Observation]:
    observed = sensors.observations(
        "climate_box", levels=HEATED, until_s=300, clean=clean
    ).observations
    return [o for o in observed if sensor_id is None or o.sensor_id == sensor_id]


def _climate(time_s: float) -> EnvironmentField:
    response = respond(
        "GET", f"/api/scenarios/climate_box/fields/climate?set=heater:1,fan:1&t={time_s:g}"
    )
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _sensor(sensor_id: str) -> PointSensor:
    sensor = next(s for s in CONFIG.layout.sensors if s.sensor_id == sensor_id)
    assert isinstance(sensor, PointSensor)
    return sensor


def test_a_clean_sensor_reports_the_air_where_it_stands_at_each_of_its_samples() -> None:
    # The climate box's front temperature sensor is clean.
    observed = _observed("temperature_front")
    position = _sensor("temperature_front").position

    # The published field is in 32-bit floats; a sensor reads the run's own.
    assert [o.value for o in observed] == pytest.approx(
        [_climate(moment).sample(AirQuantity.TEMPERATURE, position) for moment in MOMENTS], rel=1e-6
    )
    assert [o.timestamp for o in observed] == [START + timedelta(seconds=m) for m in MOMENTS]
    assert [o.delivered_at for o in observed] == [o.timestamp for o in observed]


def test_each_kind_reports_its_own_quantity() -> None:
    latest = {o.sensor_id: o for o in _observed()}

    assert latest["humidity_front"].observation_type == ObservationType.RELATIVE_HUMIDITY_PCT
    assert latest["co2"].observation_type == ObservationType.CO2_PPM
    assert latest["co2"].value == pytest.approx(420.0, abs=40)
    # In the fan's jet, its anemometer reads the jet's speed.
    assert latest["anemometer"].observation_type == ObservationType.AIR_SPEED_M_S
    assert latest["anemometer"].value > 3.0


def test_a_quantity_no_model_gives_is_no_reading_at_all() -> None:
    truth = sensors.truth("climate_box", levels=HEATED, until_s=300)
    par = next(s for s in truth.sensors if s.sensor_id == "par")

    assert _observed("par") == []
    assert par.values == [None] * len(MOMENTS)
    assert par.observation_type == ObservationType.PAR_UMOL_M2_S


def test_observations_conform_to_the_protocol_and_name_their_sensor_and_run() -> None:
    observed = sensors.observations("climate_box", levels={"heater": 1.0}, until_s=300)

    assert check_observations(observed.observations) == []
    assert {o.sensor_id for o in observed.observations} == {
        "temperature_front",
        "humidity_front",
        "temperature_back",
        "humidity_back",
        "anemometer",
        "co2",
        "station_temperature",
        "station_humidity",
        "station_pressure",
        "station_wind_speed",
        "station_wind_direction",
    }
    assert {o.source.source_id for o in observed.observations} == {observed.run_id}
    delivered = [o.delivered_at or o.timestamp for o in observed.observations]
    assert delivered == sorted(delivered)


def test_another_run_is_another_source() -> None:
    heated = sensors.observations("climate_box", levels={"heater": 1.0}, until_s=60)
    unheated = sensors.observations("climate_box", until_s=60)

    assert heated.run_id != unheated.run_id
    assert heated.run_id == sensors.observations("climate_box", levels={"heater": 1.0}).run_id


def test_the_truth_is_what_a_clean_sensor_observed() -> None:
    observed = _observed(clean=True)

    for truth in sensors.truth("climate_box", levels=HEATED, until_s=300).sensors:
        readings = [o.value for o in observed if o.sensor_id == truth.sensor_id]
        assert readings == [value for value in truth.values if value is not None]
        assert truth.times_s == MOMENTS


def test_a_sensor_samples_every_cadence_from_the_start() -> None:
    sensor = PointSensor(
        sensor_id="t", kind=SensorKind.TEMPERATURE, position=Vector3(x=1, y=1, z=1), cadence_s=45
    )

    assert samples(sensor, 100) == [0, 45, 90]
    assert samples(sensor, 0) == [0]


def test_a_sensor_in_steady_air_reads_it_the_same_at_every_sample() -> None:
    sensor = PointSensor(
        sensor_id="t", kind=SensorKind.TEMPERATURE, position=Vector3(x=1, y=1, z=1)
    )
    air = CONFIG.airflow.field("still", _climate(0).grid)

    observed = observe([sensor], lambda _: air, 180, start=START, greenhouse_id="box", run_id="run")

    assert [o.value for o in observed] == [reads(sensor, air)] * 4


def test_the_api_serves_the_observations_and_the_truth() -> None:
    observed = respond(
        "GET", "/api/scenarios/climate_box/climate/observations?set=heater:1&t=120&clean=1"
    )
    truth = respond("GET", "/api/scenarios/climate_box/climate/truth?set=heater:1&t=120")

    assert (observed.status, truth.status) == (200, 200)
    assert isinstance(observed.body, dict) and isinstance(truth.body, dict)
    assert observed.body["run_id"] == truth.body["run_id"]
    assert isinstance(observed.body["observations"], list)
    # Six sensors inside and five outside give a reading a minute each; PAR
    # gives none.
    assert len(observed.body["observations"]) == 11 * 3


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("?t=4000", "a run lasts from 0 to 3600 s, not 4000"),
        ("?set=boiler:1", "climate_box has no equipment 'boiler'"),
    ],
    ids=["after the run", "unknown equipment"],
)
def test_observations_a_run_cannot_give_are_refused(query: str, error: str) -> None:
    for asked in ("observations", "truth"):
        response = respond("GET", f"/api/scenarios/climate_box/climate/{asked}{query}")
        assert (response.status, response.body) == (400, {"error": error})


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


def test_nothing_on_the_observation_path_imports_the_truth() -> None:
    """Only evaluation, and the services that serve it to evaluation and QA
    tooling, read what was truly the case."""
    allowed = {PACKAGE / "evaluation", PACKAGE / "services"}
    readers = [
        path.relative_to(PACKAGE)
        for path in PACKAGE.rglob("*.py")
        if not any(folder in path.parents for folder in allowed)
        and any(
            name == "greenhouse_sim.ground_truth" or name.startswith("greenhouse_sim.evaluation")
            for name in _imports(path)
        )
    ]

    assert readers == []
