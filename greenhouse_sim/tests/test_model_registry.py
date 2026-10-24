"""The models a manifest chooses for each part of a run (P14.1, decision
0054): each part's models by name, its default the configuration's own, and
each model's parameters the configuration's fields, so that a manifest's
models change no run."""

import json

import pytest
from pydantic import ValidationError

from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.manifest_files import MANIFESTS_DIR
from greenhouse_sim.scenarios.registry import (
    CONFIGURED,
    DEFAULTS,
    MODELS,
    SIMPLE_CROP_FIELDS,
    WALK_FIELDS,
    CropWalk,
    SimpleCrop,
    chosen,
    model,
)


def test_every_part_runs_a_model_it_has_when_a_manifest_names_none() -> None:
    assert set(MODELS) == set(DEFAULTS) == set(Part)
    for part, name in DEFAULTS.items():
        assert model(part, name).name == name
    # The configuration's own defaults are the default models'.
    fields = ScenarioConfig.model_fields
    assert fields["weather"].default.kind == DEFAULTS[Part.WEATHER]
    assert fields["airflow"].default.kind == DEFAULTS[Part.AIR_FIELD]
    assert fields["crop_model"].default == DEFAULTS[Part.CROP]


def test_a_model_the_part_does_not_have_is_refused_naming_those_it_has() -> None:
    with pytest.raises(ValueError, match="the air_field has no model 'storm': its models are"):
        model(Part.AIR_FIELD, "storm")


def test_the_simple_crops_and_the_walks_parameters_are_the_configurations_fields() -> None:
    """Written once, in the configuration, with its types, bounds and
    defaults, until P14.3 moves them."""
    fields = ScenarioConfig.model_fields

    assert CONFIGURED == {"weather", "airflow", *SIMPLE_CROP_FIELDS, *WALK_FIELDS}
    assert CONFIGURED <= set(fields)
    assert SimpleCrop().model_dump() == {name: fields[name].default for name in SIMPLE_CROP_FIELDS}
    assert CropWalk().model_dump() == {name: fields[name].default for name in WALK_FIELDS}
    with pytest.raises(ValidationError, match="water_capacity_ml"):
        SimpleCrop(water_capacity_ml=0)


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
