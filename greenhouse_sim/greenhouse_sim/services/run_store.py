"""A run's epochs kept on disk (P17.3, decisions 0065 and 0066): what a
worker writes and a reader reads, with no run, clock or API in between.

The store is an interface over named objects (`ObjectStore`: put one whole,
create one unless it exists, get, list, delete) and a folder under the user's
state folder is its first backend (`FolderStore`). An epoch's objects, under
`{run_id}/{epoch}/`:

- `manifest.json`: the run, its seed, its status, and why it failed if it did;
- `budget.json`: what its worker keeps to (`limits`), which whoever puts it in line
  writes before it, and writes again if it finds it waiting under other limits. Of its
  own, so that it never writes over what a worker says of the epoch, and in no digest;
- `usage.json`: what the epoch has used (`EpochUsage`, decision 0067), written
  after each commit and as it ends: a report in no digest, which nothing that
  decides a trajectory reads, and which the list reads so as not to walk;
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
- `stop.json`: that the epoch's worker is asked to stop, for a worker no process
  that asks can signal (the one of a server that was killed, or on another
  machine). The worker reads it between its moments and ends `interrupted`; it
  names no moment and no process, and is removed when the epoch ended and waits
  for a worker again, so that it never stops the work carried on after it. No
  commit names it, so that no digest does;
- `inherited/outcomes.jsonl`: for a fork, the outcomes of its parent's up to
  where it branched, which say what its crop actions before then did;
- `leases/{number}.json`: who works the epoch (`leases`), which no commit names;
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

import errno
import hashlib
import json
import logging
import math
import os
import secrets
import shutil
import tempfile
import threading
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
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import leases
from greenhouse_sim.services.errors import ServiceError
from greenhouse_sim.services.limits import Budget, LimitPassed
from greenhouse_sim.services.resources import ProcessUse

logger = logging.getLogger(__name__)

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
_STOP_ASKED: Final = "stop.json"
USAGE: Final = "usage.json"
_BUDGET: Final = "budget.json"
# How much is drawn to tell apart two requests asked in one nanosecond.
REQUEST_TOKEN_BYTES: Final = 4
# The instant instants are counted from in a segment's file.
EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)


class StoreCorrupt(RuntimeError):
    """An object a commit names is missing, or is not what its digest says."""


class EpochTaken(RuntimeError):
    """A process said an epoch runs with no claim on it, while another holds one."""


class Status(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    # Stopped before its end: a restart, or the producer stopping.
    INTERRUPTED = "interrupted"


# The statuses an epoch is told when it is no longer worked.
ENDED: Final = frozenset({Status.FINISHED, Status.FAILED, Status.INTERRUPTED})

# What a failed epoch whose writer gave no reason says.
NO_REASON_GIVEN: Final = "no reason was given: its worker's log may say"
_DISK_FULL: Final = frozenset({errno.ENOSPC, errno.EDQUOT})


def failure_reason(error: BaseException) -> str:
    """Why an epoch failed, as any client that lists it may read. A service's
    error is already written for a client. Of any other only its kind is said,
    and never its text, which can hold a path or a value; the traceback stays in
    its worker's log."""
    while not isinstance(error, ServiceError) and error.__cause__ is not None:
        error = error.__cause__
    if isinstance(error, ServiceError):
        return error.message
    if isinstance(error, MemoryError):
        return "its worker ran out of memory"
    if isinstance(error, StoreCorrupt):
        return "an object its commits name is missing, or is not what its digest says"
    if isinstance(error, OSError):
        if error.errno in _DISK_FULL:
            return "the disk of its run store is full"
        code = errno.errorcode.get(error.errno or 0, type(error).__name__)
        return f"its run store could not be read or written ({code})"
    return f"its run could not be worked out ({type(error).__name__})"


class Kind(StrEnum):
    """One of an epoch's logs of records."""

    OBSERVATIONS = "observations"
    EVENTS = "events"
    OUTCOMES = "outcomes"


