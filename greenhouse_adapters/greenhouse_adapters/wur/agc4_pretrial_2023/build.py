"""Builds the canonical tier for the 2023 pre-trial greenhouse from the raw
time-series archive: resolve the artifact, read the climate workbook straight
out of the zip together with the weekly crop measurements, parse, and write
one deterministic canonical greenhouse with its single compartment and its
labelled plants, and the destructive samples as events."""

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from greenhouse_protocol.enums import SourceType
from greenhouse_protocol.greenhouse import GreenhouseDescription, GreenhouseLayout, Plant
from greenhouse_protocol.observation import Observation

from greenhouse_adapters.canonical import (
    CanonicalGreenhouse,
    SourceMember,
    write_canonical_greenhouse,
)
from greenhouse_adapters.manifests import DatasetManifest, load_manifest
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_adapters.storage.resolver import ArtifactResolver
from greenhouse_adapters.wur.agc4_pretrial_2023 import (
    CLIMATE_MEMBER,
    CROP_MEMBER,
    DATASET,
    DESTRUCTIVE_MEMBER,
    TIMESERIES_ARTIFACT,
)
from greenhouse_adapters.wur.agc4_pretrial_2023.climate import parse_climate
from greenhouse_adapters.wur.agc4_pretrial_2023.compartments import (
    COMPARTMENT_ID,
    GREENHOUSE_ID,
    compartment,
)
from greenhouse_adapters.wur.agc4_pretrial_2023.crops import read_crop_measurements
from greenhouse_adapters.wur.agc4_pretrial_2023.destructive import read_destructive_samples

ADAPTER = "greenhouse_adapters.wur.agc4_pretrial_2023"
CROP = "dwarf_tomato"


def manifest() -> DatasetManifest:
    return load_manifest(DATASET.id)


def canonical_directory(data_dir: DataDirectory) -> Path:
    return data_dir.canonical(manifest()) / GREENHOUSE_ID


def build_greenhouse(data_dir: DataDirectory, resolver: ArtifactResolver) -> CanonicalGreenhouse:
    dataset = manifest()
    artifact = dataset.artifact(TIMESERIES_ARTIFACT)
    archive_path = resolver.resolve(dataset, artifact.name)
    with zipfile.ZipFile(archive_path) as archive:
        observations = list(parse_climate(io.BytesIO(archive.read(CLIMATE_MEMBER))))
        crops = read_crop_measurements(io.BytesIO(archive.read(CROP_MEMBER)))
        samples = read_destructive_samples(io.BytesIO(archive.read(DESTRUCTIVE_MEMBER)))
    observations.extend(crops.observations)

    return write_canonical_greenhouse(
        canonical_directory(data_dir),
        greenhouse=_greenhouse(observations, crops.plants),
        observations=observations,
        events=samples,
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        adapter=ADAPTER,
        sources=[
            SourceMember(artifact=artifact.name, artifact_md5=artifact.md5, member=member)
            for member in (CLIMATE_MEMBER, CROP_MEMBER, DESTRUCTIVE_MEMBER)
        ],
        selection={"compartments": [COMPARTMENT_ID]},
    )


def _greenhouse(observations: list[Observation], plants: list[Plant]) -> GreenhouseDescription:
    # created_at is the start of the recording so the canonical record is a
    # pure function of the source data, not of when the build ran.
    recording_start = min(o.timestamp for o in observations) if observations else datetime.now(UTC)
    return GreenhouseDescription(
        greenhouse_id=GREENHOUSE_ID,
        name="WUR AGC4 2023 pre-trial",
        description=(
            "Recorded history of the 4th Autonomous Greenhouse Challenge pre-trial (2023) at "
            "the WUR Bleiswijk facility: one compartment of dwarf tomatoes under four light "
            "and two EC treatments, with 5-minute greenhouse climate, site weather and "
            "weekly manual measurements of 40 labelled plants, plus 240 destructively "
            "sampled plants. "
            f"Source: WUR / 4TU, {DATASET.id}."
        ),
        source_type=SourceType.IMPORTED_DATA,
        crop=CROP,
        layout=GreenhouseLayout(kind="compartment", rows=0, columns=0),
        plants=[],
        compartments=[compartment(plants)],
        created_at=recording_start,
    )
