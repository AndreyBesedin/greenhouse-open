"""A policy's port on a run played back, in the simulator's process (P15.3,
decision 0061): what a control policy reads of the run and gives it, as
its own principal, by the protocol's contract
(`greenhouse_protocol.contracts.policy`).

A port is opened on a playback for one principal (`policy_port`). Every
plan, revision and cancellation it gives goes to the run's gateway as that
principal; the authorisation in force decides the rest. It reads:

- its **context,** the run's for its principal (`policy_context`);
- its **budget:** the observations and the clock alone. Forecasts come
  with P15.6, so its forecast log stays empty;
- the run's **observations,** of the types its context's sources observe;
- the run's **events,** each with only the parameters its type lets a
  policy read;
- the **outcomes** of the plans its principal owns, and those **plans.**

Its logs are its own. Each holds what its principal may read of the
run's log, in the run's order, so its positions are not the run's, and
its cursors are given and checked apart from the consumer interface's
(`consumer.Cursors`), by the same rules. A new epoch starts them again.

The port is trusted code in the simulator's process, held to the contract
by `check_policy_port` and to its imports by the repository's dependency
test. Neither is a sandbox.
"""

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final, Protocol

from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
    RunDescriptor,
)
from greenhouse_protocol.contracts.gateway import PlanState, Receipt
from greenhouse_protocol.contracts.policy import readable_event
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.event import Event
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import ActionKey, Plan, Principal

from greenhouse_sim.services.consumer import (
    Cursors,
    batch_cursor,
    batch_limit,
    run_descriptor,
)
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.playback import Playbacks, PlaybackState, RecordsAfter

# How many of the run's records a port reads at once, catching up.
READ_AT_ONCE: Final = 5_000
# Before any epoch: a port's logs start at the first one it reads.
NO_EPOCH: Final = -1


class PlayedRun(Protocol):
    """What a port reads of and gives to a run played back: a playback's."""

    def state(self) -> PlaybackState: ...

    def context(self, principal: Principal) -> CapabilityContext: ...

    def records_after(self, after: int, limit: int) -> RecordsAfter[Observation]: ...

    def events_after(self, after: int, limit: int) -> RecordsAfter[Event]: ...

    def outcomes_after(self, after: int, limit: int) -> tuple[OutcomeBatch, PlaybackState]: ...

    def plan(self, plan_id: str, revision: int | None = None) -> PlanState: ...

    def submit(self, plan: Plan, *, by: Principal) -> Receipt: ...

    def cancel(self, keys: Sequence[ActionKey], *, by: Principal) -> Receipt: ...

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int, by: Principal) -> Receipt: ...


@dataclass
class _Kept[RecordT]:
    """What a port keeps of one of its run's logs in an epoch: the records
    its principal reads, in the log's order, and how far into the run's log
    it has read."""

    epoch: int = NO_EPOCH
    read: int = 0
    records: list[RecordT] = field(default_factory=list)


@dataclass(frozen=True)
class _Cut[RecordT]:
    """A cut of a run's log: its records after a position, the position
    after them, whether it has more, and the state it was cut at."""

    records: Sequence[RecordT]
    next: int
    has_more: bool
    state: PlaybackState


@dataclass(frozen=True)
class _Answer[RecordT]:
    """What a port answers of one of its logs: the records after a cursor,
    the cursor after them, whether it has more, and the run's state."""

    records: tuple[RecordT, ...]
    after: int
    next: int
    has_more: bool
    state: PlaybackState


