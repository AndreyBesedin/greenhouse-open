"""A crop model's parameter set as a file (P20.2, decision 0077).

A set names its model, by its registered name; a name and a version, for
people; the set it is based on, by name, version and digest, or none; the
values it changes from its base, by its model's parameters' fields, each
with why; the version of its model it was made for; the cultivar it was
made for, where its source names one; and a description.

- **Read** (`read_parameter_set`): the file's form; its model one that has
  sets; each value a parameter of that model's, with why; a fixed
  parameter at its published value; and a set based on none giving every
  value.
- **Resolved** (`resolved`), against its base, among the published sets
  and those given: its base's values with its own over them, each within
  its range and each ordered pair in order, as the model's parameters
  check them; and its digest, of its model's name and those values.
- **Compared** (`compared`) with another set of its model, parameter by
  parameter.

The published sets are each model's defaults, version 1, under the name its
crop section gives, based on none (`PUBLISHED_SETS`). A refusal says what is
wrong by field (`InvalidParameterSet.problems`).
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    JsonValue,
    PositiveInt,
    StringConstraints,
    ValidationError,
)

from greenhouse_sim.biology.parameter_fields import fixed_parameters, parameter_sources
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.scenarios.registry import model

# A set's name: lower-case letters, digits and underscores.
SET_NAME: Final = r"^[a-z0-9][a-z0-9_]*$"
# A set's digest: the whole SHA-256, in hexadecimal, under its scheme.
DIGEST_SCHEME: Final = "sha256:"
SET_DIGEST: Final = r"^sha256:[0-9a-f]{64}$"
# The version a set's first is, a published set's included.
FIRST_VERSION: Final = 1
# The parameters of each crop model that has sets, by its registered name.
PARAMETER_MODELS: Final[Mapping[str, type[BaseModel]]] = {
    CropModel.REDUCED_TOMGRO.value: TomgroParameters,
    CropModel.VANTHOOR_KATZIN.value: VanthoorParameters,
}
# Each one's published set: the name its crop section gives it, and what it is.
PUBLISHED_NAMES: Final = {
    CropModel.REDUCED_TOMGRO.value: "gnvman",
    CropModel.VANTHOOR_KATZIN.value: "greenlight_2_0_7",
}
PUBLISHED_DESCRIPTIONS: Final = {
    CropModel.REDUCED_TOMGRO.value: (
        "Reduced-State TOMGRO's published parameters: Oliveira et al.'s set gnvman and inputs"
        " gnv_n01 (release v0.4.0), as its reproduction runs them (decision 0060)."
    ),
    CropModel.VANTHOOR_KATZIN.value: (
        "Vanthoor's model's published parameters: GreenLight 2.0.7's crop definition and its"
        " standalone extension's, as its reproduction runs them (decision 0060)."
    ),
}

Why = Annotated[str, StringConstraints(min_length=1)]


class InvalidParameterSet(ValueError):
    """A set refused, with what is wrong by field, such as
    `parameters.sla` or `based_on.digest`; `""` for the set as a whole."""

    def __init__(self, problems: Mapping[str, str]) -> None:
        self.problems = dict(problems)
        super().__init__(
            "; ".join(f"{field}: {why}" if field else why for field, why in problems.items())
        )


class SetNamed(BaseModel):
    """A set as another names it: its name, its version and its digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=SET_NAME)
    version: PositiveInt
    digest: str = Field(pattern=SET_DIGEST)


