"""The models a manifest chooses for each part of a run (P14.1, decision
0054): each part's models by name, its default the configuration's own, and
each model's parameters under a field of the configuration, the crop's of
the model its rows grow (P14.3)."""

import json

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import OrganCrop, SimpleCrop
from greenhouse_sim.scenarios.manifest_files import MANIFESTS_DIR
from greenhouse_sim.scenarios.registry import CONFIGURED, DEFAULTS, MODELS, chosen, model


def test_every_part_runs_a_model_it_has_when_a_manifest_names_none() -> None:
    assert set(MODELS) == set(DEFAULTS) == set(Part)
    for part, name in DEFAULTS.items():
        assert model(part, name).name == name
    # The configuration's own defaults are the default models'.
    fields = ScenarioConfig.model_fields
    assert fields["weather"].default.kind == DEFAULTS[Part.WEATHER]
    assert fields["airflow"].default.kind == DEFAULTS[Part.AIR_FIELD]
    assert fields["crop_model"].default == DEFAULTS[Part.CROP]
    assert fields["crop"].default.kind == DEFAULTS[Part.CROP]
    assert fields["crop_walk"].default.kind == DEFAULTS[Part.CROP_WALK]


def test_a_model_the_part_does_not_have_is_refused_naming_those_it_has() -> None:
    with pytest.raises(ValueError, match="the air_field has no model 'storm': its models are"):
        model(Part.AIR_FIELD, "storm")


def test_each_models_parameters_are_held_under_its_field_of_the_configuration() -> None:
    fields = ScenarioConfig.model_fields

    assert CONFIGURED == {"weather", "airflow", "crop", "crop_walk"}
    assert CONFIGURED <= set(fields)
    for models in MODELS.values():
        for each in models.values():
            assert each.parameters.model_fields["kind"].default == each.name
    with pytest.raises(ValidationError, match="water_capacity_ml"):
        SimpleCrop(water_capacity_ml=0)


def test_a_scenarios_crop_takes_the_parameters_of_the_model_its_rows_grow() -> None:
    simple = SCENARIO_REGISTRY["climate_box"]
    given = simple.model_dump(exclude={"crop"}) | {"crop_model": CropModel.ORGAN}

    organ = ScenarioConfig.model_validate(given)

    assert organ.crop == OrganCrop()
    # The engine's day grows the simple crop by its own settings in its place.
    assert organ.simple_crop == SimpleCrop()
    with pytest.raises(ValidationError, match="the simple crop's, but it grows the organ crop"):
        ScenarioConfig.model_validate(given | {"crop": {"kind": "simple"}})


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_REGISTRY))
def test_each_scenario_runs_the_models_its_manifest_names_or_the_defaults(
    scenario_id: str,
) -> None:
    document = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    config = SCENARIO_REGISTRY[scenario_id]
    named = {Part(part): section["model"] for part, section in document["models"].items()}
    rows = {Part.CROP: config.crop_model.value}

    assert chosen(config) == dict(DEFAULTS) | rows | named


def test_a_models_parameters_name_no_kind_but_its_section_does() -> None:
    weather = model(Part.WEATHER, "constant")

    read = weather.read({"air_temperature_c": 4.0})

    assert weather.written(read) == read.model_dump(mode="json", exclude={"kind"})
    assert weather.configured(read)["weather"] == read.model_dump(mode="json")
    with pytest.raises(ValueError, match="its kind is its model's name"):
        weather.read({"kind": "constant"})
