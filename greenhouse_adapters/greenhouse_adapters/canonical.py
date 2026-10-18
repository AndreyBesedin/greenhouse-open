"""The canonical tier: one directory per imported greenhouse holding the
normalised records an adapter produced, as line-delimited JSON of the
domain models themselves.

    <canonical>/<greenhouse_id>/
      greenhouse.json      the GreenhouseDescription record
      observations.jsonl   Observations, sorted by (timestamp, type, id)
      events.jsonl         Events, sorted the same way
      provenance.json      which source artifacts/members produced this,
                           their checksums, and content hashes of the
                           outputs - so a rebuild can be checked for drift

Deterministic by construction: same source bytes -> same output bytes. What
is written passes the protocol's conformance checks, or nothing is written.
"""

import hashlib
import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from greenhouse_protocol.contracts.conformance import check_events, check_observations
from greenhouse_protocol.event import Event
from greenhouse_protocol.greenhouse import GreenhouseDescription
from greenhouse_protocol.observation import Observation
from pydantic import BaseModel

GREENHOUSE_FILE = "greenhouse.json"
OBSERVATIONS_FILE = "observations.jsonl"
EVENTS_FILE = "events.jsonl"
PROVENANCE_FILE = "provenance.json"

_HASH_CHUNK_BYTES = 1024 * 1024
# A refused build can break thousands of records the same way; its error
# names the first few.
_VIOLATIONS_NAMED = 5


class RefusedBuild(ValueError):
    """A build the canonical tier does not write: one whose records fail the
    protocol's conformance checks, or one with no readings at all."""


class SourceMember(BaseModel):
    """One input the build read: an artifact from the dataset manifest and,
    for archives, the member inside it."""

    artifact: str
    artifact_md5: str
    member: str | None = None


class CanonicalProvenance(BaseModel):
    dataset_id: str
    dataset_version: int
    adapter: str
    greenhouse_id: str
    sources: list[SourceMember]
    selection: dict[str, Any]
    observation_count: int
    event_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    content_sha256: dict[str, str]


@dataclass(frozen=True)
class CanonicalGreenhouse:
    directory: Path

    @property
    def greenhouse_id(self) -> str:
        return self.directory.name

    def greenhouse(self) -> GreenhouseDescription:
        # Older tiers may carry extra fields (an owner, replay timestamps);
        # they are not part of the description and are ignored. Whoever
        # loads the tier decides ownership.
        return GreenhouseDescription.model_validate_json(
            (self.directory / GREENHOUSE_FILE).read_text()
        )

    def provenance(self) -> CanonicalProvenance:
        return CanonicalProvenance.model_validate_json(
            (self.directory / PROVENANCE_FILE).read_text()
        )

    def observations(self) -> Iterator[Observation]:
        yield from _read_jsonl(self.directory / OBSERVATIONS_FILE, Observation)

    def events(self) -> Iterator[Event]:
        yield from _read_jsonl(self.directory / EVENTS_FILE, Event)


def recording_start(observations: Sequence[Observation]) -> datetime:
    """When the source's recording starts, its first reading: a
    greenhouse's `created_at`, so that the tier is a pure function of the
    source data and not of when the build ran."""
    if not observations:
        raise RefusedBuild("the source has no readings, so no greenhouse is built from it")
    return min(o.timestamp for o in observations)


def write_canonical_greenhouse(
    directory: Path,
    *,
    greenhouse: GreenhouseDescription,
    observations: Iterable[Observation],
    events: Iterable[Event],
    dataset_id: str,
    dataset_version: int,
    adapter: str,
    sources: list[SourceMember],
    selection: dict[str, Any],
) -> CanonicalGreenhouse:
    # Checked before they are sorted: records built without validation may
    # hold a naive timestamp beside an aware one, which cannot be ordered.
    observations = list(observations)
    events = list(events)
    violations = check_observations(observations) + check_events(events)
    if violations:
        raise RefusedBuild(
            f"{len(violations)} conformance violation(s) in what {adapter} would write, "
            "for example: " + "; ".join(violations[:_VIOLATIONS_NAMED])
        )
    sorted_observations = sorted(
        observations, key=lambda o: (o.timestamp, o.observation_type.value, o.observation_id)
    )
    sorted_events = sorted(events, key=lambda e: (e.timestamp, e.event_type.value, e.event_id))

    directory.mkdir(parents=True, exist_ok=True)

    # Only the description, even if a caller passes a richer subclass, so
    # the tier stays the same whoever wrote it.
    description = GreenhouseDescription.model_validate(
        greenhouse.model_dump(include=set(GreenhouseDescription.model_fields))
    )
    (directory / GREENHOUSE_FILE).write_text(description.model_dump_json(indent=2) + "\n")
    _write_jsonl(directory / OBSERVATIONS_FILE, sorted_observations)
    _write_jsonl(directory / EVENTS_FILE, sorted_events)

    timestamps = [o.timestamp for o in sorted_observations] + [e.timestamp for e in sorted_events]
    provenance = CanonicalProvenance(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        adapter=adapter,
        greenhouse_id=greenhouse.greenhouse_id,
        sources=sources,
        selection=selection,
        observation_count=len(sorted_observations),
        event_count=len(sorted_events),
        first_timestamp=min(timestamps).isoformat() if timestamps else None,
        last_timestamp=max(timestamps).isoformat() if timestamps else None,
        content_sha256={
            name: _sha256(directory / name)
            for name in (GREENHOUSE_FILE, OBSERVATIONS_FILE, EVENTS_FILE)
        },
    )
    (directory / PROVENANCE_FILE).write_text(
        json.dumps(provenance.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    return CanonicalGreenhouse(directory)


def _write_jsonl(path: Path, records: Iterable[BaseModel]) -> None:
    with path.open("w") as sink:
        for record in records:
            sink.write(record.model_dump_json())
            sink.write("\n")


def _read_jsonl[T: BaseModel](path: Path, model: type[T]) -> Iterator[T]:
    with path.open() as source:
        for line in source:
            if line.strip():
                yield model.model_validate_json(line)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
