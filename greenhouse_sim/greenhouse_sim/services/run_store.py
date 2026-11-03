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
- `interventions.jsonl`: the changes given to the epoch, in order, each
  written before it is acted on (P17.8);
- `requests/{id}.json`: a change asked of the epoch by someone other than its
  worker, the only way one reaches it (the store is the only channel between
  a worker and the API), and `answers/{id}.json`, why its worker did not take
  it. Each is written once, by the one side, so that no two writers share an
  object;
- `inherited/outcomes.jsonl`: for a fork, the outcomes of its parent's up to
  where it branched, which say what its crop actions before then did;
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
import secrets
import tempfile
import time
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
_INHERITED_OUTCOMES: Final = "inherited/outcomes.jsonl"
# How much is drawn to tell apart two requests asked in one nanosecond.
REQUEST_TOKEN_BYTES: Final = 4
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


class ForkOf(BaseModel):
    """Where a fork comes from (decision 0065): its parent, the exact instant
    it branches at, the state it inherits (a checkpoint at `start_s`, kept as a
    copy of its own, and the parent's trajectory digest through it; none for
    one from its run's start), how many entries of its log are its parent's,
    and the layout it changes to, if it does."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    epoch: int
    at_s: float
    start_s: float
    digest: str | None = None
    checkpoint_sha256: str | None = None
    inherited: int = 0
    layout: str | None = None


class EpochManifest(BaseModel):
    """What an epoch is: its run, its number, the scenario it is of, its seed
    (none: the scenario's own), its layout and its status; and, for a fork, its
    parent."""

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
    fork: ForkOf | None = None


class LogEntry(BaseModel):
    """A change given to an epoch while it ran: its number in the log, the
    instant it takes effect, the moment of the epoch's clock it was given at,
    who gave it, what it is, and the request it answers if it was asked for
    through the store. It is applied again at the moment it was given, so
    that the epoch it makes is the same whenever it is worked out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    at_s: float
    given_s: float
    by: str
    what: dict[str, JsonValue]
    request: str | None = None


class Answer(BaseModel):
    """Why a worker did not act on a request it took, in its own words."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request: str
    reason: str


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
class Inherited:
    """What a fork at some instant of an epoch inherits of it: the nearest
    state at or before that instant, where it is, and the trajectory's digest
    through it. None of them for an instant before its first state: its run's
    start."""

    start_s: float
    checkpoint: bytes | None
    digest: str | None


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


def digest_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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

    def write_fork(
        self,
        manifest: EpochManifest,
        *,
        state: bytes | None,
        log: Sequence[LogEntry],
        outcomes: Sequence[ActionOutcome],
    ) -> None:
        """Writes a fork: the state it inherits, its log so far and its parent's
        outcomes, then its manifest, last, so that one cut short is never listed."""
        assert manifest.fork is not None
        if state is not None:
            self.objects.put(self._inherited_name(manifest.fork), state)
        if log:
            self.objects.put(
                f"{self._home}/interventions.jsonl",
                b"".join(entry.model_dump_json().encode() + b"\n" for entry in log),
            )
        if outcomes:
            self.objects.put(
                f"{self._home}/{_INHERITED_OUTCOMES}",
                b"".join(outcome.model_dump_json().encode() + b"\n" for outcome in outcomes),
            )
        self.objects.put(f"{self._home}/manifest.json", manifest.model_dump_json().encode())

    def _inherited_name(self, fork: ForkOf) -> str:
        return f"{self._home}/checkpoints/{instant_name(fork.start_s)}.json.zst"

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

    def start_s(self) -> float:
        """Where what the epoch holds begins: its run's start, or for a fork
        the state it inherits."""
        fork = self.manifest().fork
        return 0.0 if fork is None else fork.start_s

    def frontier_s(self) -> float:
        """How far the epoch is committed, in seconds into its run: where it
        begins, until a commit says otherwise."""
        commits = self.commits()
        return commits[-1].end_s if commits else self.start_s()

    def size_bytes(self, listed: Iterable[str] | None = None) -> int:
        """How many bytes the epoch's objects hold, those `listed` of it if
        they have just been."""
        names = self.objects.names(f"{self._home}/") if listed is None else listed
        return sum(self.objects.size(name) or 0 for name in names)

    def lacks(
        self, manifest: EpochManifest, commits: Sequence[Commit], listed: Iterable[str]
    ) -> bool:
        """Whether an object that `commits` name, or the state a fork inherits,
        is missing from what was `listed` of the epoch after they were read. A
        writer puts up what a commit names before the commit, so that an epoch
        being worked is never told so. No object is read: `verify` says whether
        those held are what their commits name."""
        held = set(listed)
        wanted = {
            f"{self._home}/segments/{commit.segment}/{kind}.parquet"
            for commit in commits
            for kind in Kind
        }
        wanted.update(commit.checkpoint for commit in commits if commit.checkpoint is not None)
        if commits and commits[-1].log_position:
            wanted.add(f"{self._home}/interventions.jsonl")
        if manifest.fork is not None and manifest.fork.checkpoint_sha256 is not None:
            wanted.add(self._inherited_name(manifest.fork))
        if not wanted <= held:
            return True
        # `commits` stops at a gap: a commit listed past the next one, which is not.
        written = sum(name.startswith(f"{self._home}/commits/") for name in held)
        next_commit = f"{self._home}/commits/{len(commits):0{SEQ_DIGITS}d}.json"
        return written > len(commits) and next_commit not in held

    def log(self) -> list[LogEntry]:
        """The changes given to the epoch up to the last commit."""
        commits = self.commits()
        return self.logged()[: commits[-1].log_position if commits else 0]

    def logged(self) -> list[LogEntry]:
        """Every change logged, those no commit names yet included: each is
        acted on once it is here, and applied again if a crash comes first."""
        data = self.objects.get(f"{self._home}/interventions.jsonl") or b""
        return [LogEntry.model_validate_json(line) for line in data.decode().splitlines()]

    def append_log(self, entry: LogEntry) -> None:
        """Logs a change, its number the next, before it is acted on. Only
        the epoch's worker writes its log."""
        held = self.objects.get(f"{self._home}/interventions.jsonl") or b""
        if entry.seq != len(held.splitlines()):
            raise ValueError(f"the log of {self._home} is at {len(held.splitlines())}")
        line = entry.model_dump_json().encode() + b"\n"
        self.objects.put(f"{self._home}/interventions.jsonl", held + line)

    def ask(self, what: dict[str, JsonValue]) -> str:
        """Asks the epoch's worker for a change: an object of its own, named
        so that names sort as they were asked; the name it is known by."""
        request = f"{time.time_ns():020d}-{secrets.token_hex(REQUEST_TOKEN_BYTES)}"
        self.objects.put(f"{self._home}/requests/{request}.json", json.dumps(what).encode())
        return request

    def requests(self) -> list[str]:
        """The changes asked of the epoch, in the order they were asked."""
        prefix = f"{self._home}/requests/"
        return [
            name.removeprefix(prefix).removesuffix(".json") for name in self.objects.names(prefix)
        ]

    def request(self, request: str) -> bytes | None:
        return self.objects.get(f"{self._home}/requests/{request}.json")

    def answer(self, answer: Answer) -> None:
        """Says why a request was not acted on."""
        self.objects.put(
            f"{self._home}/answers/{answer.request}.json", answer.model_dump_json().encode()
        )

    def answers(self) -> list[Answer]:
        found = (self.objects.get(n) for n in self.objects.names(f"{self._home}/answers/"))
        return [Answer.model_validate_json(data) for data in found if data is not None]

    def _log_bytes(self, position: int) -> bytes:
        """The log's first `position` entries as a trajectory's digest takes
        them: what each is, and not the name of the request that brought it,
        which is drawn afresh each time one is asked."""
        return b"".join(
            entry.model_copy(update={"request": None}).model_dump_json().encode() + b"\n"
            for entry in self.logged()[:position]
        )

    def commit(
        self,
        start_s: float,
        end_s: float,
        *,
        observations: Sequence[Observation] = (),
        events: Sequence[Event] = (),
        outcomes: Sequence[ActionOutcome] = (),
        checkpoint: bytes | None = None,
    ) -> Commit:
        """Writes a span's segment and its checkpoint, then the commit that
        names them, last, with the log's entries given before the span's end:
        what its records were worked out under, whatever else is logged by the
        time it is written, which depends on how the epoch was paced."""
        # Named, and so refused if an instant cannot be, before anything is written.
        segment = f"{instant_name(start_s)}-{instant_name(end_s)}"
        if end_s < start_s:
            raise ValueError(f"a span ends no earlier than it starts, not {start_s}-{end_s} s")
        commits = self.commits()
        previous = commits[-1] if commits else None
        before = previous.digest if previous else self._genesis()
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
        position = sum(entry.given_s < end_s for entry in self.logged())
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
            digest=_extend(before, parts),
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
            inherited = self._inherited_state(at_s)
            return None if inherited is None else (inherited, CHECKPOINT_TYPE)
        # A state restored is the trajectory's: checked against its commit, as
        # the records are.
        self._verify_commit(best)
        data = self.objects.get(best.checkpoint)
        if data is None:
            raise StoreCorrupt(f"commit {best.seq} of {self._home} names a checkpoint that is gone")
        return data, best.checkpoint_type

    def _inherited_state(self, at_s: float) -> bytes | None:
        """The state a fork inherited, if it did and `at_s` is not before it,
        checked against what its manifest says of it."""
        fork = self.manifest().fork
        if fork is None or fork.checkpoint_sha256 is None or at_s < fork.start_s:
            return None
        data = self.objects.get(self._inherited_name(fork))
        if data is None or digest_of(data) != fork.checkpoint_sha256:
            raise StoreCorrupt(f"the state {self._home} inherited is not what it says")
        return data

    def inherited_at(self, at_s: float) -> Inherited:
        """What a fork of the epoch at `at_s` inherits of it."""
        best = None
        for commit in self.commits():
            if commit.checkpoint is not None and commit.end_s <= at_s:
                best = commit
        if best is not None:
            found = self.checkpoint_at(best.end_s)
            assert found is not None
            return Inherited(best.end_s, found[0], best.digest)
        fork = self.manifest().fork
        if fork is None:
            return Inherited(0.0, None, None)
        return Inherited(fork.start_s, self._inherited_state(at_s), fork.digest)

    def outcomes_kept(self) -> list[ActionOutcome]:
        """Every outcome it knows of, its parent's it inherited first: what
        its crop actions before where it is kept did."""
        held = self.objects.get(f"{self._home}/{_INHERITED_OUTCOMES}") or b""
        inherited = [ActionOutcome.model_validate_json(line) for line in held.splitlines()]
        return [*inherited, *self.outcomes().records]

    def _genesis(self) -> str:
        """What the trajectory goes on from: for a fork its parent's, through
        the state it inherits."""
        fork = self.manifest().fork
        return GENESIS if fork is None or fork.digest is None else fork.digest

    def verify(self) -> None:
        """Checks every commit's digest against the objects it names."""
        for commit in self.commits():
            self._verify_commit(commit)

    def discard_uncommitted(self) -> list[str]:
        """Removes what a crash left past the last commit, which names what
        the epoch holds: segments and checkpoints written for a commit that
        was never made, and a commit past a gap. The next commit writes over
        those of its own span; the rest, of another span, would stay. Log
        entries past the last commit stay, to be applied again, as do the
        requests and answers, which no commit names. The names removed."""
        commits = self.commits()
        kept = {f"{self._home}/manifest.json", f"{self._home}/interventions.jsonl"}
        kept.add(f"{self._home}/{_INHERITED_OUTCOMES}")
        fork = self.manifest().fork
        if fork is not None and fork.checkpoint_sha256 is not None:
            kept.add(self._inherited_name(fork))
        for commit in commits:
            kept.add(f"{self._home}/commits/{commit.seq:0{SEQ_DIGITS}d}.json")
            kept.update(f"{self._home}/segments/{commit.segment}/{kind}.parquet" for kind in Kind)
            if commit.checkpoint is not None:
                kept.add(commit.checkpoint)
        # By their folders and not by a listing, in which one asked meanwhile
        # would be missing: the asker is in another process.
        spared = (f"{self._home}/requests/", f"{self._home}/answers/")
        removed = []
        for name in self.objects.names(f"{self._home}/"):
            if (
                name not in kept
                and name != f"{self._home}/{leases.LEASE}"
                and not name.startswith(spared)
            ):
                self.objects.delete(name)
                removed.append(name)
        return removed

    def _verify_commit(self, commit: Commit) -> None:
        previous = self._genesis()
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
    # Where what it holds begins, and for a fork where it comes from.
    start_s: float = 0.0
    fork: ForkOf | None = None
    # Whether an object its commits name is missing, so that it cannot be read
    # whole. Said from the names of its objects, not from their contents.
    damaged: bool = False


def stored_run(objects: ObjectStore, run_id: str, epoch_number: int) -> StoredRun:
    """One epoch as a list of them shows it. Only its own folder is read, and
    no more of it than its size asks: its commits, and the names of its objects,
    which are listed after the commits so that all they name are there."""
    epoch = EpochStore(objects, run_id, epoch_number)
    manifest = epoch.manifest()
    commits = epoch.commits()
    frontier = commits[-1].end_s if commits else epoch.start_s()
    listed = objects.names(f"{run_id}/{epoch_number}/")
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
        size_bytes=epoch.size_bytes(listed),
        start_s=0.0 if manifest.fork is None else manifest.fork.start_s,
        fork=manifest.fork,
        damaged=epoch.lacks(manifest, commits, listed),
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
