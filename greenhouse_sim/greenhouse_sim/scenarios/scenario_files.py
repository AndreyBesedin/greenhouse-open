"""A scenario as a file that can be sent to someone else (P17.11).

The scenario file is a scenario's manifest (decision 0031) in a portable
form: its house held as an installation with its layout written out rather
than named (decision 0050), the manifests' one format version and
migrations (`manifest_files.SCHEMA_VERSION`), a refusal that names the field
at fault, and no code: a crop is named by its model, and a recorded weather
is data.

A scenario that runs under a recorded weather (a CSV, told apart by its
content) names it in `recorded_weather`: the file's name and its digest, and,
if the sender chose to send it, the CSV. A file whose CSV is not the digest's
is refused; one without the CSV names a weather the receiver may not have
(`ScenarioFile.recording_missing`).
"""

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Final

from pydantic import JsonValue, ValidationError

from greenhouse_sim.digests import short_digest
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios.catalogue import SCENARIO_ID
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import (
    CannotCopy,
    ScenarioHouse,
    scenario_installation,
)
from greenhouse_sim.scenarios.manifest_files import (
    DIGEST_LENGTH,
    SCHEMA_VERSION,
    InvalidManifest,
    scenario_from_manifest,
)
from greenhouse_sim.scenarios.registry import CONFIGURED, chosen, model
from greenhouse_sim.weather.recorded import (
    RECORDING_NAME,
    RecordedWeather,
    WeatherFileError,
    read_records,
    recording_available,
    recording_digest,
)

# A file larger than this is refused before it is read, as an installation's
# file is: a chooser can say so as the file is picked.
MAX_IMPORT_BYTES: Final = 8_000_000
# The first format a scenario file was written in. A manifest's migrations
# carry an older file on to the current format.
FIRST_FORMAT: Final = 7
RECORDED_WEATHER: Final = "recorded_weather"
_VERSION_KEY: Final = "schema_version"
_INSTALLATION_KEY: Final = "installation"
_MODELS_KEY: Final = "models"
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
# What a manifest has that a file has not: where the viewer opens a packaged
# scenario's run, kept as a checkpoint beside it.
_NOT_IN_A_FILE: Final = "opening_day"
_RECORDING_FIELDS: Final = frozenset({"file", "digest", "csv"})


class ScenarioFileError(ValueError):
    """A file that is not a scenario this simulator reads: the field at fault
    by its path (empty for the file as a whole) and what is wrong with it."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        where = f"{field}: " if field else ""
        super().__init__(f"not a scenario file: {where}{message}")


@dataclass(frozen=True)
class Recording:
    """The recorded weather a scenario runs under, as its file names it: the
    file's name, the digest of its content, and the content if the file
    carries it."""

    file: str
    digest: str
    csv: bytes | None


@dataclass(frozen=True)
class ScenarioFile:
    """A scenario file read: its scenario, its recording if it runs under
    one, and the digest of the file, so that the same file again is the same
    scenario."""

    config: ScenarioConfig
    recording: Recording | None
    digest: str

    @property
    def recording_missing(self) -> bool:
        """Whether the scenario runs under a recorded weather this process has
        not got: the file does not carry it, and none of that name and
        content is offered."""
        recording = self.recording
        return (
            recording is not None
            and recording.csv is None
            and not recording_available(recording.file, recording.digest)
        )


def export_scenario_file(config: ScenarioConfig, *, with_recording: bool = True) -> str:
    """A scenario as a file: its manifest, with its layout written out. If it
    runs under a recorded weather the file names it and its digest, and
    carries its CSV unless `with_recording` is False. Refused if the
    scenario plants fewer positions than its layout's rows hold (an
    installation's crop grows every position of a row), or holds a number
    JSON cannot write."""
    try:
        installation = scenario_installation(config)
    except CannotCopy as error:
        raise ScenarioFileError("", f"it cannot be written as a file: {error}") from None
    held = set(ScenarioHouse.model_fields) | CONFIGURED
    document: dict[str, JsonValue] = {
        _VERSION_KEY: SCHEMA_VERSION,
        **{
            name: value
            for name, value in config.model_dump(mode="json").items()
            if name not in held
        },
        _INSTALLATION_KEY: installation.model_dump(mode="json"),
        _MODELS_KEY: _models(config),
    }
    weather = config.weather
    if isinstance(weather, RecordedWeather):
        content = weather.content()
        section: dict[str, JsonValue] = {
            "file": weather.file,
            "digest": recording_digest(content),
        }
        if with_recording:
            section["csv"] = content.decode()
        document[RECORDED_WEATHER] = section
    try:
        return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except ValueError as error:
        raise ScenarioFileError("", f"it holds a number JSON cannot write: {error}") from None


def import_scenario_file(text: str) -> ScenarioFile:
    """The scenario a file holds. Refused if it is too large, not JSON (NaN
    and infinities included), in a format it is not read in, not a scenario,
    has a field, at any depth, that a scenario does not, or names a recorded
    weather wrongly: not the one the scenario runs under, or a CSV whose
    digest is not the one named or that is not a weather file."""
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise ScenarioFileError("", f"larger than {MAX_IMPORT_BYTES} bytes")
    document = _parsed(text)
    version = document.get(_VERSION_KEY)
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not FIRST_FORMAT <= version <= SCHEMA_VERSION
    ):
        raise ScenarioFileError(
            _VERSION_KEY,
            f"format {version!r}; this simulator reads formats {FIRST_FORMAT} to {SCHEMA_VERSION}",
        )
    if _NOT_IN_A_FILE in document:
        raise ScenarioFileError(_NOT_IN_A_FILE, "a scenario file has no kept opening day")
    scenario_id = document.get("greenhouse_id")
    if not isinstance(scenario_id, str) or not SCENARIO_ID.fullmatch(scenario_id):
        raise ScenarioFileError(
            "greenhouse_id",
            f"a scenario is named by lowercase letters, digits and _, not {scenario_id!r}",
        )
    written = {key: value for key, value in document.items() if key != RECORDED_WEATHER}
    try:
        config = scenario_from_manifest(scenario_id, written, layout_written=True)
    except ValidationError as error:
        first = error.errors()[0]
        raise ScenarioFileError(_path(first["loc"]), first["msg"]) from None
    except InvalidManifest as error:
        raise ScenarioFileError("", str(error)) from None
    recording = _recording(config, document.get(RECORDED_WEATHER))
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return ScenarioFile(config, recording, short_digest(canonical, DIGEST_LENGTH))


def _models(config: ScenarioConfig) -> dict[str, JsonValue]:
    """The section of each part: its model and that model's parameters."""
    sections: dict[str, JsonValue] = {}
    for part, name in chosen(config).items():
        chosen_model = model(part, name)
        parameters: dict[str, JsonValue] = (
            {}
            if chosen_model.field is None
            else chosen_model.written(getattr(config, chosen_model.field))
        )
        sections[str(Part(part))] = {"model": name, "parameters": parameters}
    return sections


