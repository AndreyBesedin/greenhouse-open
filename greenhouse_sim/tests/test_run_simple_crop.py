"""The simple crop as a rung of the run (P14.3): a scenario whose rows grow
it grows it in its run's air, draws it with its numbers, and keeps it in a
checkpoint, which a run of another crop model refuses."""

from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.core.crop import OrganRung
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import checkpoints
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.crop import of_organs, of_plants, scenario_crop
from greenhouse_sim.services.crop_models import SimpleCropState
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import plant_ids
from greenhouse_sim.services.simulator import Simulator

# Each test starts with no run, crop or checkpoint kept.
pytestmark = pytest.mark.usefixtures("afresh")

SCENARIO = "climate_box"
RUN = RunRequest(SCENARIO)
PLANTS = plant_ids(SCENARIO_REGISTRY[SCENARIO])


def test_its_run_grows_its_simple_crop_a_day_at_a_time_in_its_air(simulator: Simulator) -> None:
    crop = scenario_crop(simulator, RUN)
    _, climate = climate_run(simulator, RUN)

    assert of_plants(crop) and not of_organs(crop)
    assert [plant.plant_id for plant in crop.plants_on(3)] == PLANTS
    assert {plant.plant.age_days for plant in crop.plants_on(3)} == {3}
    for day in range(3):
        air = climate.house.mean_between(day * DAY_S, (day + 1) * DAY_S)
        assert crop.local(PLANTS[0], day).mean_temperature_c == air.temperature_c
    assert all(
        later.standing_cm() > first.standing_cm()
        for first, later in zip(crop.plants_on(0), crop.plants_on(3), strict=True)
    )


def test_its_crop_is_drawn_as_it_stands_with_its_numbers(simulator: Simulator) -> None:
    response = respond(simulator, "GET", f"/api/scenarios/{SCENARIO}/crop?t={3 * DAY_S:.0f}")

    assert response.status == HTTPStatus.OK, response.body
    body: Any = response.body
    crop = scenario_crop(simulator, RUN)
    assert of_plants(crop) and not of_organs(crop)
    plants = crop.plants_on(3)
    assert body["simulated_day"] == 3
    assert [entity["entity_id"] for entity in body["entities"]] == PLANTS
    first = body["entities"][0]
    assert first["kind"] == "PLANT"
    assert first["properties"]["age_days"] == 3
    assert first["properties"]["visible_height_cm"] == plants[0].standing_cm()
    assert first["shape"]["height"] == pytest.approx(plants[0].standing_cm() / 100.0)


def _saved(simulator: Simulator, day: int = 2) -> dict[str, Any]:
    saved = checkpoints.save_checkpoint(simulator, RUN, time_s=day * DAY_S)
    return checkpoints.checkpoint(simulator, saved.checkpoint_id).model_dump(mode="json")


def test_a_checkpoint_keeps_its_simple_crop_and_a_run_carries_on_from_it(
    simulator: Simulator, afresh: Callable[[], None]
) -> None:
    document = _saved(simulator)
    crop = scenario_crop(simulator, RUN)
    assert of_plants(crop)
    kept = checkpoints.read_checkpoint(document)

    assert isinstance(kept.crop, SimpleCropState)
    assert kept.crop.plants == list(crop.plants_on(2))
    assert kept.crop.lived == crop.lived_through(2)
    assert document["models"]["crop"]["model"] == "simple"
    assert document["models"]["crop"]["version"] == 2

    afresh()
    checkpoints.upload_checkpoint(simulator, document)

    # The run made again takes its plants on its day over from it.
    restored = scenario_crop(simulator, RUN)
    assert of_plants(restored)
    assert restored.plants_on(2) == tuple(kept.crop.plants)
    assert restored.plants_on(4) == crop.plants_on(4)


def test_a_checkpoint_of_a_simple_plant_older_than_its_day_is_refused(
    simulator: Simulator,
) -> None:
    document = _saved(simulator)
    document["models"]["crop"]["state"]["plants"][0]["plant"]["age_days"] = 3

    with pytest.raises(InvalidRequest, match=f"{PLANTS[0]} is 3 days old on day 2"):
        checkpoints.upload_checkpoint(simulator, document)


@pytest.mark.parametrize(
    ("crop", "said"),
    [
        (
            {"model": "organ", "version": 1},
            "made with the organ model of the crop, version 1: its run's is the simple model",
        ),
        # Made before its runs grew it (P14.3), with no plants kept.
        (
            {"model": "simple", "version": 1},
            "made with the simple model of the crop, version 1: its run's is the simple "
            "model, version 2",
        ),
    ],
)
def test_a_checkpoint_of_another_crop_model_or_version_is_refused_naming_the_crop(
    simulator: Simulator, crop: dict[str, Any], said: str
) -> None:
    document = _saved(simulator)
    document["models"]["crop"] = crop

    with pytest.raises(InvalidRequest, match=said):
        checkpoints.upload_checkpoint(simulator, document)


def test_a_checkpoint_of_the_simple_crop_keeping_another_models_plants_is_refused(
    simulator: Simulator,
) -> None:
    """Its state is read as its crop's model keeps it: the organ crop's
    transplants, under its plants' names, are not the simple crop's."""
    document = _saved(simulator, day=0)
    organ = OrganRung(SCENARIO_REGISTRY[SCENARIO].random_seed)
    document["models"]["crop"]["state"]["plants"] = [
        organ.transplant(plant_id).model_dump(mode="json") for plant_id in PLANTS
    ]

    with pytest.raises(InvalidRequest, match="not a checkpoint"):
        checkpoints.upload_checkpoint(simulator, document)


def test_a_checkpoint_of_a_simple_plant_without_its_fruits_values_is_refused(
    simulator: Simulator,
) -> None:
    """Its next day reads them: kept without them, the crop could not live
    it."""
    document = _saved(simulator, day=8)
    plant = document["models"]["crop"]["state"]["plants"][0]
    fruit = plant["plant"]["trusses"][0]["fruits"][0]["fruit_id"]
    del plant["fruits"][fruit]

    with pytest.raises(InvalidRequest, match=f"keeps no values for its fruit {fruit}"):
        checkpoints.upload_checkpoint(simulator, document)
