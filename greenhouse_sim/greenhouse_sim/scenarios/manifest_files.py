"""Scenarios as declarative files (P09.1, decision 0031).

Each scenario is a manifest, `manifests/<scenario id>.json` next to this
module: a `ScenarioConfig` (`greenhouse_sim.scenarios.config`) written as
JSON, with its layout named rather than written out, since the layouts are
files of their own (`layout_files`). Beside the configuration, a manifest
states the version of the format it is written in, which a reader refuses
if it does not know it, and may carry notes: what the scenario, or one of
its fields, is and why, which JSON has no comments for.

A manifest names the JSON Schema it follows, `scenario.schema.json` next to
this module, so an editor can check it while it is written; the simulator
checks it again when it reads it, refusing a field it does not know, at any
depth, rather than ignoring it.
"""

import hashlib
import json
from pathlib import Path
from typing import Final

from pydantic import JsonValue

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT, LAYOUT_NAME, load_layout

MANIFESTS_DIR: Final = Path(__file__).parent / "manifests"
MANIFEST_SCHEMA_FILE: Final = Path(__file__).parent / "scenario.schema.json"
# Where a manifest finds the schema, from the manifests' folder.
SCHEMA_FROM_A_MANIFEST_FILE: Final = "../scenario.schema.json"
# The JSON Schema dialect Pydantic generates, stated in the published schema.
JSON_SCHEMA_DIALECT: Final = "https://json-schema.org/draft/2020-12/schema"
# The version of the format a manifest is written in.
SCHEMA_VERSION: Final = 1
# How many hexadecimal digits of its content's digest name a manifest's
# version.
DIGEST_LENGTH: Final = 16
# The scenario listed first, the reference scenario (P09); the others
# follow by identifier.
FIRST_SCENARIO: Final = "reference_greenhouse"
# What a note may be about besides one of the configuration's fields.
WHOLE_SCENARIO: Final = "scenario"
# A manifest's fields that are not the configuration's.
_SCHEMA_KEY: Final = "$schema"
_VERSION_KEY: Final = "schema_version"
_NOTES_KEY: Final = "notes"
_LAYOUT_KEY: Final = "layout"


class InvalidManifest(ValueError):
    """A manifest the simulator cannot read as a scenario."""


def manifest_ids() -> list[str]:
    """The scenarios with a manifest, `FIRST_SCENARIO` first, then the others
    by identifier."""
    ids = sorted(path.stem for path in MANIFESTS_DIR.glob("*.json"))
    return sorted(ids, key=lambda scenario_id: scenario_id != FIRST_SCENARIO)


def load_manifest(scenario_id: str) -> ScenarioConfig:
    """A scenario, read from its manifest and checked."""
    path = MANIFESTS_DIR / f"{scenario_id}.json"
    return scenario_from_manifest(scenario_id, json.loads(path.read_text()))


def manifest_digest(scenario_id: str) -> str:
    """What tells one version of a scenario's manifest from another: a
    digest of its content, however its file is laid out."""
    document = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:DIGEST_LENGTH]


def scenario_from_manifest(scenario_id: str, document: dict[str, JsonValue]) -> ScenarioConfig:
    """The scenario a manifest describes, with its layout read from the file
    it names. Refused, with the reason, if the manifest is in a format this
    simulator does not read, names another scenario, notes a field it does
    not have, or has a field the configuration does not."""
    fields = {
        key: value
        for key, value in document.items()
        if key not in (_SCHEMA_KEY, _VERSION_KEY, _NOTES_KEY, _LAYOUT_KEY)
    }
    version = document.get(_VERSION_KEY)
    if version != SCHEMA_VERSION:
        raise InvalidManifest(
            f"{scenario_id}: a manifest in format {version!r}; this simulator reads "
            f"format {SCHEMA_VERSION}"
        )
    if fields.get("greenhouse_id") != scenario_id:
        raise InvalidManifest(
            f"{scenario_id}: its manifest describes {fields.get('greenhouse_id')!r}"
        )
    layout = document.get(_LAYOUT_KEY, DEFAULT_LAYOUT)
    if not isinstance(layout, str) or not LAYOUT_NAME.fullmatch(layout):
        raise InvalidManifest(f"{scenario_id}: a layout is named, not {layout!r}")
    notes = document.get(_NOTES_KEY, {})
    if not isinstance(notes, dict) or not all(isinstance(note, str) for note in notes.values()):
        raise InvalidManifest(f"{scenario_id}: notes are written by what each is about")
    unnoted = set(notes) - {WHOLE_SCENARIO, *ScenarioConfig.model_fields}
    if unnoted:
        raise InvalidManifest(f"{scenario_id}: notes on what it does not have: {sorted(unnoted)}")
    config = ScenarioConfig.model_validate(fields | {"layout": load_layout(scenario_id, layout)})
    unknown = _unknown_fields(fields, config.model_dump(mode="json", exclude={"layout"}))
    if unknown:
        raise InvalidManifest(f"{scenario_id}: fields it does not have: {', '.join(unknown)}")
    return config


def manifest_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema a manifest follows, published as
    `scenario.schema.json`: the configuration's, with its layout named, its
    format's version and its notes, and no field it does not have."""
    schema = ScenarioConfig.model_json_schema()
    properties = schema["properties"]
    properties[_LAYOUT_KEY] = {
        "type": "string",
        "pattern": f"^{LAYOUT_NAME.pattern}$",
        "default": DEFAULT_LAYOUT,
        "description": "The name of one of the scenario's layout files.",
    }
    properties[_SCHEMA_KEY] = {"type": "string"}
    properties[_VERSION_KEY] = {"const": SCHEMA_VERSION}
    properties[_NOTES_KEY] = {
        "type": "object",
        "additionalProperties": {"type": "string"},
        "description": "What the scenario, or one of its fields, is and why.",
    }
    schema["required"] = [_VERSION_KEY, *(name for name in schema["required"] if name != "layout")]
    schema["additionalProperties"] = False
    schema["$defs"] = _referenced(schema["$defs"], properties)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def _unknown_fields(written: JsonValue, read: JsonValue, path: str = "") -> list[str]:
    """Where a document has a field that what was read from it does not: a
    field the model would otherwise have ignored."""
    if isinstance(written, dict) and isinstance(read, dict):
        found: list[str] = []
        for key, value in written.items():
            where = f"{path}.{key}" if path else key
            found += [where] if key not in read else _unknown_fields(value, read[key], where)
        return found
    if isinstance(written, list) and isinstance(read, list):
        return [
            field
            for index, (item, read_item) in enumerate(zip(written, read, strict=False))
            for field in _unknown_fields(item, read_item, f"{path}[{index}]")
        ]
    return []


def _referenced(definitions: dict[str, JsonValue], within: JsonValue) -> dict[str, JsonValue]:
    """The definitions `within` refers to, directly or through one another:
    the layout's are left out, as a manifest only names it."""
    kept: dict[str, JsonValue] = {}
    waiting = [within]
    while waiting:
        node = waiting.pop()
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str):
                name = reference.removeprefix("#/$defs/")
                if name not in kept:
                    kept[name] = definitions[name]
                    waiting.append(definitions[name])
            waiting.extend(node.values())
        elif isinstance(node, list):
            waiting.extend(node)
    return {name: kept[name] for name in sorted(kept)}