def _recording(config: ScenarioConfig, written: JsonValue) -> Recording | None:
    """The recording a file names, checked against the scenario's weather."""
    weather = config.weather
    if not isinstance(weather, RecordedWeather):
        if written is not None:
            raise ScenarioFileError(
                RECORDED_WEATHER,
                f"the scenario runs under a {weather.kind} weather, not a recorded one",
            )
        return None
    if not isinstance(written, dict) or set(written) - _RECORDING_FIELDS:
        raise ScenarioFileError(
            RECORDED_WEATHER, f"a recorded weather is named by {sorted(_RECORDING_FIELDS)}"
        )
    file, digest, csv = written.get("file"), written.get("digest"), written.get("csv")
    if file != weather.file or not RECORDING_NAME.fullmatch(weather.file):
        raise ScenarioFileError(
            f"{RECORDED_WEATHER}.file",
            f"the scenario runs under {weather.file!r}, a plain name ending in .csv; "
            f"the file names {file!r}",
        )
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ScenarioFileError(f"{RECORDED_WEATHER}.digest", "a SHA-256, in lowercase hexadecimal")
    if csv is None:
        return Recording(weather.file, digest, None)
    if not isinstance(csv, str):
        raise ScenarioFileError(f"{RECORDED_WEATHER}.csv", "the weather file's text")
    content = csv.encode()
    if recording_digest(content) != digest:
        raise ScenarioFileError(
            f"{RECORDED_WEATHER}.csv", "its content is not the one the digest names"
        )
    try:
        read_records(csv)
    except WeatherFileError as error:
        raise ScenarioFileError(f"{RECORDED_WEATHER}.csv", str(error)) from None
    return Recording(weather.file, digest, content)


class _NotJson(ValueError):
    """A constant Python reads as JSON, and JSON has not."""


def _not_json(constant: str) -> float:
    raise _NotJson(f"{constant} is not a JSON number")


def _finite(written: str) -> float:
    """A number as JSON writes it, refused if Python reads it as infinite, as
    it reads `1e999`."""
    number = float(written)
    if not math.isfinite(number):
        raise _NotJson(f"{written} is too large a number")
    return number


def _parsed(text: str) -> dict[str, Any]:
    try:
        document = json.loads(text, parse_constant=_not_json, parse_float=_finite)
    except (json.JSONDecodeError, _NotJson) as error:
        raise ScenarioFileError("", f"not JSON: {error}") from None
    except RecursionError:
        raise ScenarioFileError("", "not JSON this simulator reads: nested too deeply") from None
    if not isinstance(document, dict):
        raise ScenarioFileError("", "not a JSON object")
    return document


def _path(location: tuple[int | str, ...]) -> str:
    """A field's path as a manifest's checks write it: `a.b[0].c`."""
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path
