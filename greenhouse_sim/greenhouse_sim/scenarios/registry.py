"""The models a manifest chooses for the parts of a run (P14.1, decision
0054).

A part is what a run needs worked out. A model of it has a name, unique
within its part; a version, which changes whenever its numbers change for
the same parameters, so that a run's identity, which covers it (P14.2),
tells the runs apart; and a parameter model, which checks the section of a
manifest that gives its parameters. The registry holds each part's models
by name, with its default: the model a manifest that says nothing of the
part runs, today's choice. P14.1 registers the parts a manifest chose
already: the weather, the air field drawn, the crop and the crop walk's
measurements. The others follow (P14.6).

Until P14.3 moves them, a scenario's configuration (`ScenarioConfig`) holds
each model's parameters where it held them before: the weather's and the
air field's under a field of their own, told apart by their `kind`, which is
the model's name; the simple crop's and the crop walk's as fields at its
top. So the manifest's `models` change where a manifest writes a choice,
not what a run is: its configuration, and so its run's identity, stays the
one it was.

The crop's model is the one its rows grow (decision 0050): a manifest's
crop section gives that model's parameters, and names it as its rows do.
Until P14.3, either crop model's parameters are the simple crop's
settings: a scenario's live run grows the simple crop whatever its rows
grow (`services.live`), so a scenario of organ rows has them too.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, JsonValue, create_model

from greenhouse_sim.airflow.prescribed import (
    BuoyancyAirflow,
    GradientAirflow,
    UniformAirflow,
    VortexAirflow,
)
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.weather.recorded import RecordedWeather
from greenhouse_sim.weather.seasonal import SeasonalWeather
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.weather.synthetic import SyntheticWeather

# The field of a parameter model that a configuration's union tells its
# models apart by: the model's name.
KIND: Final = "kind"
# The simple crop's settings, and the engine's it runs in, which the
# configuration holds at its top until P14.3.
SIMPLE_CROP_FIELDS: Final = (
    "air_temperature_bounds",
    "humidity_bounds",
    "initial_water_reservoir_ml",
    "water_capacity_ml",
    "water_use_ml_per_day_base",
    "evaporation_ml_per_day",
    "water_stress_threshold_pct",
    "initial_stem_length_cm",
    "stem_growth_cm_per_day_base",
    "truss_interval_days",
    "max_trusses",
    "fruits_per_truss_bounds",
    "target_diameter_mm_bounds",
    "fruit_growth_days_to_target",
    "mass_coefficient_g_per_mm3",
    "ripening_days_bounds",
    "soil_moisture_noise_pct",
    "air_temperature_noise_c",
)
# The crop walk's measurement noises, which act on either crop's walk
# (`services.crop_log`).
WALK_FIELDS: Final = ("fruit_count_noise_probability", "ripe_mass_noise_pct", "height_noise_cm")
# The crop walk's one model.
WALK: Final = "walk"


def _the_configurations(name: str, fields: tuple[str, ...]) -> type[BaseModel]:
    """A parameter model of fields the configuration holds itself, as it
    has them: their types, bounds and defaults, written once."""
    held = ScenarioConfig.model_fields
    # Each field as `create_model` takes it: its type and its field.
    definitions: dict[str, Any] = {field: (held[field].annotation, held[field]) for field in fields}
    return create_model(name, __config__=ConfigDict(frozen=True, extra="forbid"), **definitions)


SimpleCrop: Final = _the_configurations("SimpleCrop", SIMPLE_CROP_FIELDS)
CropWalk: Final = _the_configurations("CropWalk", WALK_FIELDS)


@dataclass(frozen=True)
class Model:
    """A model of a part: its name, its parameters' model, where the
    configuration holds them (under `field`, with the model's name as their
    `kind`; or, with no field, as fields of its own), and its version."""

    part: Part
    name: str
    parameters: type[BaseModel]
    field: str | None = None
    version: int = 1

    def read(self, parameters: Mapping[str, JsonValue]) -> BaseModel:
        """Its parameters as a manifest's section gives them, checked:
        refused with their model's reason, or if they name its kind, which
        is the section's model."""
        if self.field is not None and KIND in parameters:
            raise ValueError(f"its {KIND} is its model's name, {self.name!r}")
        given = dict(parameters) | ({} if self.field is None else {KIND: self.name})
        return self.parameters.model_validate(given)

    def written(self, parameters: BaseModel) -> dict[str, JsonValue]:
        """Its parameters as a manifest's section writes them."""
        return parameters.model_dump(mode="json", exclude={KIND})

    def configured(self, parameters: BaseModel) -> dict[str, JsonValue]:
        """The configuration's fields its parameters are."""
        fields = parameters.model_dump(mode="json")
        return fields if self.field is None else {self.field: fields}


def _models(*models: Model) -> dict[str, Model]:
    return {model.name: model for model in models}


