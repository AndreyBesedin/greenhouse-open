"""The two AGC4 time-series archives, where `greenhouse-data prepare wur
agc4-2024 --profile dev` (and `agc4-2023`) put them: found, checked against
their manifests' checksums, and listed without the metadata of the tool
that zipped them. What the profile and the drivers read them through."""

import hashlib
import math
import zipfile
from pathlib import Path
from typing import Any, Final

from greenhouse_adapters.manifests import DatasetManifest, load_manifest
from greenhouse_adapters.storage.layout import DataDirectory

CHALLENGE: Final = "wur_agc4-challenge-2024"
PRETRIAL: Final = "wur_agc4-pretrial-2023"
CHALLENGE_ARCHIVE: Final = "autonomous_greenhouse_challenge4_timeseries.zip"
PRETRIAL_ARCHIVE: Final = "4th_autonomous_greenhouse_challenge_dwarf_tomato_pretrial_Timeseries.zip"
PRETRIAL_CLIMATE: Final = "ClimateTimeseries.xlsx"
PRETRIAL_CLIMATE_SHEET: Final = "weather_climate"
# What the archives' authors wrote where a value is missing, beside an empty cell.
NO_VALUE: Final = frozenset({"", "nan"})


def archive_path(data: DataDirectory, dataset: str, name: str) -> Path:
    """The archive `name` of `dataset`, refused if missing or not as its
    manifest has it."""
    manifest = load_manifest(dataset)
    path = data.raw(manifest) / name
    expected = manifest.artifact(name).md5
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing: `greenhouse-data prepare` downloads it at the dev profile"
        )
    if hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest() != expected:
        raise SystemExit(f"{path} does not match its manifest's checksum {expected}")
    return path


def provenance(manifest: DatasetManifest, name: str) -> dict[str, Any]:
    """Where an archive comes from, under which licence, and its checksum."""
    return {
        "doi": manifest.source.doi,
        "licence": manifest.licence,
        "archive": name,
        "md5": manifest.artifact(name).md5,
    }


def members(opened: zipfile.ZipFile) -> list[str]:
    """The archive's files, without the folders and the macOS resource forks
    its authors' zip tool added."""
    return sorted(
        name
        for name in opened.namelist()
        if not name.endswith("/")
        and not name.startswith("__MACOSX/")
        and Path(name).name != ".DS_Store"
    )


def holds(cell: object) -> bool:
    """Whether a cell holds a value: not empty, and not `NaN`."""
    if cell is None:
        return False
    if isinstance(cell, float):
        return not math.isnan(cell)
    return str(cell).strip().lower() not in NO_VALUE
