"""The consumer interface: how a client reads a running producer.

A producer is anything that makes canonical records as time passes: a
simulator run, a gateway in front of a real greenhouse's sensors, a bridge
to a third-party feed. A consumer is anything that wants those records as
they come: a dashboard, a policy, a store. This module is the contract
between them, so that one client reads any producer and a producer serves
any client, and neither learns the other's internals. Its first producer is
the simulator; the interface's shape belongs here, not to it.

A consumer reaches **observed records only**: what sensors reported and what
happened. It reaches no truth, no model state, no scene, and nothing a
policy could cheat with (decision 0036). That is a property of the
interface, not a courtesy of one server, and `check_batch` holds a producer
to the part of it that can be checked from the outside.

## Routes

Every route is `GET`, answers JSON, and lives under `/consumer/v1`, the
`CONSUMER_INTERFACE_VERSION`. A breaking change to a payload or a rule here
is a new version segment; the old one may be served beside it.

    /consumer/v1/runs                              -> RunList
    /consumer/v1/runs/{run_id}                     -> RunDescriptor
    /consumer/v1/runs/{run_id}/greenhouse          -> GreenhouseDescription
    /consumer/v1/runs/{run_id}/observations?after= -> ObservationBatch
    /consumer/v1/runs/{run_id}/events?after=       -> EventBatch

An unknown run is `404`. `after` is a cursor (below), `0` when omitted;
`limit` caps a batch's size and a producer may cap it lower.

## Runs, epochs and the clock

A **run** is one producer's timeline, named by a `run_id` that is stable
for as long as the producer serves it. Its **epoch** counts the times that
timeline started over: a simulator that loops its scenario, a producer
restarted from day one, a gateway re-initialised. Each epoch starts at
`started_at`, day 0, and its records' identities may repeat those of the
epoch before, since a deterministic run makes the same records again. So a
consumer keys what it stores by `(run_id, epoch)` as well as by record id,
and treats a new epoch as a new timeline, never as time going backwards.

The run's **clock** is the simulated instant the producer has reached. A
batch says what the clock read when it was cut (`simulated_now`), and no
record in it was delivered after that: a consumer at `simulated_now` sees
nothing from its own future.

## Cursors and batches

Each run keeps two append-only logs, its observations and its events, in
**delivery order**: the order in which the records reached the producer,
which is the order of each record's `delivered_at`, or its `timestamp`
when it was delivered as it was taken. A reading taken on day 1 and
delivered on day 2 sits in the log among day 2's records, so a consumer
that follows the log sees records arrive as the producer did, late ones
included, and no record ever appears earlier than it could have been known.

A **cursor** is a count of records delivered so far in one log, so `0` is
before the first. A batch answers `after=c` with the records at positions
`c+1 .. c+n`, in order, and `next = c + n`; when nothing new has come,
`next == after` and the batch is empty. `has_more` says the producer cut
the batch short of what it held, and the client should poll again at once.

The rules a producer keeps, which `check_batch` and `check_polls` test:

- `next == after + len(records)`: positions are dense, and a batch is the
  log's slice, nothing filtered out of it.
- Delivery order within a batch is non-decreasing, and every record was
  delivered at or before `simulated_now`.
- The record at a position never changes: two polls of the same epoch
  that both reach a position hold the same record there, the record
  itself and not only its identity. A log is appended to, never
  rewritten, so a repoll duplicates nothing a client already stored.
- Delivery order holds across batches as within one: the first record of
  a batch was delivered no earlier than the last of the batch before it.
- Within an epoch, a non-empty batch's `after` is `0` or a `next` the
  producer gave before: a client cannot be answered from a position it was
  never given. A cursor from an earlier epoch is answered with an empty
  batch of the current epoch at the same `after`; the client sees the epoch
  change and starts again from `0`.
- An epoch never decreases, and within an epoch the clock never turns
  back: consecutive batches' `simulated_now` are non-decreasing. A
  timeline that starts over is a new epoch, not an earlier clock.
- Every record names the run's greenhouse. A batch does not carry the
  run's `greenhouse_id`, so a client checks it against the run
  descriptor's: `check_batch(batch, greenhouse_id=run.greenhouse_id)`.

## Fixtures

`greenhouse_protocol/tests/fixtures/consumer/exchange.json` is a recorded
exchange: the requests a client made, in order, and what a conforming
producer answered, over three simulated days, with a late reading, a cut
batch, a repoll, a harvest, and a restart. A client is developed against it
before any producer serves it, and a producer's answers are compared with
it; `tests/test_consumer_fixture.py` writes it and holds it to the rules.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from greenhouse_protocol.contracts.conformance import check_events, check_observations
from greenhouse_protocol.event import Event
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.observation import Observation

# The path segment every route of this version lives under.
CONSUMER_INTERFACE_VERSION: Final = "v1"
CONSUMER_PREFIX: Final = f"/consumer/{CONSUMER_INTERFACE_VERSION}"
# The first cursor: before any record.
FIRST_CURSOR: Final = 0
# The first epoch of a run.
FIRST_EPOCH: Final = 0


class RunClock(BaseModel):
    """Where a run's timeline stands: the simulated instant it has reached,
    which day of its epoch that is, and whether it is advancing."""

    model_config = ConfigDict(frozen=True)

    simulated_now: Instant
    # Days since the epoch's start, 0 on the day it started.
    day: int = Field(ge=0)
    playing: bool


class RunDescriptor(BaseModel):
    """A run as a consumer sees it: its identity, its epoch, the greenhouse
    it describes, and its clock."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    epoch: int = Field(ge=0)
    greenhouse_id: str = Field(min_length=1)
    # What the producer calls what it runs, for people; a consumer keys on
    # run_id and epoch, never on this.
    scenario: str | None = None
    # The simulated instant this epoch began: day 0.
    started_at: Instant
    clock: RunClock
    interface_version: str = CONSUMER_INTERFACE_VERSION


