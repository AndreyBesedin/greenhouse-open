"""Where dataset files live on disk: the raw / canonical / features tiers.

${GREENHOUSE_DATA_DIR:-~/.greenhouse-open/data}/
  raw/<provider>/<dataset>/v<version>/        immutable source artifacts
  canonical/<provider>/<dataset>/v<version>/  deterministic normalised records
  features/<provider>/<dataset>/<extractor>/  derived perception outputs
"""

import os
from pathlib import Path

from greenhouse_adapters.manifests import DatasetManifest

DATA_DIR_ENV_VAR = "GREENHOUSE_DATA_DIR"
DEFAULT_DATA_DIR = Path.home() / ".greenhouse-open" / "data"


class DataDirectory:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _root_from_environment()).expanduser().resolve()

    def raw(self, manifest: DatasetManifest) -> Path:
        return self.root / "raw" / manifest.storage_prefix

    def canonical(self, manifest: DatasetManifest) -> Path:
        return self.root / "canonical" / manifest.storage_prefix

    def features(self, manifest: DatasetManifest, extractor_version: str) -> Path:
        return self.root / "features" / Path(*manifest.id.split("_", 1)) / extractor_version


def _root_from_environment() -> Path:
    configured = os.environ.get(DATA_DIR_ENV_VAR)
    return Path(configured) if configured else DEFAULT_DATA_DIR
