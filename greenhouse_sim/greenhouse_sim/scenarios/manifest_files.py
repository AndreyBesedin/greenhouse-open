"""Scenarios as declarative files (P09.1, decision 0031).

Each scenario is a manifest, `manifests/<scenario id>.json` next to this
module: a `ScenarioConfig` (`greenhouse_sim.scenarios.config`) written as
JSON, its house held as an installation (`greenhouse_sim.scenarios.installation`,
decision 0050): its envelope, its layout, named rather than written out
since the layouts are files of their own (`layout_files`), and the crop
each row grows. Beside the configuration, a manifest
states the version of the format it is written in, which a reader refuses
if it does not know it, and may carry notes: what the scenario, or one of
its fields, is and why, which JSON has no comments for.

A manifest names the JSON Schema it follows, `scenario.schema.json` next to
this module, so an editor can check it while it is written; the simulator
checks it again when it reads it, refusing a field it does not know, at any
depth, rather than ignoring it.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Final

from pydantic import JsonValue

from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import (
    CannotRun,
    Installation,
    ScenarioHouse,
    scenario_house,
)
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT, LAYOUT_NAME, load_layout

MANIFESTS_DIR: Final = Path(__file__).parent / "manifests"
MANIFEST_SCHEMA_FILE: Final = Path(__file__).parent / "scenario.schema.json"
# Where a manifest finds the schema, from the manifests' folder.
SCHEMA_FROM_A_MANIFEST_FILE: Final = "../scenario.schema.json"
# The version of the format a manifest is written in: 4 since a manifest
# holds its house as an installation (P12.1, decision 0050).
SCHEMA_VERSION: Final = 4
# How many hexadecimal digits of its content's digest name a manifest's
# version.
DIGEST_LENGTH: Final = 16
# The scenario listed first, the reference scenario (P09); the others
# follow by identifier.
FIRST_SCENARIO: Final = "reference_greenhouse"
# What a note may be about besides one of the configuration's fields.
WHOLE_SCENARIO: Final = "scenario"
_SCHEMA_KEY: Final = "$schema"
_VERSION_KEY: Final = "schema_version"
_NOTES_KEY: Final = "notes"
_LAYOUT_KEY: Final = "layout"
_INSTALLATION_KEY: Final = "installation"
_OPENING_KEY: Final = "opening_day"
_THERMOSTAT_KEY: Final = "thermostat"
_CONTROL_KEY: Final = "control"
# What format 3 moved from a thermostat to the control: its day and night.
_CONTROL_TIMES: Final = frozenset({"day_from_s", "night_from_s"})
# What format 3 wrote of a scenario's house as fields of its own, which
# format 4 holds as its installation.
_FORMAT_3_HOUSE: Final = frozenset(ScenarioHouse.model_fields)
# What a format 3 note on one of those fields is about in format 4: the part
# of the installation the field became.
_FORMAT_3_NOTES: Final = {
    "envelope": "installation.envelope",
    "layout": "installation.layout",
    "rows": "installation.layout",
    "columns": "installation.layout",
    "crop_model": "installation.row_crops",
    "variety": "installation.row_crops",
}
# A manifest's fields that this module reads itself rather than handing them
# to `ScenarioConfig`, which could not read them as written: the schema, the
# format's version and the notes are about the file, not the greenhouse; the
# installation is read as one, its layout's own file read in place of its
# name, and gives the configuration its house; and the opening day is where
# a viewer opens the scenario's run, not part of its world.
_MANIFEST_ONLY_FIELDS: Final = frozenset(
    {_SCHEMA_KEY, _VERSION_KEY, _NOTES_KEY, _INSTALLATION_KEY, _OPENING_KEY}
)
# What a note may be about: the scenario, one of the manifest's fields, or a
# field of its installation, by its path (`installation.envelope`).
_NOTED: Final = frozenset(
    {WHOLE_SCENARIO, _OPENING_KEY, _INSTALLATION_KEY}
    | (set(ScenarioConfig.model_fields) - _FORMAT_3_HOUSE)
    | {f"{_INSTALLATION_KEY}.{name}" for name in Installation.model_fields}
)
# How Pydantic's schema points to a model it defines, once, under `$defs`:
# `{"$ref": "#/$defs/<model>"}`, wherever the model is used.
_DEFINITION_REFERENCE: Final = "#/$defs/"
# Where a scenario's kept opening day lies: a checkpoint of its run at that
# day's start (P09.5), gzipped, named for the scenario.
OPENINGS_DIR: Final = Path(__file__).parent / "openings"
# And of the same run with everything off, named so.
ALL_OFF_SUFFIX: Final = ".all-off"


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


def opening_day(scenario_id: str) -> int | None:
    """The day of its run a scenario's manifest names as where the viewer
    opens it, kept as a checkpoint at that day's start (`opening_file`), or
    None if it names none."""
    document = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    day = document.get(_OPENING_KEY)
    if day is None:
        return None
    if not isinstance(day, int) or isinstance(day, bool) or day < 0:
        raise InvalidManifest(f"{scenario_id}: an opening day is a day of its run, not {day!r}")
    return day


def opening_file(scenario_id: str, all_off: bool = False) -> Path:
    """Where a scenario's kept opening day lies, gzipped JSON: its run's, or
    the same run's with everything off, which a viewer charts beside it."""
    return OPENINGS_DIR / f"{scenario_id}{ALL_OFF_SUFFIX if all_off else ''}.json.gz"


