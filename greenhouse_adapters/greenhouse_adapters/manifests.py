"""Dataset manifests: what a source dataset contains, checked into Git in
place of the data itself. Generated from the provider's metadata API by
`greenhouse-data inventory`, never hand-copied."""

import json
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"
# The name in this package's own pyproject.toml, which marks its checkout.
PROJECT_NAME = "greenhouse-adapters"


class ArtifactKind(StrEnum):
    """Phase 0's classification of source files, which decides what a
    snapshot profile is allowed to download."""

    METADATA = "metadata"
    TIMESERIES = "timeseries"
    LABELLED_IMAGES = "labelled_images"
    LONGITUDINAL_RGBD = "longitudinal_rgbd"


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: ArtifactKind
    size_bytes: int
    md5: str
    download_url: str

    @field_validator("name")
    @classmethod
    def _a_plain_file_name(cls, name: str) -> str:
        # An artifact is stored under its name in the data directory, and a
        # name comes from the provider's metadata: a path, `..`, or on
        # Windows a drive (`D:file.zip`), would put the download somewhere
        # else.
        if name in {"", ".", ".."} or any(c in name for c in ("/", "\\", ":", "\0")):
            raise ValueError(f"artifact name {name!r} is not a plain file name")
        return name


class DatasetSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Literal["4tu"]
    dataset_uuid: str
    doi: str


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    version: int
    title: str
    source: DatasetSource
    licence: str
    artifacts: list[ArtifactManifest]

    def artifact(self, name: str) -> ArtifactManifest:
        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        raise KeyError(f"dataset {self.id!r} has no artifact named {name!r}")

    def artifacts_of_kind(self, *kinds: ArtifactKind) -> list[ArtifactManifest]:
        return [artifact for artifact in self.artifacts if artifact.kind in kinds]

    @property
    def storage_prefix(self) -> Path:
        """Where this dataset lives under raw/, canonical/ and features/:
        `<provider family>/<dataset>/v<version>`."""
        return Path(*self.id.split("_", 1)) / f"v{self.version}"


def manifest_path(dataset_id: str) -> Path:
    return MANIFEST_DIR / f"{dataset_id}.json"


def manifests_in_a_checkout() -> bool:
    """Whether the manifests are the source checkout's, which `inventory
    --write` may update, rather than an installed package's copy: beside
    this package's own metadata, not any `pyproject.toml`, which the
    application a package is installed into (`pip install --target`) may
    have."""
    metadata = MANIFEST_DIR.parents[1] / "pyproject.toml"
    if not metadata.is_file():
        return False
    try:
        project = tomllib.loads(metadata.read_text(encoding="utf-8")).get("project", {})
    except tomllib.TOMLDecodeError:
        return False
    name: object = project.get("name")
    return name == PROJECT_NAME


def load_manifest(dataset_id: str) -> DatasetManifest:
    path = manifest_path(dataset_id)
    if not path.exists():
        raise FileNotFoundError(
            f"no manifest for dataset {dataset_id!r} at {path}; run "
            f"`greenhouse-data inventory` to generate it"
        )
    return DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_manifest(manifest: DatasetManifest) -> Path:
    path = manifest_path(manifest.id)
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return path


def list_manifest_ids() -> list[str]:
    return sorted(path.stem for path in MANIFEST_DIR.glob("*.json"))