class RunPolicyPort:
    """A policy's port on a run played back, for one principal: see the
    module."""

    def __init__(self, played: PlayedRun, principal: Principal) -> None:
        self._played = played
        self.principal = principal
        self._lock = threading.Lock()
        self._cursors = Cursors()
        self._observations: _Kept[Observation] = _Kept()
        self._events: _Kept[Event] = _Kept()
        self._outcomes: _Kept[ActionOutcome] = _Kept()
        # The types its context's sources observe, in an epoch.
        self._observed: tuple[int, frozenset[ObservationType]] = (NO_EPOCH, frozenset())
        # Who owns each plan of an epoch, once asked.
        self._owners: dict[tuple[int, str], Principal] = {}

    def run(self) -> RunDescriptor:
        return run_descriptor(self._played.state())

    def context(self) -> CapabilityContext:
        return self._played.context(self.principal)

    def budget(self) -> InformationBudget:
        return OBSERVATIONS_ONLY

    def observations(self, after: int = 0, limit: int | None = None) -> ObservationBatch:
        answer = self._answer(
            "observations",
            self._observations,
            self._read_observations,
            self._observed_now,
            after=after,
            limit=limit,
        )
        return ObservationBatch(
            run_id=answer.state.run_id,
            epoch=answer.state.epoch,
            after=answer.after,
            next=answer.next,
            simulated_now=answer.state.simulated_now,
            has_more=answer.has_more,
            observations=answer.records,
        )

    def events(self, after: int = 0, limit: int | None = None) -> EventBatch:
        answer = self._answer(
            "events",
            self._events,
            self._read_events,
            lambda event, _: readable_event(event),
            after=after,
            limit=limit,
        )
        return EventBatch(
            run_id=answer.state.run_id,
            epoch=answer.state.epoch,
            after=answer.after,
            next=answer.next,
            simulated_now=answer.state.simulated_now,
            has_more=answer.has_more,
            events=answer.records,
        )

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch:
        answer = self._answer(
            "outcomes", self._outcomes, self._read_outcomes, self._owned, after=after, limit=limit
        )
        return OutcomeBatch(
            run_id=answer.state.run_id,
            epoch=answer.state.epoch,
            after=answer.after,
            next=answer.next,
            simulated_now=answer.state.simulated_now,
            has_more=answer.has_more,
            outcomes=answer.records,
        )

    def forecasts(self, after: int = 0, limit: int | None = None) -> ForecastBatch:
        """None: its budget has no forecast provider."""
        cursor = batch_cursor(after)
        batch_limit(limit)
        state = self._played.state()
        return ForecastBatch(
            run_id=state.run_id,
            epoch=state.epoch,
            after=cursor,
            next=cursor,
            simulated_now=state.simulated_now,
            forecasts=(),
        )

    def plan(self, plan_id: str) -> PlanState | None:
        try:
            found = self._played.plan(plan_id)
        except NotFound:
            return None
        return found if found.owner == self.principal else None

    def submit(self, plan: Plan) -> Receipt:
        return self._played.submit(plan, by=self.principal)

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int) -> Receipt:
        return self._played.cancel_plan(plan_id, revision=revision, epoch=epoch, by=self.principal)

    def cancel(self, keys: Sequence[ActionKey]) -> Receipt:
        return self._played.cancel(keys, by=self.principal)

    # Its logs.

    def _answer[RecordT](
        self,
        log: str,
        kept: _Kept[RecordT],
        read: Callable[[int], _Cut[RecordT]],
        keep: Callable[[RecordT, int], RecordT | None],
        *,
        after: int | None,
        limit: int | None,
    ) -> _Answer[RecordT]:
        """The records of one of its logs after a cursor, the run's log read
        on as far as its clock and kept as its principal reads it; none
        after a cursor it never gave in the epoch, as the consumer
        interface answers."""
        cursor, most = batch_cursor(after), batch_limit(limit)
        with self._lock:
            state = self._caught_up(kept, read, keep)
            known = self._cursors.knows(state.run_id, log, kept.epoch, cursor)
            chosen = tuple(kept.records[cursor : cursor + most]) if known else ()
            if known:
                self._cursors.give(state.run_id, log, kept.epoch, cursor + len(chosen))
            return _Answer(
                records=chosen,
                after=cursor,
                next=cursor + len(chosen),
                has_more=known and cursor + len(chosen) < len(kept.records),
                state=state,
            )

    @staticmethod
    def _caught_up[RecordT](
        kept: _Kept[RecordT],
        read: Callable[[int], _Cut[RecordT]],
        keep: Callable[[RecordT, int], RecordT | None],
    ) -> PlaybackState:
        """Reads the run's log on from where it last read, keeping what its
        principal reads: from its start again in a new epoch."""
        while True:
            cut = read(kept.read)
            if cut.state.epoch != kept.epoch:
                kept.epoch, kept.read, kept.records = cut.state.epoch, 0, []
                cut = read(0)
            kept.records += [
                kept_record
                for record in cut.records
                if (kept_record := keep(record, cut.state.epoch)) is not None
            ]
            kept.read = cut.next
            if not cut.has_more:
                return cut.state

    def _read_observations(self, after: int) -> _Cut[Observation]:
        cut = self._played.records_after(after, READ_AT_ONCE)
        return _Cut(cut.records, cut.next, cut.has_more, cut.state)

    def _read_events(self, after: int) -> _Cut[Event]:
        cut = self._played.events_after(after, READ_AT_ONCE)
        return _Cut(cut.records, cut.next, cut.has_more, cut.state)

    def _read_outcomes(self, after: int) -> _Cut[ActionOutcome]:
        cut, state = self._played.outcomes_after(after, READ_AT_ONCE)
        return _Cut(cut.outcomes, cut.next, cut.has_more, state)

    def _observed_now(self, observation: Observation, epoch: int) -> Observation | None:
        if self._observed[0] != epoch:
            self._observed = (epoch, self.context().observed_types())
        return observation if observation.observation_type in self._observed[1] else None

    def _owned(self, outcome: ActionOutcome, epoch: int) -> ActionOutcome | None:
        key = (epoch, outcome.plan_id)
        if key not in self._owners:
            self._owners[key] = self._played.plan(outcome.plan_id).owner
        return outcome if self._owners[key] == self.principal else None


def policy_port(playbacks: Playbacks, run_id: str, principal: Principal) -> RunPolicyPort:
    """A port for `principal` on the run `run_id` played back; a run not
    played back is not found."""
    return RunPolicyPort(playbacks.of_run(run_id), principal)
