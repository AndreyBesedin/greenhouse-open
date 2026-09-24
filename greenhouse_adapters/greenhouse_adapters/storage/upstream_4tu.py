"""The 4TU.ResearchData metadata API - the upstream for WUR datasets.

Only metadata is fetched here (one small JSON document per dataset); the
artifact downloads themselves go through greenhouse_adapters.storage.resolver so
their size, checksum and precedence rules are enforced in one place.
"""

from collections.abc import Callable
from typing import Any

import httpx

from greenhouse_adapters.manifests import (
    ArtifactKind,
    ArtifactManifest,
    DatasetManifest,
    DatasetSource,
)

API_BASE_URL = "https://data.4tu.nl/v2/articles"

MetadataFetcher = Callable[[str], dict[str, Any]]
ArtifactClassifier = Callable[[str], ArtifactKind]


def fetch_dataset_metadata(dataset_uuid: str, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    response = httpx.get(
        f"{API_BASE_URL}/{dataset_uuid}",
        headers={"Accept": "application/json"},
        timeout=timeout_seconds,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


def build_manifest(
    *,
    dataset_id: str,
    dataset_uuid: str,
    classify: ArtifactClassifier,
    metadata: dict[str, Any],
) -> DatasetManifest:
    """Turns a 4TU article document into a DatasetManifest. Every field the
    manifest needs (sizes, MD5s, download URLs, licence, version) is taken
    from the document - nothing is guessed."""
    files = sorted(metadata["files"], key=lambda entry: str(entry["name"]))
    return DatasetManifest(
        id=dataset_id,
        version=int(metadata["version"]),
        title=str(metadata["title"]).strip(),
        source=DatasetSource(provider="4tu", dataset_uuid=dataset_uuid, doi=str(metadata["doi"])),
        licence=str(metadata["license"]["name"]),
        artifacts=[
            ArtifactManifest(
                name=str(entry["name"]),
                kind=classify(str(entry["name"])),
                size_bytes=int(entry["size"]),
                md5=str(entry["computed_md5"]),
                download_url=str(entry["download_url"]),
            )
            for entry in files
        ],
    )