class ObjectStore(Protocol):
    """Named objects, put whole: one is seen entire or not at all."""

    def put(self, name: str, data: bytes) -> None: ...

    def create(self, name: str, data: bytes) -> bool:
        """Makes the object `name` unless one exists, and says whether this call
        made it (decision 0067). Of any number of callers at once, in any process
        that reaches the store, exactly one is told it did; from then until the
        object is deleted every other is told it did not, and changes nothing. The
        object is seen whole, as one `put` is. Nothing else is promised: not which
        caller wins, and not that another caller's listing shows the object yet. A
        store of objects gives this as a write conditional on no such object."""
        ...

    def get(self, name: str) -> bytes | None: ...

    def names(self, prefix: str = "") -> list[str]: ...

    def children(self, prefix: str = "") -> list[str]: ...

    def size(self, name: str) -> int | None: ...

    def delete(self, name: str) -> None: ...

    def free_bytes(self) -> int | None:
        """How many more bytes it has room for, or none if it cannot say, as a
        store of objects with no disk of its own cannot."""
        ...


def default_root() -> Path:
    """Where a run store is kept on this machine: the user's state folder
    (`XDG_STATE_HOME`, or ~/.local/state), under greenhouse-sim."""
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "greenhouse-sim" / "runs"


def _written_beside(path: Path, data: bytes) -> str:
    """`data`, on the disk, under a name of its own beside `path` that is never listed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, partial = tempfile.mkstemp(dir=path.parent, suffix=_PARTIAL)
    try:
        with os.fdopen(descriptor, "wb") as written:
            written.write(data)
            written.flush()
            os.fsync(written.fileno())
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise
    return partial


class FolderStore:
    """Objects as files under a folder. An object is written to a name of its
    own beside it and moved into place, so that a reader finds it whole or
    not there, and one half written, which a crash leaves, is never listed."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = default_root() if root is None else root

    def put(self, name: str, data: bytes) -> None:
        path = self.root / name
        partial = _written_beside(path, data)
        try:
            os.replace(partial, path)
        except BaseException:
            Path(partial).unlink(missing_ok=True)
            raise

    def create(self, name: str, data: bytes) -> bool:
        """The whole file is given the name as a hard link, which the file system
        refuses, whoever else is linking, if the name is taken. So the folder must be
        on one that has hard links: a local disk or NFS, not exFAT or some network
        mounts, where this raises the file system's error and no epoch can be worked."""
        path = self.root / name
        partial = _written_beside(path, data)
        try:
            os.link(partial, path)
        except FileExistsError:
            return False
        finally:
            Path(partial).unlink(missing_ok=True)
        return True

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
        runs reads their folders and not their segments. A `Path` for each entry
        would be most of what a list of a large store costs (P18.2)."""
        directory = PurePosixPath(prefix.rstrip("/"))
        if prefix.startswith("/") or ".." in directory.parts:
            return []
        try:
            found = os.listdir(self.root / directory)
        except FileNotFoundError, NotADirectoryError:
            return []
        return sorted(name for name in found if not name.endswith(_PARTIAL))

    def delete(self, name: str) -> None:
        (self.root / name).unlink(missing_ok=True)

    def free_bytes(self) -> int | None:
        """What is free on the folder's disk: on the nearest folder there is, since
        a store's own is made by its first object."""
        for folder in (self.root, *self.root.parents):
            try:
                return shutil.disk_usage(folder).free
            except OSError:
                continue
        return None


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
    (none: the scenario's own), its layout and its status; for a fork, its
    parent; and what a worker needs beside it (decision 0067). An epoch written
    before they were kept says neither of the last two."""

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
    # When it was last put in line for a scheduler's worker, which is what brings it
    # back in its place after a restart: none for one a process of its own takes up.
    queued_at: datetime | None = None
    # Whether it was last asked to be carried on: if its worker ends before it takes
    # it up, it is as interrupted as it was, with or without a commit to go on from.
    resumed: bool = False
    fork: ForkOf | None = None
    # The digest of its scenario's portable file in this store
    # (`services.scenario_files`): none for a packaged scenario, which every
    # simulator has.
    scenario_file: str | None = None
    # The real seconds to a simulated day its worker advances at: none, as fast
    # as it can.
    seconds_per_day: float | None = None
    # Why it failed (`failure_reason`), for any client: none unless it did, or
    # if it failed before epochs said why.
    reason: str | None = None
    # Whether it failed for a limit (`EpochStore.end_past_limit`), which alone of all
    # failures leaves it as it would be interrupted: it can be carried on.
    past_limit: bool = False

    @property
    def carries_on(self) -> bool:
        """Whether it has ended in a way that a worker can carry it on from."""
        return self.status == Status.INTERRUPTED or (
            self.status == Status.FAILED and self.past_limit
        )


class EpochUsage(BaseModel):
    """What an epoch has used, as `usage.json` says it (decision 0067): written
    after each commit and as the epoch ends, so that it may lag a crash by a
    commit. It is a report and not a record: in no digest, and read by nothing
    that decides a trajectory.

    Across a resume, each figure says the epoch's whole so far:

    - `commits`, `checkpoints`, `frontier_s`, `days_computed` and `bytes_kept`
      are worked out afresh from what it holds, so that nothing is counted twice
      and a resume resets nothing. A fork counts from the state it inherits: that
      state's bytes are its own, its parent's days are not, and a day worked out
      by a worker that died before committing it does not count;
    - `cpu_s` adds up its workers' seconds, each worker's as far as it last
      reported them, those spent on work a crash then lost included: it is what
      the machine gave. A fork starts from none of its parent's;
    - `peak_memory_bytes` is the highest of any one of its workers;
    - `wall_s` adds up its workers' time, from when each began, as `cpu_s` does.

    The last three are none if no process of its own ever worked the epoch: a
    playback in the API's process or a caller's `execute` shares that process
    with other work, whose figures are not the epoch's, and a report given to an
    epoch kept before reports were written (`usage_reports`) cannot know them. None
    is not zero: no one measured. An epoch resumed that had none, or was worked
    partly so, counts only the workers that reported."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commits: int
    checkpoints: int
    frontier_s: float
    days_computed: float
    bytes_kept: int
    cpu_s: float | None = None
    peak_memory_bytes: int | None = None
    wall_s: float | None = None


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
        with tempfile.TemporaryDirectory() as folder, duckdb.connect() as con:
            con.execute("SET TimeZone='UTC'")
            path = Path(folder) / "segment.parquet"
            path.write_bytes(data)
            # A segment written before a column was added to its log has none
            # of it: read as unset.
            written = {
                row[0]
                for row in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()
            }
            names = ", ".join(
                "NULL"
                if name not in written
                else f"epoch_us({name})"
                if sql == "TIMESTAMPTZ"
                else name
                for name, sql in self.columns
            )
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
        o.scope_id,
    )