def manifest_digest(scenario_id: str) -> str:
    """What tells one version of a scenario's manifest from another: a
    digest of its content, however its file is laid out."""
    document = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return short_digest(canonical, DIGEST_LENGTH)


def scenario_from_manifest(scenario_id: str, document: dict[str, JsonValue]) -> ScenarioConfig:
    """The scenario a manifest describes, its house its installation's, with
    its layout read from the file it names. Refused, with the reason, if the
    manifest is in a format this simulator does not read, names another
    scenario, notes a field it does not have, has a field the configuration
    or the installation does not, writes its house outside its installation,
    or holds an installation a run cannot grow."""
    version = document.get(_VERSION_KEY)
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not (version == SCHEMA_VERSION or version in _MIGRATIONS)
    ):
        older = ", ".join(str(each) for each in sorted(_MIGRATIONS))
        raise InvalidManifest(
            f"{scenario_id}: a manifest in format {version!r}; this simulator reads "
            f"format {SCHEMA_VERSION}, and formats {older} migrated to it"
        )
    document = _migrated(scenario_id, document, version)
    fields = {key: value for key, value in document.items() if key not in _MANIFEST_ONLY_FIELDS}
    if fields.get("greenhouse_id") != scenario_id:
        raise InvalidManifest(
            f"{scenario_id}: its manifest describes {fields.get('greenhouse_id')!r}"
        )
    outside = sorted(set(fields) & _FORMAT_3_HOUSE)
    if outside:
        raise InvalidManifest(
            f"{scenario_id}: its house is its installation's, not written beside it: {outside}"
        )
    notes = document.get(_NOTES_KEY, {})
    if not isinstance(notes, dict) or not all(isinstance(note, str) for note in notes.values()):
        raise InvalidManifest(f"{scenario_id}: notes are written by what each is about")
    unnoted = set(notes) - _NOTED
    if unnoted:
        raise InvalidManifest(f"{scenario_id}: notes on what it does not have: {sorted(unnoted)}")
    installation = _installation(scenario_id, document.get(_INSTALLATION_KEY))
    try:
        house = scenario_house(installation)
    except CannotRun as error:
        raise InvalidManifest(
            f"{scenario_id}: a run cannot grow its installation: {error}"
        ) from None
    config = ScenarioConfig.model_validate(fields | dict(house))
    unknown = unknown_fields(fields, config.model_dump(mode="json", exclude={"layout"}))
    if unknown:
        raise InvalidManifest(f"{scenario_id}: fields it does not have: {', '.join(unknown)}")
    return config


