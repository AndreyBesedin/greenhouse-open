"""Talks to the real 4TU API (metadata only, a few KB). Skipped unless
GREENHOUSE_ONLINE_TESTS=1 so ordinary CI never needs the network."""

import os

import pytest

from greenhouse_adapters.manifests import load_manifest
from greenhouse_adapters.storage.upstream_4tu import build_manifest, fetch_dataset_metadata
from greenhouse_adapters.wur.datasets import WUR_DATASETS

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("GREENHOUSE_ONLINE_TESTS") != "1",
        reason="set GREENHOUSE_ONLINE_TESTS=1 to query 4TU",
    ),
]


@pytest.mark.parametrize("dataset", list(WUR_DATASETS.values()), ids=lambda d: d.cli_name)
def test_committed_manifest_matches_upstream(dataset) -> None:  # type: ignore[no-untyped-def]
    metadata = fetch_dataset_metadata(dataset.dataset_uuid)

    generated = build_manifest(
        dataset_id=dataset.id,
        dataset_uuid=dataset.dataset_uuid,
        classify=dataset.classify,
        metadata=metadata,
    )

    assert generated == load_manifest(dataset.id)