class RunList(BaseModel):
    model_config = ConfigDict(frozen=True)

    runs: tuple[RunDescriptor, ...]


class ObservationBatch(BaseModel):
    """The observations delivered after a cursor, in delivery order."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    epoch: int = Field(ge=0)
    after: int = Field(ge=0)
    next: int = Field(ge=0)
    simulated_now: Instant
    has_more: bool = False
    observations: tuple[Observation, ...]

    @property
    def records(self) -> tuple[Observation, ...]:
        return self.observations


class EventBatch(BaseModel):
    """The events delivered after a cursor, in delivery order."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    epoch: int = Field(ge=0)
    after: int = Field(ge=0)
    next: int = Field(ge=0)
    simulated_now: Instant
    has_more: bool = False
    events: tuple[Event, ...]

    @property
    def records(self) -> tuple[Event, ...]:
        return self.events


type Batch = ObservationBatch | EventBatch


def delivered_at(record: Observation | Event) -> datetime:
    """When a record reached the producer: its delivery time, or the instant
    it describes when it was delivered as it was taken."""
    if isinstance(record, Observation) and record.delivered_at is not None:
        return record.delivered_at
    return record.timestamp


def record_id(record: Observation | Event) -> str:
    return record.observation_id if isinstance(record, Observation) else record.event_id


def check_run(run: RunDescriptor) -> list[str]:
    """What a run descriptor must say, beyond what its model enforces."""
    violations = []
    if run.clock.simulated_now < run.started_at:
        violations.append(
            f"run {run.run_id!r} epoch {run.epoch} reads {run.clock.simulated_now.isoformat()}, "
            f"before it started ({run.started_at.isoformat()})"
        )
    if run.interface_version != CONSUMER_INTERFACE_VERSION:
        violations.append(
            f"run {run.run_id!r} speaks interface {run.interface_version!r}, "
            f"not {CONSUMER_INTERFACE_VERSION!r}"
        )
    return violations


