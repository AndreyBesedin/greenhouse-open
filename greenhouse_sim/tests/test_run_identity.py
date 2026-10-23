"""A run's identity (decision 0042): the same scenario, the same run id;
anything it is made of changed, its manifest or its layout, another, for a
scenario whose equipment drives its air and for one whose airflow is its
own."""

import pytest

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
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
