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
    is sent (`_AsAnswered`)."""
    schema = _without_discriminators(
        TypeAdapter(answered).json_schema(mode="serialization", schema_generator=_AsAnswered)
    )
    assert isinstance(schema, dict)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def _without_discriminators(value: JsonValue) -> JsonValue:
    """A schema without OpenAPI's `discriminator` keyword, with which Pydantic
    marks a tagged union: it is not JSON Schema, and the `oneOf` and each
    case's constant tag already say the same."""
    if isinstance(value, dict):
        return {
            key: _without_discriminators(item)
            for key, item in value.items()
            if not (key == "discriminator" and isinstance(item, dict) and "propertyName" in item)
        }
    if isinstance(value, list):
        return [_without_discriminators(item) for item in value]
    return value
