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
measurements. P14.6 registers the others: the sunlight and the sensors,
each with the one model it has, which takes no parameters; the house's
air, as one well-mixed volume or cell by cell beside it; and the
controller, its loops or none.

A scenario's configuration (`ScenarioConfig`) holds each model's
parameters under a field of its own, told apart by their `kind`, which is
the model's name: the weather's under `weather`, the air field's under
`airflow`, the crop's under `crop`, the crop walk's under `crop_walk`
(P14.3), the house air's under `climate` and the controller's loops under
`control` (P14.6). The crop's model is the one its rows grow (decision 0050): a
manifest's crop section gives that model's parameters, and names it as its
rows do.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue

from greenhouse_sim.airflow.prescribed import (
    BuoyancyAirflow,
    GradientAirflow,
    UniformAirflow,
    VortexAirflow,
)
from greenhouse_sim.climate.control import Control
from greenhouse_sim.climate.settings import GridAir, WholeHouseAir
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import RETIRED, WALK, CropWalk, OrganCrop, SimpleCrop
from greenhouse_sim.weather.recorded import RecordedWeather
from greenhouse_sim.weather.seasonal import SeasonalWeather
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.weather.synthetic import SyntheticWeather

# The field of a parameter model that a configuration's union tells its
# models apart by: the model's name.
KIND: Final = "kind"
# The sunlight's one model, and the sensors'.
SUNLIGHT: Final = "haurwitz_erbs"
SAMPLED: Final = "sampled"
# The house air's two models.
GRID: Final = "grid"
WHOLE_HOUSE: Final = "whole_house"
# The controller's two models.
LOOPS: Final = "loops"
NO_CONTROLLER: Final = "none"


class NoParameters(BaseModel):
    """The parameters of a model that takes none."""

    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class Model:
    """A model of a part: its name, its parameters' model, the field of the
    configuration that holds them, with the model's name as their `kind`,
    none for a model that takes no parameters, its version, and the
    parameters it no longer has, which a manifest written before may still
    give and which its parameters' model drops."""

    part: Part
    name: str
    parameters: type[BaseModel] = NoParameters
    field: str | None = None
    version: int = 1
    retired: frozenset[str] = frozenset()

    def read(self, parameters: Mapping[str, JsonValue]) -> BaseModel:
        """Its parameters as a manifest's section gives them, checked:
        refused with their model's reason, or if they name its kind, which
        is the section's model."""
        if KIND in parameters:
            raise ValueError(f"its {KIND} is its model's name, {self.name!r}")
        named = {} if self.field is None else {KIND: self.name}
        return self.parameters.model_validate(dict(parameters) | named)

    def written(self, parameters: BaseModel) -> dict[str, JsonValue]:
        """Its parameters as a manifest's section writes them."""
        return parameters.model_dump(mode="json", exclude={KIND})

    def configured(self, parameters: BaseModel) -> dict[str, JsonValue]:
        """The configuration's field its parameters are; none for a model
        that takes no parameters."""
        return {} if self.field is None else {self.field: parameters.model_dump(mode="json")}


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
        # 2: grown in the run, from its air, rather than in the engine's day
        # alone (P14.3).
        Model(
            Part.CROP,
            CropModel.SIMPLE.value,
            SimpleCrop,
            "crop",
            version=2,
            retired=frozenset(RETIRED),
        ),
        Model(Part.CROP, CropModel.ORGAN.value, OrganCrop, "crop"),
    ),
    Part.CROP_WALK: _models(Model(Part.CROP_WALK, WALK, CropWalk, "crop_walk")),
    # The sun placed and the sky's light after Haurwitz, split into beam and
    # diffuse after Erbs, through the glazing and the shadows of what stands
    # in the house (`greenhouse_sim.solar`).
    Part.SUNLIGHT: _models(Model(Part.SUNLIGHT, SUNLIGHT)),
    # Each point sensor sampling the run's air where it stands, with its
    # own imperfections, and the weather station the weather
    # (`greenhouse_sim.sensors.air`).
    Part.SENSORS: _models(Model(Part.SENSORS, SAMPLED)),
    # The house's air cell by cell beside the whole house, or the whole
    # house alone (`greenhouse_sim.climate.day`).
    Part.HOUSE_AIR: _models(
        Model(Part.HOUSE_AIR, GRID, GridAir, "climate"),
        Model(Part.HOUSE_AIR, WHOLE_HOUSE, WholeHouseAir, "climate"),
    ),
    # Loops that each switch devices by one quantity of the house's air, in
    # steps, with hysteresis (P11, `greenhouse_sim.climate.control`), or no
    # controller: the devices run by their commands alone.
    Part.CONTROLLER: _models(
        Model(Part.CONTROLLER, LOOPS, Control, "control"),
        Model(Part.CONTROLLER, NO_CONTROLLER),
    ),
}

# The model each part runs when a manifest says nothing of it: the
# configuration's own default. The crop's is the one its rows grow.
DEFAULTS: Final[Mapping[Part, str]] = {
    Part.WEATHER: "constant",
    Part.AIR_FIELD: "uniform",
    Part.CROP: CropModel.SIMPLE.value,
    Part.CROP_WALK: WALK,
    Part.SUNLIGHT: SUNLIGHT,
    Part.SENSORS: SAMPLED,
    Part.HOUSE_AIR: GRID,
    Part.CONTROLLER: NO_CONTROLLER,
}

# The configuration's fields that a part's models hold their parameters
# in, which a manifest writes in its `models` instead.
CONFIGURED: Final = frozenset(
    {model.field for models in MODELS.values() for model in models.values() if model.field}
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
        Part.CROP: config.crop.kind,
        Part.CROP_WALK: config.crop_walk.kind,
        # Each the one model it has.
        Part.SUNLIGHT: SUNLIGHT,
        Part.SENSORS: SAMPLED,
        Part.HOUSE_AIR: config.climate.kind,
        Part.CONTROLLER: NO_CONTROLLER if config.control is None else config.control.kind,
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
            schema.setdefault("properties", {}).pop(KIND, None)
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