def check_batch(batch: Batch, *, greenhouse_id: str | None = None) -> list[str]:
    """What one batch must satisfy on its own: dense positions, delivery
    order, nothing from after its clock, conforming records, and, given the
    run's `greenhouse_id`, records of that greenhouse only."""
    label = _label(batch)
    violations: list[str] = []
    if batch.next < batch.after:
        violations.append(f"{label} goes backwards: next {batch.next} < after {batch.after}")
    elif batch.next != batch.after + len(batch.records):
        violations.append(
            f"{label} holds {len(batch.records)} record(s) but moves the cursor by "
            f"{batch.next - batch.after}: positions must be dense"
        )
    previous: datetime | None = None
    for record in batch.records:
        if greenhouse_id is not None and record.greenhouse_id != greenhouse_id:
            violations.append(
                f"{label} delivers {record_id(record)!r} of greenhouse "
                f"{record.greenhouse_id!r}, not the run's ({greenhouse_id!r})"
            )
        delivered = delivered_at(record)
        if delivered.tzinfo is None or delivered.utcoffset() is None:
            # The record checks below report it; delivery order cannot be
            # judged against an ambiguous time.
            continue
        if previous is not None and delivered < previous:
            violations.append(
                f"{label} is out of delivery order at {record_id(record)!r}: "
                f"{delivered.isoformat()} after {previous.isoformat()}"
            )
        if delivered > batch.simulated_now:
            violations.append(
                f"{label} delivers {record_id(record)!r} at {delivered.isoformat()}, "
                f"after its clock ({batch.simulated_now.isoformat()})"
            )
        previous = delivered
    if isinstance(batch, ObservationBatch):
        violations += check_observations(batch.observations)
    else:
        violations += check_events(batch.events)
    return violations


def check_polls(batches: Iterable[Batch], *, greenhouse_id: str | None = None) -> list[str]:
    """What a sequence of batches of one log, as a client received them,
    must satisfy together: epochs that never decrease, a clock that never
    turns back within one, repolls that extend rather than rewrite, cursors
    the producer gave, and no record twice."""
    polls = list(batches)
    violations: list[str] = []
    for batch in polls:
        violations += check_batch(batch, greenhouse_id=greenhouse_id)
    if len({batch.run_id for batch in polls}) > 1:
        violations.append(f"the polls name several runs: {sorted({b.run_id for b in polls})}")

    epoch = -1
    given: set[int] = set()
    seen: dict[str, int] = {}
    # The log as the polls revealed it, the record at each position: a
    # repoll must hold the same record there, not only the same identity.
    log: dict[int, Observation | Event] = {}
    clock: datetime | None = None
    for index, batch in enumerate(polls):
        label = f"{_label(batch)} (poll {index})"
        if batch.epoch < epoch:
            violations.append(f"{label} returns to epoch {batch.epoch}")
        if batch.epoch != epoch:
            epoch, given, seen, log, clock = batch.epoch, {FIRST_CURSOR}, {}, {}, None
        if clock is not None and batch.simulated_now < clock:
            violations.append(
                f"{label} turns the clock back within epoch {epoch}: "
                f"{batch.simulated_now.isoformat()} after {clock.isoformat()}; "
                "a timeline that starts over is a new epoch"
            )
        clock = batch.simulated_now if clock is None else max(clock, batch.simulated_now)
        records: list[Observation | Event] = list(batch.records)
        if records and batch.after not in given:
            violations.append(
                f"{label} answers after={batch.after}, "
                "a cursor the producer never gave in this epoch"
            )
        for position, record in enumerate(records, start=batch.after + 1):
            identity = record_id(record)
            earlier = log.get(position)
            if earlier is not None and earlier != record:
                violations.append(
                    f"{label} rewrites the log at position {position}: {identity!r} is not "
                    f"the record delivered there before ({record_id(earlier)!r})"
                )
            log.setdefault(position, record)
            delivered_before = seen.get(identity)
            if delivered_before is not None and delivered_before != position:
                violations.append(
                    f"{label} delivers {identity!r} again, "
                    f"at position {position} after position {delivered_before}"
                )
            seen.setdefault(identity, position)
            before = log.get(position - 1)
            if before is not None and delivered_at(record) < delivered_at(before):
                violations.append(
                    f"{label} is out of delivery order across batches: {identity!r} at position "
                    f"{position} ({delivered_at(record).isoformat()}) was delivered before "
                    f"position {position - 1} ({delivered_at(before).isoformat()})"
                )
        given.add(batch.next)
    return violations


def _label(batch: Batch) -> str:
    kind = "observations" if isinstance(batch, ObservationBatch) else "events"
    return f"{kind} batch of run {batch.run_id!r} epoch {batch.epoch} after={batch.after}"
