"""How the simulator publishes a JSON Schema (audit W13, `AUDIT.9`): in
the 2020-12 dialect, which Pydantic generates and each schema names as its
`$schema`, and written to its file one way. `tests/test_published_schemas.py` lists every
schema published, holds each committed file to its export, and writes them
all:

    python tests/test_published_schemas.py --update

A service's answer to the viewer is published by `answer_json_schema`, from
the type the service returns (audit W12, `AUDIT.8`).

This module imports nothing from the simulator, so any part may use it.
"""

import json
from collections.abc import Mapping
from typing import Final, override

from pydantic import JsonValue, TypeAdapter
from pydantic.json_schema import GenerateJsonSchema

JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"


def schema_text(schema: Mapping[str, object]) -> str:
    """A schema as its published file holds it: indented, its text as it
    is, and ending with a new line."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


class _AsAnswered(GenerateJsonSchema):
    """A schema of what `model_dump(mode="json")` writes, as a service's
    answer is sent: every field it always writes is required, its default
    included, so that a viewer never supplies one. A field left out when it
    is unset (`exclude_if`) stays optional."""

    @override
    def field_is_required(self, field: Mapping[str, object], total: bool) -> bool:
        return field.get("serialization_exclude_if") is None


def answer_json_schema(answered: type[object]) -> dict[str, JsonValue]:
    """The JSON Schema a viewer validates a service's answer against: of the
    type the service returns, a model or a list or mapping of models, as it
    is sent (`_AsAnswered`), in JSON Schema's own keywords."""
    schema = _only_json_schema(
        TypeAdapter(answered).json_schema(mode="serialization", schema_generator=_AsAnswered)
    )
    assert isinstance(schema, dict)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


# What a field's schema says for people beside JSON Schema's own keywords,
# as a crop model's parameters and a material's properties do (P20.1,
# P24.2): its unit, its value's source, where its range's ends come from,
# and why no set may change it. A validator that holds to JSON Schema, as
# the viewer's does, refuses a keyword it does not know, so an answer's
# schema leaves them out; a file's schema keeps them.
FOR_PEOPLE: Final = frozenset({"unit", "source", "range_from", "fixed"})
# The keywords whose value maps names to schemas: a property or a
# definition may be called as a keyword is.
_NAMING: Final = frozenset({"properties", "patternProperties", "$defs"})


def _only_json_schema(value: JsonValue, *, names: bool = False) -> JsonValue:
    """A schema without what JSON Schema has no keyword for: OpenAPI's
    `discriminator`, with which Pydantic marks a tagged union, when the
    `oneOf` and each case's constant tag already say the same; and what a
    field's schema says for people (`FOR_PEOPLE`). A property or definition
    called as one of them is kept: `names` marks a mapping of them."""
    if isinstance(value, list):
        return [_only_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if names:
        return {name: _only_json_schema(item) for name, item in value.items()}
    return {
        key: _only_json_schema(item, names=key in _NAMING)
        for key, item in value.items()
        if key not in FOR_PEOPLE
        and not (key == "discriminator" and isinstance(item, dict) and "propertyName" in item)
    }
