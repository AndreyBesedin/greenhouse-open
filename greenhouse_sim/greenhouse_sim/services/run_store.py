"""A run's epochs kept on disk (P17.3, decisions 0065 and 0066): what a
worker writes and a reader reads, with no run, clock or API in between.

The store is an interface over named objects (`ObjectStore`: put one whole,
get, list, delete) and a folder under the user's state folder is its first
backend (`FolderStore`). An epoch's objects, under `{run_id}/{epoch}/`:

- `manifest.json`: the run, its seed, its status;
- `segments/{start}-{end}/{observations,events,outcomes}.parquet`: its
  records for a span of simulated time, written once, zstd Parquet, read and
  written with DuckDB;
- `checkpoints/{instant}.json.zst`: a model's state at an instant, kept as
  its content type says;
- `interventions.jsonl`: the changes given to the epoch, in order;
- `commits/{seq}.json`: written last. A commit names one segment, its
  checkpoint if there is one, the position reached in the log, and the
  trajectory digest: a running sha256 over every object the commits so far
  name. A reader sees what the last commit names and nothing written after
  it, and checks a segment against its commit's digest as it reads it.

A commit's number is one more than the one before, so an epoch's frontier is
its last commit's end, and a crash leaves the epoch at the commit before.
The observations are columns of their own (a segment's bulk, and what an
analysis selects by); an event and an outcome are a few columns beside their
whole record as JSON, which is how they come back exactly.
"""

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Callable, Iterable, Sequence
from compression import zstd
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, Protocol

import duckdb
from greenhouse_protocol.enums import ObservationQuality, ObservationType
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.provenance import RecordSource
from pydantic import BaseModel, ConfigDict, JsonValue

from greenhouse_sim.services import leases

FORMAT: Final = "run-store-1"
CHECKPOINT_TYPE: Final = "application/json+zstd"
# An instant is written in a name as whole microseconds, zero-padded, so that
# names sort as instants do and two instants a microsecond apart never share
# one. Sixteen digits hold a run of more than a century.
MICROSECONDS_A_SECOND: Final = 1_000_000
INSTANT_DIGITS: Final = 16
SEQ_DIGITS: Final = 8
_PARTIAL: Final = ".partial"
# The instant instants are counted from in a segment's file.
EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)


class StoreCorrupt(RuntimeError):
    """An object a commit names is missing, or is not what its digest says."""