class ParameterSet(BaseModel):
    """A crop model's parameter set, as its file gives it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = Field(description="The crop model it is a set of, by its registered name.")
    name: str = Field(pattern=SET_NAME, description="What a person calls it.")
    version: PositiveInt = Field(description="Its version under its name, from 1.")
    based_on: SetNamed | None = Field(
        description="The set it starts from, by name, version and digest; none for a set that"
        " gives every value."
    )
    parameters: dict[str, FiniteFloat] = Field(
        description="The values it changes from its base, by its model's parameters' fields."
    )
    why: dict[str, Why] = Field(
        description="Where each value it changes comes from, by the same fields."
    )
    made_for: PositiveInt = Field(description="The version of its model it was made with.")
    cultivar: str | None = Field(
        description="The cultivar it was made for; none where its source names none."
    )
    description: str = ""


@dataclass(frozen=True)
class ResolvedSet:
    """A set with every value it resolves to, checked, and its digest."""

    parameter_set: ParameterSet
    values: BaseModel
    digest: str

    @property
    def named(self) -> SetNamed:
        """The set as another, based on it, names it."""
        return SetNamed(
            name=self.parameter_set.name, version=self.parameter_set.version, digest=self.digest
        )


class ParameterChange(BaseModel):
    """A parameter whose values two sets give apart."""

    model_config = ConfigDict(frozen=True)

    name: str
    first: float
    second: float


# A set as the sets it may be based on are looked up: its model, its name and
# its version.
SetKey = tuple[str, str, int]


def read_parameter_set(document: Mapping[str, JsonValue]) -> ParameterSet:
    """A set's file, read and checked as it stands, without its base:
    refused, by field, if it is not a set (`_problems`)."""
    try:
        read = ParameterSet.model_validate(document)
    except ValidationError as error:
        raise InvalidParameterSet(_by_field(error)) from error
    problems = _problems(read)
    if problems:
        raise InvalidParameterSet(problems)
    return read


def resolved(
    parameter_set: ParameterSet, known: Mapping[SetKey, ParameterSet] | None = None
) -> ResolvedSet:
    """`parameter_set` with every value it resolves to: its base's, looked
    up among the published sets and `known`, with its own over them. Refused,
    by field, if a set of its line is not a set, its base is not known or
    not the digest it names, or its values are not its model's."""
    sets = dict(known or {}) | {_key(published): published for published in PUBLISHED_SETS.values()}
    return _resolved(parameter_set, sets, frozenset())


def compared(first: ResolvedSet, second: ResolvedSet) -> list[ParameterChange]:
    """The parameters two sets of one model give apart, in their model's
    order. Refused if they are sets of different models."""
    first_model, second_model = first.parameter_set.model, second.parameter_set.model
    if first_model != second_model:
        raise InvalidParameterSet(
            {"model": f"{first_model} and {second_model} are sets of different models"}
        )
    first_values, second_values = first.values.model_dump(), second.values.model_dump()
    return [
        ParameterChange(name=name, first=value, second=second_values[name])
        for name, value in first_values.items()
        if value != second_values[name]
    ]


