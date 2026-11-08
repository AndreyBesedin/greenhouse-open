"""A run's identity (decision 0042): the same scenario, the same run id;
anything it is made of changed, its manifest or its layout, another, for a
scenario whose equipment drives its air and for one whose airflow is its
own."""

import dataclasses
import json
from urllib.parse import parse_qs

import pytest

from greenhouse_sim.api.routes.runs import run_request
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.crop_parameters import WALK
from greenhouse_sim.scenarios.registry import MODELS
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.sensors import observations
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.world.geometry import Vector3


@pytest.mark.parametrize("scenario_id", ["climate_box", "airflow_box"])
def test_a_run_is_named_by_what_its_scenario_is_made_of(
    simulator: Simulator, scenario_id: str
) -> None:
    _, run_id = air_through_a_run(simulator, RunRequest(scenario_id))
    assert air_through_a_run(simulator, RunRequest(scenario_id))[1] == run_id

    config = SCENARIO_REGISTRY[scenario_id]
    reseeded = config.model_copy(update={"random_seed": config.random_seed + 1})
    with Simulator(Catalogue(PACKAGED.with_config(reseeded))) as reseeding:
        _, other = air_through_a_run(reseeding, RunRequest(scenario_id))

    assert other != run_id
    assert other.startswith(f"{scenario_id}-")


# Runs as the API's addresses ask for them, and the ids they have since a
# run's identity covers its models' versions (P14.2) and its crop's and
# crop walk's parameters are each a section of its scenario (P14.3), and
# the house's air and the controller are parts of their own (P14.6), and
# the simple crop's settings hold none of the engine's day's (decision
# 0059): the same requests must name the same runs, so that every record,
# replay and kept day made of them stands.
PINNED_RUNS = [
    ("reference_greenhouse", "", "reference_greenhouse-climate-7828c7c0"),
    ("reference_greenhouse", "set=heater:0&daily=none", "reference_greenhouse-climate-4f99643e"),
    (
        "reference_greenhouse",
        "targets=3600:heating_day:24,60:heating_night:15",
        "reference_greenhouse-climate-420ddb9e",
    ),
    (
        "reference_greenhouse",
        "schedule=600:roof_vent_1:1,600:roof_vent_1:0.5&targets=86400:heating_night:12",
        "reference_greenhouse-climate-1036afb1",
    ),
    ("climate_box", "", "climate_box-climate-b438615f"),
    ("climate_box", "set=fan:1&schedule=60:fan:0.5,30:heater:1", "climate_box-climate-e868af14"),
    (
        "climate_box",
        "daily=64800:heater:1,0:fan:1&schedule=0:fan:0",
        "climate_box-climate-a2eaa597",
    ),
    ("climate_box", "open=roof_vent:0.5&schedule=120:roof_vent:1", "climate_box-climate-13e8d67f"),
    ("climate_box", "weather=cold_spring_day&set=heater:0.5", "climate_box-climate-82d3cf49"),
    # A layout that places no equipment names its run by its own airflow, not
    # by the climate it also has, under any doors asked for; but another weather,
    # under which its crop grows, is another run, as a seed is (decision 0075).
    ("tomato_compartment", "", "tomato_compartment-buoyancy-ff1e01dd"),
    ("tomato_compartment", "layout=propagation", "tomato_compartment-buoyancy-d777fe8b"),
    ("tomato_compartment", "seed=7", "tomato_compartment-buoyancy-4233e032"),
    ("tomato_compartment", "weather=cold_spring_day", "tomato_compartment-buoyancy-26a055b1"),
    ("tomato_compartment", "weather=default", "tomato_compartment-buoyancy-ff1e01dd"),
    ("tomato_compartment", "open=door_front:1", "tomato_compartment-buoyancy-ff1e01dd"),
    ("airflow_box", "", "airflow_box-uniform-d42cfee2"),
    ("airflow_box", "layout=open", "airflow_box-uniform-4acacb3e"),
    ("sensor_lab", "", "sensor_lab-gradient-0c377594"),
    ("sensor_lab", "layout=blocked", "sensor_lab-gradient-81e91e89"),
]

# What the sensor lab's sensors read through its run's first hour: its own
# airflow, each with its noise.
READINGS_OF_THE_LAB = "7abe259f6111ff15"


@pytest.mark.parametrize(("scenario_id", "query", "run_id"), PINNED_RUNS)
def test_a_run_asked_for_as_before_has_the_id_it_had(
    simulator: Simulator, scenario_id: str, query: str, run_id: str
) -> None:
    asked = run_request(scenario_id, parse_qs(query))

    assert air_through_a_run(simulator, asked)[1] == run_id


def test_a_house_without_equipment_is_sensed_in_its_own_airflow(simulator: Simulator) -> None:
    """Its climate run is the air its crop lives in and what the climate field
    draws; what its sensors read, and so the records of its run, stay its own
    airflow's, the same at every moment."""
    asked = RunRequest("tomato_compartment")
    air_at, _ = air_through_a_run(simulator, asked)
    _, climate = climate_run(simulator, asked)
    at = Vector3(x=12.0, y=8.0, z=1.5)

    assert [air_at(moment).sample(AirQuantity.TEMPERATURE, at) for moment in (0.0, DAY_S)] == [
        pytest.approx(20.7464, abs=1e-3)
    ] * 2
    assert climate.sampled("climate", DAY_S).sample(AirQuantity.TEMPERATURE, at) == pytest.approx(
        10.0
    )

    log = observations(simulator, RunRequest("sensor_lab"), until_s=HOUR_S)
    readings = [(o.sensor_id, o.timestamp.isoformat(), round(o.value, 6)) for o in log.observations]
    assert (log.run_id, len(readings)) == ("sensor_lab-gradient-0c377594", 177)
    assert short_digest(json.dumps(readings), 16) == READINGS_OF_THE_LAB


def test_a_models_version_changed_makes_another_run(
    simulator: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model whose numbers change for the same parameters has another
    version (decision 0054): its runs are other runs."""
    _, run_id = air_through_a_run(simulator, RunRequest("climate_box"))
    walks = MODELS[Part.CROP_WALK]
    monkeypatch.setitem(walks, WALK, dataclasses.replace(walks[WALK], version=2))

    _, other = air_through_a_run(simulator, RunRequest("climate_box"))

    assert other != run_id
    assert other.startswith("climate_box-climate-")