def _installation(scenario_id: str, written: JsonValue) -> Installation:
    """The installation a manifest holds, with its layout read from the file
    it names. Refused if it is not written out in the manifest, names its
    layout wrongly, or has a field an installation does not."""
    if not isinstance(written, dict):
        raise InvalidManifest(
            f"{scenario_id}: a manifest holds its {_INSTALLATION_KEY}, written out, not {written!r}"
        )
    layout = written.get(_LAYOUT_KEY, DEFAULT_LAYOUT)
    if not isinstance(layout, str) or not LAYOUT_NAME.fullmatch(layout):
        raise InvalidManifest(f"{scenario_id}: a layout is named, not {layout!r}")
    held = {key: value for key, value in written.items() if key != _LAYOUT_KEY}
    installation = Installation.model_validate(held | {"layout": load_layout(scenario_id, layout)})
    unknown = unknown_fields(held, installation.model_dump(mode="json", exclude={"layout"}))
    if unknown:
        named = ", ".join(f"{_INSTALLATION_KEY}.{where}" for where in unknown)
        raise InvalidManifest(f"{scenario_id}: fields it does not have: {named}")
    return installation


def _migrated(
    scenario_id: str, document: dict[str, JsonValue], version: int
) -> dict[str, JsonValue]:
    """A manifest in `version`, a format this simulator reads, as the
    current format writes it: each older format migrated to the next in
    turn."""
    while version < SCHEMA_VERSION:
        document = _MIGRATIONS[version](scenario_id, document) | {_VERSION_KEY: version + 1}
        version += 1
    return document