def set_digest(model_name: str, values: BaseModel) -> str:
    """What tells a set's numbers apart: the SHA-256 of the canonical JSON
    (sorted keys, no spaces) of its model's name and every value it resolves
    to, whole, under its scheme."""
    canonical = json.dumps(
        {"model": model_name, "parameters": values.model_dump()},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return DIGEST_SCHEME + hashlib.sha256(canonical.encode()).hexdigest()


def published_set(model_name: str) -> ParameterSet:
    """A model's published set: its defaults, version 1, based on none, each
    value's why its source, made for the model's version."""
    parameters = PARAMETER_MODELS[model_name]
    return ParameterSet(
        model=model_name,
        name=PUBLISHED_NAMES[model_name],
        version=FIRST_VERSION,
        based_on=None,
        parameters=parameters().model_dump(),
        why=parameter_sources(parameters),
        made_for=model(Part.CROP, model_name).version,
        cultivar=None,
        description=PUBLISHED_DESCRIPTIONS[model_name],
    )


# Each model's published set, by its model's name.
PUBLISHED_SETS: Final = {name: published_set(name) for name in PARAMETER_MODELS}


def parameter_set_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema of a set's file: its fields, and for each model its
    parameters, each with its unit, source and range, any of them given."""
    schema = ParameterSet.model_json_schema()
    definitions = schema.setdefault("$defs", {})
    cases: list[JsonValue] = []
    for name, parameters in PARAMETER_MODELS.items():
        definitions[parameters.__name__] = parameters.model_json_schema()
        cases.append(
            {
                "properties": {
                    "model": {"const": name},
                    "parameters": {"$ref": f"#/$defs/{parameters.__name__}"},
                }
            }
        )
    schema["properties"]["model"]["enum"] = list(PARAMETER_MODELS)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema, "oneOf": cases}


def _key(parameter_set: ParameterSet) -> SetKey:
    return parameter_set.model, parameter_set.name, parameter_set.version


def _resolved(
    parameter_set: ParameterSet, sets: Mapping[SetKey, ParameterSet], below: frozenset[SetKey]
) -> ResolvedSet:
    """`resolved`, `below` the sets based on this one, which its line may not
    come back to."""
    problems = _problems(parameter_set)
    if problems:
        raise InvalidParameterSet(problems)
    key = _key(parameter_set)
    based_on = parameter_set.based_on
    base_values: dict[str, float] = {}
    if based_on is not None:
        base_key = (parameter_set.model, based_on.name, based_on.version)
        if base_key in below | {key}:
            raise InvalidParameterSet({"based_on": "its line of bases comes back to it"})
        base = sets.get(base_key)
        if base is None:
            raise InvalidParameterSet(
                {
                    "based_on": f"no set {based_on.name} v{based_on.version} of"
                    f" {parameter_set.model} is known"
                }
            )
        base_resolved = _resolved(base, sets, below | {key})
        if base_resolved.digest != based_on.digest:
            raise InvalidParameterSet(
                {
                    "based_on.digest": f"{based_on.name} v{based_on.version}'s digest is"
                    f" {base_resolved.digest}, not {based_on.digest}"
                }
            )
        base_values = base_resolved.values.model_dump()
    parameters = PARAMETER_MODELS[parameter_set.model]
    try:
        values = parameters.model_validate(base_values | parameter_set.parameters)
    except ValidationError as error:
        raise InvalidParameterSet(_by_field(error, "parameters")) from error
    return ResolvedSet(parameter_set, values, set_digest(parameter_set.model, values))


def _problems(parameter_set: ParameterSet) -> dict[str, str]:
    """What makes a read set no set, by field: a model with no sets; a value
    of no parameter of its model's, or that its model fixes at another; a
    value changed without why, or a why of none changed; or, based on none,
    a value missing."""
    parameters = PARAMETER_MODELS.get(parameter_set.model)
    if parameters is None:
        return {
            "model": f"{parameter_set.model!r} has no parameter sets: those that have are"
            f" {', '.join(PARAMETER_MODELS)}"
        }
    fields = parameters.model_fields
    published = parameters().model_dump()
    fixed = fixed_parameters(parameters)
    problems: dict[str, str] = {}
    for name, value in parameter_set.parameters.items():
        if name not in fields:
            problems[f"parameters.{name}"] = f"not a parameter of {parameter_set.model}"
        elif name in fixed and value != published[name]:
            problems[f"parameters.{name}"] = f"fixed at {published[name]:g}: no set changes it"
        if name not in parameter_set.why:
            problems[f"why.{name}"] = "a value it changes says where it comes from"
    for name in parameter_set.why.keys() - parameter_set.parameters.keys():
        problems[f"why.{name}"] = "says where a value comes from that the set does not change"
    missing = [name for name in fields if name not in parameter_set.parameters]
    if parameter_set.based_on is None and missing:
        problems["parameters"] = f"a set based on none gives every value: {', '.join(missing)}"
    return problems


def _by_field(error: ValidationError, under: str = "") -> dict[str, str]:
    """A validation's errors by the field each is of, `under` a field of the
    set's; `under` itself for one of the whole."""
    problems: dict[str, str] = {}
    for found in error.errors():
        field = ".".join([under, *map(str, found["loc"])] if under else map(str, found["loc"]))
        problems[field] = "; ".join(filter(None, [problems.get(field), found["msg"]]))
    return problems