# Each part's models, by name.
MODELS: Final[Mapping[Part, Mapping[str, Model]]] = {
    Part.WEATHER: _models(
        Model(Part.WEATHER, "constant", ConstantWeather, "weather"),
        Model(Part.WEATHER, "synthetic", SyntheticWeather, "weather"),
        Model(Part.WEATHER, "seasonal", SeasonalWeather, "weather"),
        Model(Part.WEATHER, "recorded", RecordedWeather, "weather"),
    ),
    Part.AIR_FIELD: _models(
        Model(Part.AIR_FIELD, "uniform", UniformAirflow, "airflow"),
        Model(Part.AIR_FIELD, "buoyancy", BuoyancyAirflow, "airflow"),
        Model(Part.AIR_FIELD, "vortex", VortexAirflow, "airflow"),
        Model(Part.AIR_FIELD, "gradient", GradientAirflow, "airflow"),
    ),
    Part.CROP: _models(
        Model(Part.CROP, CropModel.SIMPLE.value, SimpleCrop),
        # The simple crop's settings, by which the scenario's live run grows
        # the simple crop (P14.3 moves them); its variety is its rows'.
        Model(Part.CROP, CropModel.ORGAN.value, SimpleCrop),
    ),
    Part.CROP_WALK: _models(Model(Part.CROP_WALK, WALK, CropWalk)),
}

# The model each part runs when a manifest says nothing of it: the
# configuration's own default. The crop's is the one its rows grow.
DEFAULTS: Final[Mapping[Part, str]] = {
    Part.WEATHER: "constant",
    Part.AIR_FIELD: "uniform",
    Part.CROP: CropModel.SIMPLE.value,
    Part.CROP_WALK: WALK,
}

# The configuration's fields that a part's models hold their parameters
# in, which a manifest writes in its `models` instead.
CONFIGURED: Final = frozenset(
    {"weather", "airflow", *SIMPLE_CROP_FIELDS, *WALK_FIELDS},
)


def model(part: Part, name: str) -> Model:
    """The model of `part` named `name`; refused, naming the part's
    models, if it has none of that name."""
    found = MODELS[part].get(name)
    if found is None:
        known = ", ".join(MODELS[part])
        raise ValueError(f"the {part} has no model {name!r}: its models are {known}")
    return found


class ModelRun(BaseModel):
    """A part's model as a run runs it: its name and version."""

    model_config = ConfigDict(frozen=True)

    model: str
    version: int


def models_run(config: ScenarioConfig) -> dict[Part, ModelRun]:
    """The model and version a scenario runs for each part: what a run's
    identity covers of its models, beside its parameters (P14.2)."""
    return {
        part: ModelRun(model=name, version=model(part, name).version)
        for part, name in chosen(config).items()
    }


def chosen(config: ScenarioConfig) -> dict[Part, str]:
    """The model a scenario runs for each part, by name."""
    return {
        Part.WEATHER: config.weather.kind,
        Part.AIR_FIELD: config.airflow.kind,
        Part.CROP: config.crop_model.value,
        Part.CROP_WALK: WALK,
    }


# How a schema points to a definition of its own.
_DEFINITION: Final = "#/$defs/{model}"


def models_json_schema() -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    """The JSON Schema of a manifest's `models`, and the definitions it
    uses, by name: for each part, a section naming one of its models and
    giving that model's parameters, its kind left out, as its name says
    it; required if the model has one with no default, as the recorded
    weather's file."""
    definitions: dict[str, JsonValue] = {}
    parts: dict[str, JsonValue] = {}
    for part, models in MODELS.items():
        sections: list[JsonValue] = []
        for entry in models.values():
            schema = entry.parameters.model_json_schema(ref_template=_DEFINITION)
            definitions |= schema.pop("$defs", {})
            schema["properties"].pop(KIND, None)
            definitions[entry.parameters.__name__] = schema
            needed: list[JsonValue] = (
                ["model", "parameters"] if schema.get("required") else ["model"]
            )
            sections.append(
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": needed,
                    "properties": {
                        "model": {"const": entry.name},
                        "parameters": {"$ref": _DEFINITION.format(model=entry.parameters.__name__)},
                    },
                }
            )
        default = (
            "the one its rows grow" if part is Part.CROP else f"{DEFAULTS[part]!r} if none is named"
        )
        parts[part] = {"oneOf": sections, "description": f"The {_said(part)}'s model: {default}."}
    every_part: dict[str, JsonValue] = {
        "type": "object",
        "additionalProperties": False,
        "properties": parts,
        "description": "The model each part of a run runs, by part, and its parameters.",
    }
    return every_part, definitions


def _said(part: Part) -> str:
    """A part as a sentence says it: the air field, the crop walk."""
    return part.value.replace("_", " ")