def _from_format_1(_scenario_id: str, document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Format 1 differs from format 2 only in the identifiers it allowed
    (#254): an identifier format 2 does not allow is refused as any field
    that does not fit is, by name."""
    return document


def _from_format_2(scenario_id: str, document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Format 2 wrote a heater's thermostat as `thermostat` (P10.3), which
    format 3 writes as its control's heating loop, the thermostat's day and
    night as the control's (P11.1); and a note on the thermostat as a note
    on the control."""
    if _CONTROL_KEY in document:
        raise InvalidManifest(f"{scenario_id}: a format 2 manifest has no {_CONTROL_KEY!r}")
    thermostat = document.get(_THERMOSTAT_KEY)
    rest = {key: value for key, value in document.items() if key != _THERMOSTAT_KEY}
    notes = rest.get(_NOTES_KEY)
    if isinstance(notes, dict) and _THERMOSTAT_KEY in notes:
        rest[_NOTES_KEY] = {
            (_CONTROL_KEY if about == _THERMOSTAT_KEY else about): note
            for about, note in notes.items()
        }
    if thermostat is None:
        return rest
    if not isinstance(thermostat, dict):
        raise InvalidManifest(f"{scenario_id}: a thermostat is an object, not {thermostat!r}")
    times = {key: value for key, value in thermostat.items() if key in _CONTROL_TIMES}
    heating = {key: value for key, value in thermostat.items() if key not in _CONTROL_TIMES}
    return rest | {_CONTROL_KEY: times | {"heating": heating}}


def _from_format_3(scenario_id: str, document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Format 3 wrote a scenario's house as fields of its own: its envelope,
    its layout's name, its rows and columns of plants, and the crop model
    and variety they grow. Format 4 holds them as its installation (P12.1,
    decision 0050), named for the scenario and called as it is (by its
    identifier if it has no name), every row growing that crop, where the
    format 3 fields stood; and a note on one of them is a note on the part
    of the installation it became. Its rows and columns are its layout's
    crop rows and their planting positions now, and a manifest whose are not
    is refused, naming both, as is a crop no row can grow."""
    if _INSTALLATION_KEY in document:
        raise InvalidManifest(f"{scenario_id}: a format 3 manifest has no {_INSTALLATION_KEY!r}")
    layout = document.get(_LAYOUT_KEY, DEFAULT_LAYOUT)
    if not isinstance(layout, str) or not LAYOUT_NAME.fullmatch(layout):
        raise InvalidManifest(f"{scenario_id}: a layout is named, not {layout!r}")
    crop_rows = load_layout(scenario_id, layout).crop_rows
    planted = (document.get("rows"), document.get("columns"))
    if crop_rows is None or planted != (crop_rows.rows, crop_rows.positions_per_row):
        laid = (
            "none"
            if crop_rows is None
            else f"{crop_rows.rows} rows of {crop_rows.positions_per_row} positions"
        )
        raise InvalidManifest(
            f"{scenario_id}: its {planted[0]!r} rows of {planted[1]!r} plants are not its "
            f"layout's crop rows, {laid}"
        )
    crop_model = document.get("crop_model", CropModel.SIMPLE.value)
    if crop_model not in tuple(CropModel):
        models = ", ".join(CropModel)
        raise InvalidManifest(f"{scenario_id}: a crop model is one of {models}, not {crop_model!r}")
    variety = document.get("variety")
    if not isinstance(variety, str) or not variety:
        raise InvalidManifest(f"{scenario_id}: a crop's variety is named, not {variety!r}")
    crop: dict[str, JsonValue] = {"crop_model": crop_model, "variety": variety}
    name = document.get("name")
    written: dict[str, JsonValue] = {
        "installation_id": scenario_id,
        "name": name if isinstance(name, str) and name else scenario_id,
        "envelope": document.get("envelope"),
        _LAYOUT_KEY: layout,
        "row_crops": [{"row": row, **crop} for row in range(1, crop_rows.rows + 1)],
    }
    # A field format 3 left out is left out of the installation, which says
    # so by name.
    installation: dict[str, JsonValue] = {
        key: value for key, value in written.items() if value is not None
    }
    migrated: dict[str, JsonValue] = {}
    for key, value in document.items():
        if key in _FORMAT_3_HOUSE:
            migrated.setdefault(_INSTALLATION_KEY, installation)
        elif key == _NOTES_KEY and isinstance(value, dict):
            migrated[key] = _notes_from_format_3(value)
        else:
            migrated[key] = value
    return migrated


def _notes_from_format_3(notes: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Format 3's notes, each on a house field now on the part of the
    installation it became; two on one part, one after the other."""
    moved: dict[str, JsonValue] = {}
    for about, note in notes.items():
        part = _FORMAT_3_NOTES.get(about, about)
        earlier = moved.get(part)
        moved[part] = note if earlier is None else f"{earlier} {note}"
    return moved


# How each older format a manifest may be written in becomes the next.
_MIGRATIONS: Final[dict[int, Callable[[str, dict[str, JsonValue]], dict[str, JsonValue]]]] = {
    1: _from_format_1,
    2: _from_format_2,
    3: _from_format_3,
}


def manifest_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema a manifest follows, published as
    `scenario.schema.json`: the configuration's, its house held as an
    installation with its layout named, with its format's version and its
    notes, and no field it does not have.

    It is the schema Pydantic generates for the configuration, changed where
    a manifest differs from it. Pydantic writes a model's schema as its
    fields' schemas, under `properties`; the names of those without a
    default, under `required`; and every model they use, once, under `$defs`.
    """
    schema = ScenarioConfig.model_json_schema()
    properties = schema["properties"]
    # A manifest holds its house as an installation, rather than as fields
    # of its own.
    for name in _FORMAT_3_HOUSE:
        del properties[name]
    schema["required"] = [name for name in schema["required"] if name not in _FORMAT_3_HOUSE]
    installation = Installation.model_json_schema()
    for name, definition in installation.pop("$defs").items():
        if schema["$defs"].setdefault(name, definition) != definition:
            raise ValueError(f"two definitions of {name} in a manifest's schema")
    # Its installation names its layout, rather than writing it out.
    installation["properties"][_LAYOUT_KEY] = {
        "type": "string",
        "pattern": f"^{LAYOUT_NAME.pattern}$",
        "default": DEFAULT_LAYOUT,
        "description": "The name of one of the scenario's layout files.",
    }
    installation["required"] = [
        *(name for name in installation["required"] if name != _LAYOUT_KEY),
        "row_crops",
    ]
    # Every crop row grows a crop in a scenario (`scenario_house`), so a
    # manifest's installation has at least one.
    crops = installation["properties"]["row_crops"]
    del crops["default"]
    crops["minItems"] = 1
    schema["$defs"][Installation.__name__] = installation
    properties[_INSTALLATION_KEY] = {"$ref": f"{_DEFINITION_REFERENCE}{Installation.__name__}"}
    # The fields a manifest has besides the configuration's.
    properties[_SCHEMA_KEY] = {"type": "string"}
    properties[_VERSION_KEY] = {"const": SCHEMA_VERSION}
    properties[_OPENING_KEY] = {
        "type": "integer",
        "minimum": 0,
        "description": "The day of its run where the viewer opens it, kept as a checkpoint.",
    }
    properties[_NOTES_KEY] = {
        "type": "object",
        "additionalProperties": {"type": "string"},
        "description": "What the scenario, or one of its fields, is and why.",
    }
    schema["required"] = [_VERSION_KEY, *schema["required"], _INSTALLATION_KEY]
    schema["additionalProperties"] = False
    schema["$defs"] = _used_definitions(schema["$defs"], properties)
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def unknown_fields(written: JsonValue, read: JsonValue, path: str = "") -> list[str]:
    """Where a manifest has a field that the configuration read from it does
    not, each by its path (`envelope.openings[0].centre.z`); and so for any
    document read into the configuration's models, such as an installation's
    file (`builder.portable`).

    Some of the configuration's models ignore a field they do not have,
    rather than refuse it. So what the manifest wrote is compared with what
    the configuration holds, written back as JSON: a field written but not
    held was ignored. The two have the same shape, since no field is read
    under another name (an alias) and a list keeps its items in order.
    """
    if isinstance(written, list) and isinstance(read, list):
        found: list[str] = []
        for index, (item, read_item) in enumerate(zip(written, read, strict=False)):
            found += unknown_fields(item, read_item, f"{path}[{index}]")
        return found
    if not isinstance(written, dict) or not isinstance(read, dict):
        return []
    found = []
    for key, value in written.items():
        where = f"{path}.{key}" if path else key
        if key not in read:
            found.append(where)
            continue
        found += unknown_fields(value, read[key], where)
    return found


def _used_definitions(
    definitions: dict[str, JsonValue], properties: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """The definitions a manifest's fields use, directly or through one
    another, by name.

    The configuration's schema defines the `Layout` and the models only it
    uses; a manifest's installation names its layout instead, so nothing
    uses those any more, and they are left out.
    """
    used: dict[str, JsonValue] = {}
    waiting = list(_references(properties))
    while waiting:
        name = waiting.pop()
        if name in used:
            continue
        used[name] = definitions[name]
        waiting += _references(definitions[name])
    return dict(sorted(used.items()))


def _references(schema: JsonValue) -> Iterator[str]:
    """The definitions a part of a schema points to, by name, wherever in
    it a `$ref` is."""
    if isinstance(schema, list):
        for item in schema:
            yield from _references(item)
        return
    if not isinstance(schema, dict):
        return
    reference = schema.get("$ref")
    if isinstance(reference, str):
        yield _definition_name(reference)
    for value in schema.values():
        yield from _references(value)


def _definition_name(reference: str) -> str:
    """The definition a `$ref` points to. Pydantic points only to the
    schema's own `$defs`; any other reference is refused, so that a change
    in how it writes them cannot quietly leave a definition out."""
    if not reference.startswith(_DEFINITION_REFERENCE):
        raise ValueError(f"a reference outside the schema's definitions: {reference}")
    return reference.removeprefix(_DEFINITION_REFERENCE)
