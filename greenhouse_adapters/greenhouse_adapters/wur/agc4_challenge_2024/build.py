"""Builds the canonical tier for the 2024 greenhouse from the raw
time-series archive: resolve the artifact, read the selected compartments'
members and the site weather / forecast members straight out of the zip,
parse, and write one deterministic canonical greenhouse whose records carry
their compartment id (none for site weather)."""

import io
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from greenhouse_protocol.enums import SourceType
from greenhouse_protocol.event import Event
from greenhouse_protocol.greenhouse import GreenhouseDescription, GreenhouseLayout
from greenhouse_protocol.observation import Observation

from greenhouse_adapters.canonical import (
    CanonicalGreenhouse,
    SourceMember,
    write_canonical_greenhouse,
)
from greenhouse_adapters.manifests import DatasetManifest, load_manifest
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_adapters.storage.resolver import ArtifactResolver
from greenhouse_adapters.wur.agc4_challenge_2024 import (
    DATASET,
    TIMESERIES_ARTIFACT,
    TIMESERIES_MEMBER_PREFIX,
)
from greenhouse_adapters.wur.agc4_challenge_2024.channels import (
    FORECAST_MEMBER,
    HARVEST_DAY_COLUMN,
    WEATHER_MEMBER,
)
from greenhouse_adapters.wur.agc4_challenge_2024.compartments import (
    COMPARTMENTS,
    GREENHOUSE_ID,
    Compartment,
)
from greenhouse_adapters.wur.agc4_challenge_2024.harvest import (
    final_harvest_event,
    read_harvest_workbook,
    sampling_observations,
)
from greenhouse_adapters.wur.agc4_challenge_2024.spacing import spacing_events
from greenhouse_adapters.wur.agc4_challenge_2024.timeseries import (
    final_harvest_timestamp,
    parse_forecast,
    parse_timeseries,
    parse_weather,
)

ADAPTER = "greenhouse_adapters.wur.agc4_challenge_2024"
HARVEST_MEMBER = "Harvest.xlsx"
CROP = "dwarf_tomato"


def manifest() -> DatasetManifest:
    return load_manifest(DATASET.id)


def canonical_directory(data_dir: DataDirectory) -> Path:
    return data_dir.canonical(manifest()) / GREENHOUSE_ID


def build_greenhouse(
    data_dir: DataDirectory, resolver: ArtifactResolver, compartments: Sequence[Compartment]
) -> CanonicalGreenhouse:
    """The canonical greenhouse holding the records of `compartments`. The
    Greenhouse record always lists all six compartments (the facility as
    the dataset describes it); `selection` in the provenance says which of
    them this build carries data for."""
    dataset = manifest()
    artifact = dataset.artifact(TIMESERIES_ARTIFACT)
    archive_path = resolver.resolve(dataset, artifact.name)
    harvest_member = TIMESERIES_MEMBER_PREFIX + HARVEST_MEMBER

    observations: list[Observation] = []
    events: list[Event] = []
    members: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        workbook = read_harvest_workbook(io.BytesIO(archive.read(harvest_member)))
        for compartment in compartments:
            member = TIMESERIES_MEMBER_PREFIX + compartment.timeseries_member
            members.append(member)
            lines = archive.read(member).decode("utf-8").splitlines()
            compartment_observations = list(parse_timeseries(lines, compartment))
            compartment_observations.extend(sampling_observations(workbook, compartment))
            events.extend(spacing_events(compartment_observations, compartment))
            harvested_at = final_harvest_timestamp(lines, compartment)
            date_source = HARVEST_DAY_COLUMN
            if harvested_at is None and compartment_observations:
                harvested_at = max(o.timestamp for o in compartment_observations)
                date_source = "end_of_recording"
            if harvested_at is not None:
                harvest = final_harvest_event(
                    workbook, compartment, harvested_at=harvested_at, date_source=date_source
                )
                if harvest is not None:
                    events.append(harvest)
            observations.extend(compartment_observations)
        for site_member, parse_site in (
            (WEATHER_MEMBER, parse_weather),
            (FORECAST_MEMBER, parse_forecast),
        ):
            member = TIMESERIES_MEMBER_PREFIX + site_member
            members.append(member)
            with archive.open(member) as raw:
                observations.extend(parse_site(io.TextIOWrapper(raw, encoding="utf-8")))
    members.append(harvest_member)

    return write_canonical_greenhouse(
        canonical_directory(data_dir),
        greenhouse=_greenhouse(observations),
        observations=observations,
        events=events,
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        adapter=ADAPTER,
        sources=[
            SourceMember(artifact=artifact.name, artifact_md5=artifact.md5, member=member)
            for member in members
        ],
        selection={
            "compartments": [c.number for c in compartments],
            "teams": [c.team for c in compartments],
        },
    )


def _greenhouse(observations: list[Observation]) -> GreenhouseDescription:
    # created_at is the start of the recording so the canonical record is a
    # pure function of the source data, not of when the build ran.
    recording_start = min(o.timestamp for o in observations) if observations else datetime.now(UTC)
    return GreenhouseDescription(
        greenhouse_id=GREENHOUSE_ID,
        name="WUR AGC4 2024",
        description=(
            "Recorded history of the 4th Autonomous Greenhouse Challenge (2024) at the WUR "
            "Bleiswijk facility: six dwarf-tomato compartments, each controlled by one team, "
            "with 5-minute climate, control and irrigation channels plus manual harvest "
            f"samples. Source: WUR / 4TU, {DATASET.id}."
        ),
        source_type=SourceType.IMPORTED_DATA,
        crop=CROP,
        layout=GreenhouseLayout(kind="compartment", rows=0, columns=0),
        plants=[],
        compartments=[c.to_domain() for c in COMPARTMENTS.values()],
        created_at=recording_start,
    )
