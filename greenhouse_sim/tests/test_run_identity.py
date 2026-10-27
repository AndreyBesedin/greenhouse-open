"""A run's identity (decision 0042): the same scenario, the same run id;
anything it is made of changed, its manifest or its layout, another, for a
scenario whose equipment drives its air and for one whose airflow is its
own."""

import dataclasses
from urllib.parse import parse_qs

import pytest

from greenhouse_sim.api.routes.runs import run_request
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.crop_parameters import WALK
from greenhouse_sim.scenarios.registry import MODELS
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.simulator import Simulator


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
# the house's air and the controller are parts of their own (P14.6): the
# same requests must name the same runs, so that every record, replay and
# kept day made of them stands.
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
    ("climate_box", "", "climate_box-climate-2853918a"),
    ("climate_box", "set=fan:1&schedule=60:fan:0.5,30:heater:1", "climate_box-climate-5fabd70c"),
    (
        "climate_box",
        "daily=64800:heater:1,0:fan:1&schedule=0:fan:0",
        "climate_box-climate-68d14b6f",
    ),
    ("climate_box", "open=roof_vent:0.5&schedule=120:roof_vent:1", "climate_box-climate-4e97056f"),
    ("climate_box", "weather=cold_spring_day&set=heater:0.5", "climate_box-climate-894c5f7a"),
]


@pytest.mark.parametrize(("scenario_id", "query", "run_id"), PINNED_RUNS)
def test_a_run_asked_for_as_before_has_the_id_it_had(
    simulator: Simulator, scenario_id: str, query: str, run_id: str
) -> None:
    asked = run_request(scenario_id, parse_qs(query))

    assert air_through_a_run(simulator, asked)[1] == run_id


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