def _utc(microseconds: object) -> datetime | None:
    """An instant stored as microseconds from the epoch."""
    if not isinstance(microseconds, int):
        return None
    return EPOCH + timedelta(microseconds=microseconds)


def _observation(row: tuple[object, ...]) -> Observation:
    identity, greenhouse, compartment, plant, at, kind, value, source, source_id = row[:9]
    sensor, delivered, quality, scope = row[9:]
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
            scope_id=scope,
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
        ("scope_id", "VARCHAR"),
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
        # The number of the claim this object took (`claim`), if it took one.
        self._claim: int | None = None
        self._home = f"{run_id}/{epoch}"
        # What this process has used, if it works this epoch and nothing else,
        # and what the epoch's report said before it (`counted_by`).
        self._meter: Callable[[], ProcessUse] | None = None
        self._earlier: EpochUsage | None = None
        # What this process keeps to, if it works this epoch and nothing else
        # (`keep_to`), and whether it has said a limit ended it: from then on it says
        # nothing else of it, whichever of its threads asks.
        self._budget: Budget | None = None
        self._said_past_limit = False
        # Held to say what the epoch is, or to take it: one thread at a time. A thread
        # ending this process holds it to the end (`workers`), so that the thread that
        # works the epoch goes no further than its next such step.
        self.saying = threading.RLock()

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

    def set_status(self, status: Status, *, reason: str | None = None) -> None:
        """Says what the epoch is, and if it failed, why. One said to run is
        held by this process (`leases`) until it is said to have ended, by
        whoever says it, and what it used is reported then, with all it keeps."""
        with self.saying:
            if not self._said_past_limit:
                self._say(status, reason, past_limit=False)

    def end_past_limit(self, reason: str) -> bool:
        """Says the epoch failed for a limit, unless it has ended, and whether it did.
        It keeps what it committed, and can be carried on (`EpochManifest.carries_on`).
        Asked by a thread beside the one that works the epoch, which may be saying how
        it ended: one comes first, and nothing is said after this."""
        with self.saying:
            if self.manifest().status in ENDED:
                return False
            self._say(Status.FAILED, reason, past_limit=True)
            self._said_past_limit = True
            return True

    def _say(self, status: Status, reason: str | None, *, past_limit: bool) -> None:
        before = self.manifest()
        # A worker claimed it before anything else, so this refuses only a process
        # that says an epoch runs with no claim while another works it. Before the
        # write, so that a refusal changes nothing of that other's epoch.
        if status == Status.RUNNING and before.status != Status.RUNNING and not self.claim():
            raise EpochTaken(f"epoch {self.epoch} of {self.run_id} is worked by another")
        if status == Status.QUEUED and before.status in ENDED:
            self._forget_stop()
        said = (reason or NO_REASON_GIVEN) if status == Status.FAILED else None
        manifest = before.model_copy(
            update={"status": status, "reason": said, "past_limit": past_limit}
        )
        self.objects.put(f"{self._home}/manifest.json", manifest.model_dump_json().encode())
        if status in ENDED:
            leases.release(self.objects, self._home)
            self.report_usage()

    def queue_again(
        self,
        *,
        scenario_file: str | None,
        seconds_per_day: float | None,
    ) -> None:
        """Says the epoch waits for a worker again, with what that worker
        needs, in one write."""
        self._forget_stop()
        manifest = self.manifest().model_copy(
            update={
                "status": Status.QUEUED,
                "reason": None,
                "scenario_file": scenario_file,
                "seconds_per_day": seconds_per_day,
                "queued_at": datetime.now(UTC),
                "resumed": True,
                "past_limit": False,
            }
        )
        self.objects.put(f"{self._home}/manifest.json", manifest.model_dump_json().encode())

    def budget(self) -> Budget | None:
        """What its worker keeps to: none if no scheduler put it in line, or if what
        one wrote cannot be read, as a later version's might not be, which is no reason
        for a server not to start: one that takes the epoch up writes it again."""
        data = self.objects.get(f"{self._home}/{_BUDGET}")
        try:
            return None if data is None else Budget.model_validate_json(data)
        except ValidationError:
            logger.warning("the budget of %s cannot be read", self._home)
            return None

    def give_budget(self, budget: Budget) -> None:
        """Says what its next worker keeps to. One that has read it already keeps to
        what it read."""
        self.objects.put(f"{self._home}/{_BUDGET}", budget.model_dump_json().encode())

    def claim(self, *, now: float | None = None) -> bool:
        """Takes the epoch for this process, and says whether it has it: refused
        while another's claim is fresh, and to all but one of any who ask at once
        (`leases`). Held until the epoch is told it ended, or `let_go`."""
        with self.saying:
            if self.claimed():
                return True
            self._claim = leases.claim(self.objects, self._home, now=now)
            if self._claim is None:
                return False
            leases.keep(self.objects, self._home, self._claim)
            return True

    def claimed(self) -> bool:
        """Whether this object took the claim that stands."""
        return self._claim is not None and self._claim == leases.newest(self.objects, self._home)

    def let_go(self) -> None:
        """Gives up this object's claim, if it stands, with the epoch as it is."""
        if self.claimed():
            leases.release(self.objects, self._home, self._claim)

    def end_unless_worked(self, status: Status, *, now: float | None = None) -> bool:
        """Says the epoch ended, unless a process works it or it has ended already,
        and says whether it did. Held while it is said, so that a worker taking the
        epoch up is told apart: one that came first keeps it, and one that comes
        after finds it ended."""
        if leases.claim(self.objects, self._home, now=now) is None:
            return False
        if self.manifest().status in ENDED:
            leases.release(self.objects, self._home)
            return False
        self.set_status(status)
        return True

    def worked(self, *, now: float | None = None) -> bool:
        """Whether a process holds the epoch's claim."""
        return leases.alive(self.objects, self._home, now=now)

    def ask_to_stop(self) -> None:
        """Asks whichever worker has the epoch to stop, at its next look. Asked
        twice, it is asked once."""
        self.objects.put(f"{self._home}/{_STOP_ASKED}", b"{}")

    def stop_asked(self) -> bool:
        """Whether the epoch's worker has been asked to stop. Only the asker's
        side writes this: a worker reads it and ends, and the object stays, of no
        effect, until the epoch waits for a worker again."""
        return self.objects.size(f"{self._home}/{_STOP_ASKED}") is not None

    def _forget_stop(self) -> None:
        """What was asked of the work that ended is not asked of the work that
        carries it on. Before the epoch is said to wait, so that a stop asked of
        it while it waits is kept."""
        self.objects.delete(f"{self._home}/{_STOP_ASKED}")

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
        they have just been, the report of what it used aside."""
        names = self.objects.names(f"{self._home}/") if listed is None else listed
        report = f"{self._home}/{USAGE}"
        return sum(self.objects.size(name) or 0 for name in names if name != report)

    def usage(self) -> EpochUsage | None:
        """What the epoch's report says it used: none if it has none, as an
        epoch has before its first commit or from before they were written, or
        one that cannot be read, which is a report and fails nothing."""
        try:
            data = self.objects.get(f"{self._home}/{USAGE}")
            return None if data is None else EpochUsage.model_validate_json(data)
        except OSError, ValidationError:
            logger.warning("the report of what %s used cannot be read", self._home, exc_info=True)
            return None

    def counted_by(self, meter: Callable[[], ProcessUse]) -> None:
        """Says this process works the epoch and nothing else, and that `meter`
        says what it has used. What the epoch's earlier workers used is read
        now and once, so that each report adds this process's whole to it."""
        self._earlier = self.usage()
        self._meter = meter

    def keep_to(self, budget: Budget) -> None:
        """Says this process ends the epoch at a commit past the budget's bytes."""
        self._budget = budget

    def used_so_far(self) -> ProcessUse:
        """What the epoch has used, as `counted_by` counts it: its workers' seconds,
        and the memory this one has held."""
        assert self._meter is not None
        used = self._meter()
        earlier = self._earlier
        return ProcessUse(
            used.cpu_s + (0.0 if earlier is None else earlier.cpu_s or 0.0),
            used.peak_memory_bytes,
            used.wall_s + (0.0 if earlier is None else earlier.wall_s or 0.0),
        )

    def report_usage(self, commits: Sequence[Commit] | None = None) -> EpochUsage | None:
        """Writes what the epoch has used, through `commits` if they have just
        been read, and says it. A report that cannot be written is logged and ends
        nothing: the disk that refuses it refuses the next commit too, and that says
        so."""
        try:
            return self.write_usage(self.commits() if commits is None else commits)
        except Exception:
            logger.warning("what %s used could not be reported", self._home, exc_info=True)
            return None

    def write_usage(self, commits: Sequence[Commit]) -> EpochUsage:
        """Writes what the epoch has used through `commits`, and raises if it
        cannot, for a caller with nothing else to do (`usage_reports`)."""
        usage = self._usage_now(commits)
        self.objects.put(f"{self._home}/{USAGE}", usage.model_dump_json().encode())
        return usage

    def _usage_now(self, commits: Sequence[Commit]) -> EpochUsage:
        fork = self.manifest().fork
        start_s = 0.0 if fork is None else fork.start_s
        frontier_s = commits[-1].end_s if commits else start_s
        inherited = fork is not None and fork.checkpoint_sha256 is not None
        kept = sum(commit.checkpoint is not None for commit in commits)
        before = self.usage() if self._meter is None else self._earlier
        cpu_s = None if before is None else before.cpu_s
        wall_s = None if before is None else before.wall_s
        peak = None if before is None else before.peak_memory_bytes
        if self._meter is not None:
            used = self._meter()
            cpu_s = (cpu_s or 0.0) + used.cpu_s
            wall_s = (wall_s or 0.0) + used.wall_s
            peak = max(peak or 0, used.peak_memory_bytes)
        return EpochUsage(
            commits=len(commits),
            checkpoints=kept + inherited,
            frontier_s=frontier_s,
            days_computed=(frontier_s - start_s) / DAY_S,
            bytes_kept=self.size_bytes(),
            cpu_s=cpu_s,
            peak_memory_bytes=peak,
            wall_s=wall_s,
        )

    def holds_as_counted(self, usage: EpochUsage) -> bool:
        """Whether the epoch's folders agree with its report: as many commits,
        and no fewer segments and checkpoints, since those of a commit are
        written before it. One listing of each and no object read, which a list
        of many epochs can afford, and so no sight of a file lost from inside a
        segment's folder, which only `lacks` has."""
        home = self._home
        return (
            len(self.objects.children(f"{home}/commits/")) == usage.commits
            and len(self.objects.children(f"{home}/segments/")) >= usage.commits
            and len(self.objects.children(f"{home}/checkpoints/")) >= usage.checkpoints
        )

    def lacks(
        self, manifest: EpochManifest, commits: Sequence[Commit], listed: Iterable[str]
    ) -> bool:
        """Whether an object that `commits` name, or the state a fork inherits,
        is missing from what was `listed` of the epoch after they were read, or
        an epoch that finished stops short of its end: its last commits, lost,
        leave no gap to see. A writer puts up what a commit names before the
        commit, and says it finished after its last, so that an epoch being worked
        is never told so. No object is read: `verify` says whether those held are
        what their commits name."""
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
        if written > len(commits) and next_commit not in held:
            return True
        return (
            manifest.status == Status.FINISHED
            and manifest.duration_s is not None
            and (not commits or commits[-1].end_s < manifest.duration_s)
        )

    def damaged(self, commits: Sequence[Commit]) -> bool:
        """Whether files `commits`, just read, say it holds are missing (`lacks`): one
        listing of the epoch's objects, which is what a list does not afford and
        anything that takes up one epoch does."""
        listed = self.objects.names(f"{self._home}/")
        return self.lacks(self.manifest(), commits, listed)

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
        self._end_if_past_bytes(self.report_usage([*commits, made]), end_s)
        return made

    def _end_if_past_bytes(self, usage: EpochUsage | None, end_s: float) -> None:
        """Ends the epoch at the commit just made if it keeps more than its budget lets
        it, unless that was its last: all its days are kept, and it has finished."""
        reason = (
            None
            if self._budget is None or usage is None
            else self._budget.bytes_past(usage.bytes_kept)
        )
        if reason is None:
            return
        duration_s = self.manifest().duration_s
        if duration_s is None or end_s < duration_s:
            self.end_past_limit(reason)
            raise LimitPassed(reason)

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
        requests and answers, which no commit names, and the report of what it
        used, which its next worker adds to. The names removed."""
        commits = self.commits()
        kept = {
            f"{self._home}/manifest.json",
            f"{self._home}/interventions.jsonl",
            f"{self._home}/{USAGE}",
            f"{self._home}/{_BUDGET}",
        }
        kept.add(f"{self._home}/{_INHERITED_OUTCOMES}")
        fork = self.manifest().fork
        if fork is not None and fork.checkpoint_sha256 is not None:
            kept.add(self._inherited_name(fork))
        for commit in commits:
            kept.add(f"{self._home}/commits/{commit.seq:0{SEQ_DIGITS}d}.json")
            kept.update(f"{self._home}/segments/{commit.segment}/{kind}.parquet" for kind in Kind)
            if commit.checkpoint is not None:
                kept.add(commit.checkpoint)
        # By their names and not by a listing, in which one asked meanwhile
        # would be missing: the asker is in another process.
        spared = (
            f"{self._home}/requests/",
            f"{self._home}/answers/",
            f"{self._home}/{_STOP_ASKED}",
        )
        removed = []
        for name in self.objects.names(f"{self._home}/"):
            if (
                name not in kept
                and name != f"{self._home}/{leases.LEASE}"
                and not name.startswith(f"{self._home}/{leases.CLAIMS}/")
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
    # Whether the playback that computes it here holds its clock: the status of
    # an epoch running, which only the process of that playback knows
    # (`runs_kept`), so the store never says so.
    paused: bool = False
    frontier_s: float
    duration_s: float | None
    progress: float | None
    created_at: datetime | None
    size_bytes: int
    # Where what it holds begins, and for a fork where it comes from.
    start_s: float = 0.0
    fork: ForkOf | None = None
    # Whether its worker has been asked through the store to stop and has not
    # yet: it reads `running` until its worker looks, or `interrupted` is found.
    stopping: bool = False
    # Whether files of it are missing (`EpochStore.lacks`), so that it cannot be
    # read whole. Said from the names of its objects, not from their contents: in a
    # list, from how many its folders hold (`EpochStore.holds_as_counted`).
    damaged: bool = False
    # What it has used (`EpochUsage`): the days it has computed itself, and the
    # seconds of a core, the most memory and the seconds from each start its
    # workers took, none if none of them reported any.
    days_computed: float = 0.0
    cpu_s: float | None = None
    peak_memory_bytes: int | None = None
    wall_s: float | None = None
    # Why it failed, if it did and it says; and whether it was a limit, which
    # alone of failures can be carried on (`EpochManifest.carries_on`).
    reason: str | None = None
    past_limit: bool = False


def _shown(
    run_id: str,
    manifest: EpochManifest,
    *,
    frontier_s: float,
    size_bytes: int,
    usage: EpochUsage | None,
    stopping: bool,
    damaged: bool,
) -> StoredRun:
    start_s = 0.0 if manifest.fork is None else manifest.fork.start_s
    return StoredRun(
        run_id=run_id,
        epoch=manifest.epoch,
        scenario_id=manifest.scenario_id,
        seed=manifest.seed,
        layout=manifest.layout,
        status=manifest.status,
        frontier_s=frontier_s,
        duration_s=manifest.duration_s,
        progress=None if not manifest.duration_s else frontier_s / manifest.duration_s,
        created_at=manifest.created_at,
        size_bytes=size_bytes,
        start_s=start_s,
        fork=manifest.fork,
        stopping=stopping,
        damaged=damaged,
        days_computed=(frontier_s - start_s) / DAY_S,
        cpu_s=None if usage is None else usage.cpu_s,
        peak_memory_bytes=None if usage is None else usage.peak_memory_bytes,
        wall_s=None if usage is None else usage.wall_s,
        reason=manifest.reason,
        past_limit=manifest.past_limit,
    )


def stored_run(objects: ObjectStore, run_id: str, epoch_number: int) -> StoredRun:
    """One epoch as a list of them shows it, walked: its commits, and the names
    of its objects, listed after the commits so that all they name are there,
    which says for certain whether it is damaged. Its size is asked of each
    object only if its report is missing or behind its commits."""
    epoch = EpochStore(objects, run_id, epoch_number)
    manifest = epoch.manifest()
    commits = epoch.commits()
    listed = objects.names(f"{run_id}/{epoch_number}/")
    usage = epoch.usage()
    current = usage is not None and usage.commits == len(commits)
    return _shown(
        run_id,
        manifest,
        frontier_s=commits[-1].end_s if commits else epoch.start_s(),
        size_bytes=usage.bytes_kept if usage is not None and current else epoch.size_bytes(listed),
        usage=usage,
        stopping=manifest.status not in ENDED
        and f"{run_id}/{epoch_number}/{_STOP_ASKED}" in listed,
        damaged=epoch.lacks(manifest, commits, listed),
    )


def _listed(objects: ObjectStore, run_id: str, manifest: EpochManifest) -> StoredRun:
    """One epoch of a list: from its report, if its folders agree with it. If
    they do not, or it has none, it is walked: one is behind a crash, or has lost
    something, and one from before reports were written costs what it always
    did, since nothing else knows its size and a list writes nothing, until a
    command gives it a report (`usage_reports`)."""
    epoch = EpochStore(objects, run_id, manifest.epoch)
    usage = epoch.usage()
    if usage is None or not epoch.holds_as_counted(usage):
        return stored_run(objects, run_id, manifest.epoch)
    return _shown(
        run_id,
        manifest,
        frontier_s=usage.frontier_s,
        size_bytes=usage.bytes_kept,
        usage=usage,
        stopping=manifest.status not in ENDED and epoch.stop_asked(),
        damaged=False,
    )


def held_bytes(objects: ObjectStore) -> int:
    """How many bytes a store holds, as far as its epochs' reports say, which may lag
    a worker by a commit: each epoch costs its report, and the walk of one with none;
    what is under a folder that holds no epoch, such as the scenarios' shared files,
    is walked, and a report's own bytes are not counted."""
    total = 0
    for top in objects.children():
        numbers = [name for name in objects.children(f"{top}/") if name.isdigit()]
        if not numbers:
            total += sum(objects.size(name) or 0 for name in objects.names(f"{top}/"))
        for number in numbers:
            epoch = EpochStore(objects, top, int(number))
            usage = epoch.usage()
            total += epoch.size_bytes() if usage is None else usage.bytes_kept
    return total


def stored_runs(objects: ObjectStore, scenario_id: str | None = None) -> list[StoredRun]:
    """The epochs a store holds, those of `scenario_id` if given, by run and
    epoch. An epoch costs its manifest, its report and a listing of three of its
    folders, however long it is (`_listed`)."""
    found = []
    for run_id in objects.children():
        numbers = sorted(int(name) for name in objects.children(f"{run_id}/") if name.isdigit())
        for number in numbers:
            data = objects.get(f"{run_id}/{number}/manifest.json")
            if data is None:
                continue
            manifest = EpochManifest.model_validate_json(data)
            if scenario_id is None or manifest.scenario_id == scenario_id:
                found.append(_listed(objects, run_id, manifest))
    return found
