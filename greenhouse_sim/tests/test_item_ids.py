"""The identifiers of a greenhouse's equipment, sensors and doors and vents
hold only what the API's parameters can carry (#254): letters, digits, `_`,
`.` and `-`, never the marks the parameters write them between."""

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import LAYOUT_SCHEMA_FILE
from greenhouse_sim.scenarios.manifest_files import MANIFEST_SCHEMA_FILE
from greenhouse_sim.world.identifiers import ITEM_ID_PATTERN

BOX = SCENARIO_REGISTRY["climate_box"]
# The marks the API's parameters write identifiers between, a space, and
# nothing at all.
REFUSED = ["temperature:north", "fan,left", "heater~1", "co2@front", "back sensor", ""]
TAKEN = ["temperature_front", "fan-2", "co2.left", "Heater1"]


def _items() -> list[tuple[BaseModel, str]]:
    """One of each kind of item the climate box has, with its identifier's
    field."""
    return [
        *((piece, "actuator_id") for piece in BOX.layout.equipment),
        *((sensor, "sensor_id") for sensor in BOX.layout.sensors),
        *((opening, "opening_id") for opening in BOX.envelope.openings),
    ]


def test_the_climate_box_has_an_item_of_each_kind() -> None:
    assert {field for _, field in _items()} == {"actuator_id", "sensor_id", "opening_id"}


@pytest.mark.parametrize("name", REFUSED)
def test_an_item_named_with_a_mark_or_nothing_is_refused(name: str) -> None:
    for item, field in _items():
        with pytest.raises(ValidationError, match=field):
            type(item).model_validate(item.model_dump() | {field: name})


@pytest.mark.parametrize("name", TAKEN)
def test_an_item_named_with_letters_digits_and_the_three_marks_is_taken(name: str) -> None:
    for item, field in _items():
        assert getattr(type(item).model_validate(item.model_dump() | {field: name}), field) == name


def _patterns(schema: Any, field: str) -> list[str | None]:
    """The pattern of every property `field` in a JSON Schema."""
    found: list[str | None] = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "properties" and isinstance(value, dict) and field in value:
                found.append(value[field].get("pattern"))
            found.extend(_patterns(value, field))
    elif isinstance(schema, list):
        for value in schema:
            found.extend(_patterns(value, field))
    return found


@pytest.mark.parametrize(
    ("schema_file", "field"),
    [
        (LAYOUT_SCHEMA_FILE, "actuator_id"),
        (LAYOUT_SCHEMA_FILE, "sensor_id"),
        (MANIFEST_SCHEMA_FILE, "opening_id"),
    ],
)
def test_the_published_schemas_name_the_pattern(schema_file: Any, field: str) -> None:
    patterns = _patterns(json.loads(schema_file.read_text()), field)
    assert patterns
    assert set(patterns) == {ITEM_ID_PATTERN}