class Status(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    # Stopped before its end: a restart, or the producer stopping.
    INTERRUPTED = "interrupted"


# The statuses an epoch is told when it is no longer worked.
ENDED: Final = frozenset({Status.FINISHED, Status.FAILED, Status.INTERRUPTED})


class Kind(StrEnum):
    """One of an epoch's logs of records."""

    OBSERVATIONS = "observations"
    EVENTS = "events"
    OUTCOMES = "outcomes"


class ObjectStore(Protocol):
    """Named objects, put whole: one is seen entire or not at all."""

    def put(self, name: str, data: bytes) -> None: ...

    def get(self, name: str) -> bytes | None: ...

    def names(self, prefix: str = "") -> list[str]: ...

    def children(self, prefix: str = "") -> list[str]: ...

    def size(self, name: str) -> int | None: ...

    def delete(self, name: str) -> None: ...


def default_root() -> Path:
    """Where a run store is kept on this machine: the user's state folder
    (`XDG_STATE_HOME`, or ~/.local/state), under greenhouse-sim."""
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "greenhouse-sim" / "runs"


class FolderStore:
    """Objects as files under a folder. An object is written to a name of its
    own beside it and renamed into place, so that a reader finds it whole or
    not there, and one half written, which a crash leaves, is never listed."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = default_root() if root is None else root

    def put(self, name: str, data: bytes) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, partial = tempfile.mkstemp(dir=path.parent, suffix=_PARTIAL)
        try:
            with os.fdopen(descriptor, "wb") as written:
                written.write(data)
                written.flush()
                os.fsync(written.fileno())
            os.replace(partial, path)
        except BaseException:
            Path(partial).unlink(missing_ok=True)
            raise

    def get(self, name: str) -> bytes | None:
        try:
            return (self.root / name).read_bytes()
        except FileNotFoundError:
            return None

    def names(self, prefix: str = "") -> list[str]:
        """The objects whose names begin with `prefix`, sorted. Only the
        folder the prefix names (what precedes its last `/`) is walked, so
        that listing one epoch's commits costs what it holds, not what the
        store does; a partial name after it is a filter."""
        directory = PurePosixPath(prefix.rpartition("/")[0])
        if directory.is_absolute() or ".." in directory.parts:
            return []
        walked = self.root / directory
        if not walked.is_dir():
            return []
        found = (
            path.relative_to(self.root).as_posix()
            for path in walked.rglob("*")
            if path.is_file() and path.suffix != _PARTIAL
        )
        return sorted(name for name in found if name.startswith(prefix))

    def size(self, name: str) -> int | None:
        """How many bytes an object holds, or none if there is none."""
        try:
            return (self.root / name).stat().st_size
        except FileNotFoundError:
            return None

    def children(self, prefix: str = "") -> list[str]:
        """What is directly under the folder `prefix` names (its objects and
        its folders, by their own names, sorted), so that finding a store's
        runs reads their folders and not their segments."""
        directory = PurePosixPath(prefix.rstrip("/"))
        if prefix.startswith("/") or ".." in directory.parts:
            return []
        walked = self.root / directory
        if not walked.is_dir():
            return []
        return sorted(path.name for path in walked.iterdir() if path.suffix != _PARTIAL)

    def delete(self, name: str) -> None:
        (self.root / name).unlink(missing_ok=True)


class EpochManifest(BaseModel):
    """What an epoch is: its run, its number, the scenario it is of, its seed
    (none: the scenario's own), its layout and its status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: str = FORMAT
    run_id: str
    epoch: int
    scenario_id: str
    seed: int | None = None
    layout: str
    status: Status = Status.QUEUED
    # How long the run lasts, in seconds, when its writer knows: what its
    # progress is a part of.
    duration_s: float | None = None
    # When the epoch was started, when its writer says.
    created_at: datetime | None = None


class LogEntry(BaseModel):
    """A change given to an epoch while it ran: its number in the log, the
    instant it takes effect, who gave it, and what it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at_s: float
    by: str
    what: dict[str, JsonValue]


class Commit(BaseModel):
    """What one commit names: a segment, with how many records of each log it
    holds, the checkpoint kept with it if any, the log's length, and the
    trajectory digest through it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    segment: str
    start_s: float
    end_s: float
    counts: dict[Kind, int]
    checkpoint: str | None = None
    checkpoint_type: str | None = None
    log_position: int
    digest: str


@dataclass(frozen=True)
class Page[RecordT]:
    """Records after a position of a log, the position after them, and
    whether it has more."""

    records: list[RecordT]
    next: int
    has_more: bool


@dataclass(frozen=True)
class _Codec[RecordT]:
    """How a log's records are columns: the schema of its Parquet file, a
    record as a row, and a row as the record it came from."""

    columns: tuple[tuple[str, str], ...]
    row: Callable[[RecordT], tuple[object, ...]]
    build: Callable[[tuple[object, ...]], RecordT]

    def encode(self, records: Iterable[RecordT]) -> bytes:
        """A segment's records of this log as a zstd Parquet file, in their
        order. The rows go to DuckDB as lines of JSON it reads in bulk, about
        fourteen times faster than inserting them one by one."""
        names = [name for name, _ in self.columns]
        columns = ", ".join(f"{name} {sql}" for name, sql in self.columns)
        read = ", ".join(
            f"'{name}': '{'VARCHAR' if sql == 'TIMESTAMPTZ' else sql}'"
            for name, sql in self.columns
        )
        select = ", ".join(
            f"CAST({name} AS TIMESTAMPTZ) AS {name}" if sql == "TIMESTAMPTZ" else name
            for name, sql in self.columns
        )
        with tempfile.TemporaryDirectory() as folder, duckdb.connect() as con:
            con.execute("SET TimeZone='UTC'")
            con.execute(f"CREATE TABLE log ({columns})")
            lines = Path(folder) / "rows.jsonl"
            count = 0
            with lines.open("w") as written:
                for record in records:
                    row = self.row(record)
                    written.write(
                        json.dumps(
                            {
                                name: value.isoformat() if isinstance(value, datetime) else value
                                for name, value in zip(names, row, strict=True)
                            },
                            allow_nan=False,
                        )
                        + "\n"
                    )
                    count += 1
            if count:
                con.execute(
                    f"INSERT INTO log SELECT {select} FROM read_json('{lines}', "
                    f"format='newline_delimited', columns={{{read}}})"
                )
            path = Path(folder) / "segment.parquet"
            con.execute(f"COPY log TO '{path}' (FORMAT parquet, COMPRESSION zstd)")
            return path.read_bytes()

    def decode(self, data: bytes) -> list[RecordT]:
        """The records of a segment's file, in the order they were written."""
        # An instant is read as whole microseconds from the epoch, which is
        # what it is stored as, so that no time zone library is in between.
        names = ", ".join(
            f"epoch_us({name})" if sql == "TIMESTAMPTZ" else name for name, sql in self.columns
        )
        with tempfile.TemporaryDirectory() as folder, duckdb.connect() as con:
            con.execute("SET TimeZone='UTC'")
            path = Path(folder) / "segment.parquet"
            path.write_bytes(data)
            rows = con.execute(
                f"SELECT {names} FROM read_parquet('{path}', file_row_number=true) "
                "ORDER BY file_row_number"
            ).fetchall()
        return [self.build(row) for row in rows]


def _observation_row(o: Observation) -> tuple[object, ...]:
    return (
        o.observation_id,
        o.greenhouse_id,
        o.compartment_id,
        o.plant_id,
        o.timestamp,
        o.observation_type.value,
        o.value,
        o.source.type.value,
        o.source.source_id,
        o.sensor_id,
        o.delivered_at,
        sorted(q.value for q in o.quality),
    )


def _utc(microseconds: object) -> datetime | None:
    """An instant stored as microseconds from the epoch."""
    if not isinstance(microseconds, int):
        return None
    return EPOCH + timedelta(microseconds=microseconds)


def _observation(row: tuple[object, ...]) -> Observation:
    identity, greenhouse, compartment, plant, at, kind, value, source, source_id = row[:9]
    sensor, delivered, quality = row[9:]
    assert isinstance(quality, list)
    return Observation.model_validate(
        dict(
            observation_id=identity,
            greenhouse_id=greenhouse,
            compartment_id=compartment,
            plant_id=plant,
            timestamp=_utc(at),
            observation_type=ObservationType(str(kind)),
            value=value,
            source=RecordSource.model_validate(dict(type=source, source_id=source_id)),
            sensor_id=sensor,
            delivered_at=_utc(delivered),
            quality=frozenset(ObservationQuality(str(q)) for q in quality),
        )
    )


OBSERVATIONS: Final = _Codec[Observation](
    (
        ("observation_id", "VARCHAR"),
        ("greenhouse_id", "VARCHAR"),
        ("compartment_id", "VARCHAR"),
        ("plant_id", "VARCHAR"),
        ("timestamp", "TIMESTAMPTZ"),
        ("observation_type", "VARCHAR"),
        ("value", "DOUBLE"),
        ("source_type", "VARCHAR"),
        ("source_id", "VARCHAR"),
        ("sensor_id", "VARCHAR"),
        ("delivered_at", "TIMESTAMPTZ"),
        ("quality", "VARCHAR[]"),
    ),
    _observation_row,
    _observation,
)
EVENTS: Final = _Codec[Event](
    (
        ("event_id", "VARCHAR"),
        ("timestamp", "TIMESTAMPTZ"),
        ("event_type", "VARCHAR"),
        ("plant_id", "VARCHAR"),
        ("record", "VARCHAR"),
    ),
    lambda e: (e.event_id, e.timestamp, e.event_type.value, e.plant_id, e.model_dump_json()),
    lambda row: Event.model_validate_json(str(row[-1])),
)
OUTCOMES: Final = _Codec[ActionOutcome](
    (
        ("outcome_id", "VARCHAR"),
        ("resolved_at", "TIMESTAMPTZ"),
        ("status", "VARCHAR"),
        ("plan_id", "VARCHAR"),
        ("record", "VARCHAR"),
    ),
    lambda o: (o.outcome_id, o.resolved_at, o.status.value, o.plan_id, o.model_dump_json()),
    lambda row: ActionOutcome.model_validate_json(str(row[-1])),
)


def compress(text: str) -> bytes:
    """A checkpoint's JSON as it is kept: `CHECKPOINT_TYPE`."""
    return zstd.compress(text.encode())


def decompress(data: bytes) -> str:
    return zstd.decompress(data).decode()


def instant_us(seconds: float) -> int:
    """An instant, in seconds into a run, as whole microseconds: the number
    it is written as in the shortest decimal that gives the float (`0.1` is
    100,000), so that no instant is rounded into another's name. Refused if it
    is not a whole number of microseconds, or not an instant of a run."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"an instant of a run is 0 or more seconds, not {seconds!r}")
    microseconds = Decimal(repr(seconds)) * MICROSECONDS_A_SECOND
    if microseconds != microseconds.to_integral_value():
        raise ValueError(f"an instant is a whole number of microseconds, not {seconds!r} s")
    return int(microseconds)


def instant_name(seconds: float) -> str:
    return f"{instant_us(seconds):0{INSTANT_DIGITS}d}"


def _extend(previous: str, parts: Sequence[tuple[str, bytes]]) -> str:
    """The digest through a commit: the one before, then each object it names
    by name and by the digest of its bytes."""
    running = hashlib.sha256(previous.encode())
    for name, data in parts:
        running.update(name.encode())
        running.update(hashlib.sha256(data).digest())
    return running.hexdigest()


GENESIS: Final = hashlib.sha256(FORMAT.encode()).hexdigest()


class EpochStore:
    """One epoch in a store: written by one worker, read by any number."""

    def __init__(self, objects: ObjectStore, run_id: str, epoch: int) -> None:
        self.objects = objects
        self.run_id = run_id
        self.epoch = epoch
        self._home = f"{run_id}/{epoch}"

    @classmethod
    def create(cls, objects: ObjectStore, manifest: EpochManifest) -> EpochStore:
        made = cls(objects, manifest.run_id, manifest.epoch)
        objects.put(f"{made._home}/manifest.json", manifest.model_dump_json().encode())
        return made

    def manifest(self) -> EpochManifest:
        data = self.objects.get(f"{self._home}/manifest.json")
        if data is None:
            raise StoreCorrupt(f"epoch {self._home} has no manifest")
        return EpochManifest.model_validate_json(data)

    def set_status(self, status: Status) -> None:
        """Says what the epoch is. One said to run is held by this process
        (`leases`) until it is said to have ended, by whoever says it."""
        before = self.manifest()
        manifest = before.model_copy(update={"status": status})
        self.objects.put(f"{self._home}/manifest.json", manifest.model_dump_json().encode())
        if status == Status.RUNNING:
            if before.status != Status.RUNNING:
                leases.hold(self.objects, self._home)
        elif status in ENDED:
            leases.release(self.objects, self._home)

    def worked(self, *, now: float | None = None) -> bool:
        """Whether a process holds the epoch's lease."""
        return leases.alive(self.objects, self._home, now=now)

    def commits(self, after: int = 0) -> list[Commit]:
        """The commits in order, from number `after` (a reader that has the
        first few asks only for the rest): those with no gap before them, so
        that a commit past a missing one is not seen."""
        found: list[Commit] = []
        for seq in range(after, len(self.objects.names(f"{self._home}/commits/"))):
            data = self.objects.get(f"{self._home}/commits/{seq:0{SEQ_DIGITS}d}.json")
            if data is None:
                break
            found.append(Commit.model_validate_json(data))
        return found

    def frontier_s(self) -> float:
        """How far the epoch is committed, in seconds into its run."""
        commits = self.commits()
        return commits[-1].end_s if commits else 0.0

    def size_bytes(self) -> int:
        """How many bytes the epoch's objects hold."""
        return sum(self.objects.size(name) or 0 for name in self.objects.names(f"{self._home}/"))

    def log(self) -> list[LogEntry]:
        """The changes given to the epoch up to the last commit."""
        commits = self.commits()
        return self._log_to(commits[-1].log_position if commits else 0)

    def _log_to(self, position: int) -> list[LogEntry]:
        data = self.objects.get(f"{self._home}/interventions.jsonl") or b""
        lines = data.decode().splitlines()[:position]
        return [LogEntry.model_validate_json(line) for line in lines]

    def _log_bytes(self, position: int) -> bytes:
        data = self.objects.get(f"{self._home}/interventions.jsonl") or b""
        return b"".join(line + b"\n" for line in data.splitlines()[:position])

    def commit(
        self,
        start_s: float,
        end_s: float,
        *,
        observations: Sequence[Observation] = (),
        events: Sequence[Event] = (),
        outcomes: Sequence[ActionOutcome] = (),
        checkpoint: bytes | None = None,
        log: Sequence[LogEntry] = (),
    ) -> Commit:
        """Writes a span's segment, its checkpoint and the log's new entries,
        then the commit that names them, last."""
        # Named, and so refused if an instant cannot be, before anything is written.
        segment = f"{instant_name(start_s)}-{instant_name(end_s)}"
        if end_s < start_s:
            raise ValueError(f"a span ends no earlier than it starts, not {start_s}-{end_s} s")
        commits = self.commits()
        previous = commits[-1] if commits else None
        parts: list[tuple[str, bytes]] = []
        counts = {
            Kind.OBSERVATIONS: len(observations),
            Kind.EVENTS: len(events),
            Kind.OUTCOMES: len(outcomes),
        }
        for kind, data in (
            (Kind.OBSERVATIONS, OBSERVATIONS.encode(observations)),
            (Kind.EVENTS, EVENTS.encode(events)),
            (Kind.OUTCOMES, OUTCOMES.encode(outcomes)),
        ):
            name = f"{self._home}/segments/{segment}/{kind}.parquet"
            self.objects.put(name, data)
            parts.append((name, data))
        kept = None
        if checkpoint is not None:
            kept = f"{self._home}/checkpoints/{instant_name(end_s)}.json.zst"
            self.objects.put(kept, checkpoint)
            parts.append((kept, checkpoint))
        position = previous.log_position if previous else 0
        if log:
            lines = self._log_bytes(position) + b"".join(
                entry.model_dump_json().encode() + b"\n" for entry in log
            )
            self.objects.put(f"{self._home}/interventions.jsonl", lines)
            position += len(log)
        parts.append((f"{self._home}/interventions.jsonl", self._log_bytes(position)))
        made = Commit(
            seq=len(commits),
            segment=segment,
            start_s=start_s,
            end_s=end_s,
            counts=counts,
            checkpoint=kept,
            checkpoint_type=None if kept is None else CHECKPOINT_TYPE,
            log_position=position,
            digest=_extend(previous.digest if previous else GENESIS, parts),
        )
        self.objects.put(
            f"{self._home}/commits/{made.seq:0{SEQ_DIGITS}d}.json", made.model_dump_json().encode()
        )
        return made

    def _checked(self, commit: Commit, kind: Kind) -> bytes:
        """A segment's file, after its commit's digest has been checked."""
        self._verify_commit(commit)
        return self._segment(commit, kind)

    def _segment(self, commit: Commit, kind: Kind) -> bytes:
        name = f"{self._home}/segments/{commit.segment}/{kind}.parquet"
        data = self.objects.get(name)
        if data is None:
            raise StoreCorrupt(f"commit {commit.seq} of {self._home} names {name}, which is gone")
        return data

    def observations(self, after: int = 0, limit: int | None = None) -> Page[Observation]:
        """The observations after position `after`, counted across the
        segments in the commits' order, at most `limit` of them."""
        return self._page(Kind.OBSERVATIONS, OBSERVATIONS, after, limit)

    def events(self, after: int = 0, limit: int | None = None) -> Page[Event]:
        return self._page(Kind.EVENTS, EVENTS, after, limit)

    def outcomes(self, after: int = 0, limit: int | None = None) -> Page[ActionOutcome]:
        return self._page(Kind.OUTCOMES, OUTCOMES, after, limit)

    def _page[RecordT](
        self, kind: Kind, codec: _Codec[RecordT], after: int, limit: int | None
    ) -> Page[RecordT]:
        found: list[RecordT] = []
        position = total = 0
        for commit in self.commits():
            held = commit.counts[kind]
            total += held
            if position + held > after and (limit is None or len(found) < limit):
                records = codec.decode(self._checked(commit, kind))
                start = max(0, after - position)
                room = None if limit is None else limit - len(found)
                found += records[start : None if room is None else start + room]
            position += held
        reached = after + len(found)
        return Page(found, reached, reached < total)

    def checkpoint_at(self, at_s: float) -> tuple[bytes, str] | None:
        """The latest checkpoint at or before `at_s`, and its content type."""
        best = None
        for commit in self.commits():
            if commit.checkpoint is not None and commit.end_s <= at_s:
                best = commit
        if best is None or best.checkpoint is None or best.checkpoint_type is None:
            return None
        # A state restored is the trajectory's: checked against its commit, as
        # the records are.
        self._verify_commit(best)
        data = self.objects.get(best.checkpoint)
        if data is None:
            raise StoreCorrupt(f"commit {best.seq} of {self._home} names a checkpoint that is gone")
        return data, best.checkpoint_type

    def verify(self) -> None:
        """Checks every commit's digest against the objects it names."""
        for commit in self.commits():
            self._verify_commit(commit)

    def _verify_commit(self, commit: Commit) -> None:
        previous = GENESIS
        if commit.seq:
            data = self.objects.get(f"{self._home}/commits/{commit.seq - 1:0{SEQ_DIGITS}d}.json")
            if data is None:
                raise StoreCorrupt(f"commit {commit.seq - 1} of {self._home} is gone")
            previous = Commit.model_validate_json(data).digest
        parts = [
            (f"{self._home}/segments/{commit.segment}/{kind}.parquet", self._segment(commit, kind))
            for kind in Kind
        ]
        if commit.checkpoint is not None:
            data = self.objects.get(commit.checkpoint)
            if data is None:
                raise StoreCorrupt(f"{commit.checkpoint} is gone")
            parts.append((commit.checkpoint, data))
        parts.append((f"{self._home}/interventions.jsonl", self._log_bytes(commit.log_position)))
        if _extend(previous, parts) != commit.digest:
            raise StoreCorrupt(f"commit {commit.seq} of {self._home} is not what it names")


def epochs(objects: ObjectStore, run_id: str) -> list[int]:
    """The epochs a run has in a store, in order: the folders of its own whose
    manifests are there."""
    return sorted(
        int(name)
        for name in objects.children(f"{run_id}/")
        if name.isdigit() and objects.get(f"{run_id}/{name}/manifest.json") is not None
    )


# What an epoch deleted leaves in its folder, so that its number is not used again.
DELETED: Final = "deleted.json"


def started_epochs(objects: ObjectStore, run_id: str) -> list[int]:
    """Every epoch a run has ever started in a store, in order: those it
    holds and those that were deleted, which keep their numbers."""
    return sorted(int(name) for name in objects.children(f"{run_id}/") if name.isdigit())


def delete_epoch(objects: ObjectStore, run_id: str, epoch: int) -> None:
    """Removes an epoch's objects, leaving a mark that it was, so that no
    epoch of the run takes its number (decision 0040). The mark is written
    first and the manifest removed next, so that a deletion cut short leaves
    an epoch no list shows and no run reuses."""
    home = f"{run_id}/{epoch}/"
    objects.put(f"{home}{DELETED}", b'{"deleted": true}')
    manifest = f"{home}manifest.json"
    objects.delete(manifest)
    for name in objects.names(home):
        if name not in (manifest, f"{home}{DELETED}"):
            objects.delete(name)


class StoredRun(BaseModel):
    """An epoch as a person's list shows it: which run, whose seed, in what
    state, and how far it is committed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    epoch: int
    scenario_id: str
    seed: int | None
    layout: str
    status: Status
    frontier_s: float
    duration_s: float | None
    progress: float | None
    created_at: datetime | None
    size_bytes: int


def stored_run(objects: ObjectStore, run_id: str, epoch_number: int) -> StoredRun:
    """One epoch as a list of them shows it. Only its own folder is read."""
    epoch = EpochStore(objects, run_id, epoch_number)
    manifest = epoch.manifest()
    frontier = epoch.frontier_s()
    return StoredRun(
        run_id=run_id,
        epoch=manifest.epoch,
        scenario_id=manifest.scenario_id,
        seed=manifest.seed,
        layout=manifest.layout,
        status=manifest.status,
        frontier_s=frontier,
        duration_s=manifest.duration_s,
        progress=None if not manifest.duration_s else frontier / manifest.duration_s,
        created_at=manifest.created_at,
        size_bytes=epoch.size_bytes(),
    )


def stored_runs(objects: ObjectStore, scenario_id: str | None = None) -> list[StoredRun]:
    """The epochs a store holds, those of `scenario_id` if given, by run and
    epoch. Only the runs' folders are read, not their segments."""
    found = []
    for run_id in objects.children():
        for epoch_number in epochs(objects, run_id):
            if scenario_id is not None:
                manifest = EpochStore(objects, run_id, epoch_number).manifest()
                if manifest.scenario_id != scenario_id:
                    continue
            found.append(stored_run(objects, run_id, epoch_number))
    return found
