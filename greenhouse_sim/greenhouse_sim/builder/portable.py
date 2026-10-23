"""An installation as a file of its own, read and written without a
database or a repository (P12.0, decision 0050).

The file holds a draft's fields, written as a scenario's manifest writes
the same parts, and the version of the manifests' format, which it shares
with them (`manifest_files.SCHEMA_VERSION`): a format change to the house
part of a manifest changes this file with it. Format 4, which put a
manifest's house in an installation, left the installation as format 3
wrote it, so a file in either is read. Like a manifest it may name
its JSON Schema, `installation.schema.json` beside this module, and is
refused if it has a field a draft does not. It names a crop by its model,
and holds no code.
"""

import json
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.scenarios.installation import Installation
from greenhouse_sim.scenarios.manifest_files import SCHEMA_VERSION, unknown_fields

INSTALLATION_SCHEMA_FILE: Final = Path(__file__).parent / "installation.schema.json"
# A file larger than this is refused before it is read: an editor can say
# so as it is chosen.
MAX_IMPORT_BYTES: Final = 8_000_000
_SCHEMA_KEY: Final = "$schema"
_VERSION_KEY: Final = "schema_version"
# The first format an installation's file was written in; it has not
# changed since.
FIRST_FORMAT: Final = 3


class Problem(BaseModel):
    """Why a file was refused: the field at fault, by its path
    (`envelope.openings[0].centre.z`), empty for the file as a whole, and
    what is wrong with it."""

    model_config = ConfigDict(frozen=True)

    field: str
    message: str


class InstallationFileError(ValueError):
    """A file that is not an installation this simulator reads, with each
    problem found, for an editor to show by its field."""

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems
        first = problems[0]
        where = f"{first.field}: " if first.field else ""
        more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
        super().__init__(f"not a greenhouse installation file: {where}{first.message}{more}")


def export_installation(draft: Installation) -> str:
    """The file of a draft, its rows' crops included. A draft holding a
    number JSON cannot write, such as NaN, is not written."""
    document = {_VERSION_KEY: SCHEMA_VERSION, **draft.model_dump(mode="json")}
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def import_installation(text: str) -> Installation:
    """The draft a file holds. Refused with its problems if it is too
    large, not JSON (NaN and infinities included, which JSON has not), in
    a format it is not read in, not a draft, or has a field, at any depth,
    that a draft does not."""
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise InstallationFileError(
            [Problem(field="", message=f"larger than {MAX_IMPORT_BYTES} bytes")]
        )
    try:
        document = json.loads(text, parse_constant=_not_json)
    except (json.JSONDecodeError, _NotJson) as error:
        raise InstallationFileError([Problem(field="", message=f"not JSON: {error}")]) from None
    if not isinstance(document, dict):
        raise InstallationFileError([Problem(field="", message="not a JSON object")])
    version = document.get(_VERSION_KEY)
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not FIRST_FORMAT <= version <= SCHEMA_VERSION
    ):
        raise InstallationFileError(
            [
                Problem(
                    field=_VERSION_KEY,
                    message=(
                        f"format {version!r}; this simulator reads formats {FIRST_FORMAT} "
                        f"to {SCHEMA_VERSION}"
                    ),
                )
            ]
        )
    fields = {
        key: value for key, value in document.items() if key not in (_VERSION_KEY, _SCHEMA_KEY)
    }
    try:
        draft = Installation.model_validate(fields)
    except ValidationError as error:
        raise InstallationFileError(
            [Problem(field=_path(each["loc"]), message=each["msg"]) for each in error.errors()]
        ) from None
    # Some of the models a draft is made of ignore a field they do not have,
    # rather than refuse it, as a manifest's are read.
    unknown = unknown_fields(fields, draft.model_dump(mode="json"))
    if unknown:
        raise InstallationFileError(
            [Problem(field=where, message="not a field of an installation") for where in unknown]
        )
    return draft


class _NotJson(ValueError):
    """A constant Python reads as JSON, and JSON has not."""


def _not_json(constant: str) -> float:
    raise _NotJson(f"{constant} is not a JSON number")


def installation_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema an installation's file follows, published as
    `installation.schema.json`: a draft's, with the format's version and
    the schema's name."""
    schema = Installation.model_json_schema()
    properties = schema["properties"]
    properties[_VERSION_KEY] = {"const": SCHEMA_VERSION}
    properties[_SCHEMA_KEY] = {"type": "string"}
    schema["required"] = [_VERSION_KEY, *schema["required"]]
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


def _path(location: tuple[int | str, ...]) -> str:
    """A field's path as a manifest's checks write it: `a.b[0].c`."""
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path
