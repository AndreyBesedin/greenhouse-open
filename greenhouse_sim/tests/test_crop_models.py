"""Each crop model is registered with all that tells it apart (decision
0055, P14.6): the registry's name, version and parameters, and, under the
same name, what the services ask of it, which every registration answers
as the services take it."""

from typing import Any

import pytest

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.registry import MODELS
from greenhouse_sim.services.crop_models import CROP_MODELS, CropRegistration, registration
from greenhouse_sim.services.scenarios import plant_ids

CONFIG = SCENARIO_REGISTRY["climate_box"]
PLANTS = plant_ids(CONFIG)[:2]
STEADY = LocalEnvironment(mean_temperature_c=22.0, par_mol_m2_day=20.0, co2_ppm=600.0)
# Long enough for the simple crop's fruit, and the organ crop's first truss.
DAYS = 40


def test_every_crop_model_of_the_registry_is_registered_for_the_services() -> None:
    assert set(CROP_MODELS) == set(MODELS[Part.CROP])
    for name, registered in CROP_MODELS.items():
        assert registered.name == name
    assert registration(CONFIG) is CROP_MODELS[CONFIG.crop.kind]


def _grown(registered: CropRegistration[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """Its transplants after `DAYS` days in `STEADY`, and what they lived."""
    rung = registered.rung(CONFIG)
    plants = [rung.transplant(plant_id) for plant_id in PLANTS]
    for _ in range(DAYS):
        plants = [rung.live_day(plant, STEADY) for plant in plants]
    return plants, [dict.fromkeys(PLANTS, STEADY) for _ in range(DAYS)]


@pytest.mark.parametrize("registered", list(CROP_MODELS.values()), ids=list(CROP_MODELS))
def test_a_registration_answers_what_the_services_ask_of_a_crop_model(
    registered: CropRegistration[Any],
) -> None:
    plants, lived = _grown(registered)

    # Its state, as a checkpoint keeps and reads it back, plausible on its
    # day, and not on another.
    state = registered.state(plants=plants, lived=lived)
    assert registered.state.model_validate_json(state.model_dump_json()) == state
    assert registered.implausible(state, DAYS) == []
    # Drawn, each plant in the scene; measured as a walk finds it.
    drawn = registered.drawn(plants, CONFIG)
    assert {entity.properties.get("plant_id", entity.entity_id) for entity in drawn} == set(PLANTS)
    measured = [registered.measured(plant) for plant in plants]
    assert [plant.plant_id for plant in measured] == PLANTS
    assert all(plant.height_cm > 0 and plant.fruits >= plant.ripe >= 0 for plant in measured)
    # A plant has picked nothing since itself; a replay counts its organs.
    assert [registered.picked(plant, plant, None) for plant in plants] == [(0, 0.0)] * 2
    organs, thermal_cd = registered.probed(plants)
    assert organs >= 0 and thermal_cd >= 0.0


def test_the_organs_registration_finds_what_no_run_of_it_reaches() -> None:
    plants, lived = _grown(CROP_MODELS["organ"])
    state = CROP_MODELS["organ"].state(plants=plants, lived=lived[1:])

    (problem, *_) = CROP_MODELS["organ"].implausible(state, DAYS)
    assert "thermal time" in problem
