"""Dataset manifests: what a source dataset contains, checked into Git in
place of the data itself. Generated from the provider's metadata API by
`greenhouse-data inventory`, never hand-copied."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"


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


def load_manifest(dataset_id: str) -> DatasetManifest:
    path = manifest_path(dataset_id)
    if not path.exists():
        raise FileNotFoundError(
            f"no manifest for dataset {dataset_id!r} at {path}; run "
            f"`greenhouse-data inventory` to generate it"
        )
    return DatasetManifest.model_validate_json(path.read_text())


def write_manifest(manifest: DatasetManifest) -> Path:
    path = manifest_path(manifest.id)
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n")
    return path


def list_manifest_ids() -> list[str]:
    return sorted(path.stem for path in MANIFEST_DIR.glob("*.json"))
