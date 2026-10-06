"""Scenario layouts as declarative files.

Each scenario's layouts live in `layouts/<scenario id>/<name>.json` next to
this module: a `Layout` (`greenhouse_sim.world.layout`) written as JSON.
`default` is the layout the scenario is defined with; others are
alternatives for the same greenhouse, which the local API can show in its
place (`?layout=<name>`) without a change to any code. A file names the
JSON Schema it follows, `layout.schema.json` next to this module, so an
editor can check it while it is written; the simulator checks it again when
it reads it, refusing a field it does not know.
"""

import json
import re
from pathlib import Path
from typing import Final

from pydantic import JsonValue

from greenhouse_sim.world.layout import Layout

LAYOUTS_DIR: Final = Path(__file__).parent / "layouts"
LAYOUT_SCHEMA_FILE: Final = Path(__file__).parent / "layout.schema.json"
DEFAULT_LAYOUT: Final = "default"
# A layout's name, as a file name and in an address: lower case, digits and
# underscores, so that it can never reach outside its scenario's folder.
LAYOUT_NAME: Final = re.compile(r"[a-z0-9_]+")
# The JSON Schema dialect Pydantic generates, stated in the published schema.
JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"
# Where a layout file finds the schema, from its scenario's folder.
SCHEMA_FROM_A_LAYOUT_FILE: Final = "../../layout.schema.json"


def layout_names(scenario_id: str) -> list[str]:
    """The names of a scenario's layouts, its default first."""
    folder = LAYOUTS_DIR / scenario_id
    names = sorted(path.stem for path in folder.glob("*.json")) if folder.is_dir() else []
    return sorted(names, key=lambda name: name != DEFAULT_LAYOUT)


def load_layout(scenario_id: str, name: str = DEFAULT_LAYOUT) -> Layout:
    """A scenario's layout, read from its file and checked."""
    if not LAYOUT_NAME.fullmatch(name) or name not in layout_names(scenario_id):
        raise KeyError(f"{scenario_id} has no layout {name!r}")
    document = json.loads((LAYOUTS_DIR / scenario_id / f"{name}.json").read_text())
    document.pop("$schema", None)
    return Layout.model_validate(document)


def layout_document(layout: Layout) -> dict[str, JsonValue]:
    """A layout as its file holds it: every field it sets, naming its schema."""
    fields = layout.model_dump(mode="json", exclude_none=True)
    return {"$schema": SCHEMA_FROM_A_LAYOUT_FILE, **fields}


def layout_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema a layout file follows, published as
    `layout.schema.json`."""
    schema = Layout.model_json_schema()
    # A file names its schema; the model ignores the name.
    schema.setdefault("properties", {})["$schema"] = {"type": "string"}
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}
