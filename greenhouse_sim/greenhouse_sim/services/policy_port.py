"""A policy's port on a run played back, in the simulator's process (P15.3,
decision 0061): what a control policy reads of the run and gives it, as
its own principal, by the protocol's contract
(`greenhouse_protocol.contracts.policy`).

A port is opened on a playback for one principal (`policy_port`). Every
plan, revision and cancellation it gives goes to the run's gateway as that
principal; the authorisation in force decides the rest. It reads:

- its **context,** the run's for its principal (`policy_context`);
- its **budget,** given when it is opened: the observations and the clock
  alone, or also the forecasts of providers the simulator serves
  (`services.forecasts`). A budget the port cannot serve is refused when
  it is opened;
- the run's **observations,** of the types its context's sources observe;
- the **forecasts** of its budget's providers, each no earlier than it was
  issued, made from the observations it has read;
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
from datetime import datetime
from typing import Final, Protocol

from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBasis, InformationBudget
from greenhouse_protocol.context import CapabilityContext
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
    RunDescriptor,
)
from greenhouse_protocol.contracts.gateway import PlanState, Receipt
from greenhouse_protocol.contracts.policy import readable_event, readable_forecast
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.event import Event
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import ActionKey, Plan, Principal

from greenhouse_sim.services.consumer import (
    Cursors,
    batch_cursor,
    batch_limit,
    run_descriptor,
)
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.forecasts import PERSISTENCE, Forecaster
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

    def owner_of(self, outcome: ActionOutcome) -> Principal | None: ...


@dataclass
class _Kept[RecordT]:
    """What a port keeps of one of its run's logs in an epoch: the records
    its principal reads, in the log's order, and how far into the run's log
    it has read."""

    epoch: int = NO_EPOCH
    read: int = 0
    records: list[RecordT] = field(default_factory=list)


@dataclass
class _Issued:
    """The forecasts its forecasters have issued in an epoch, in the order
    they were issued, and the moment they were last asked up to."""

    epoch: int = NO_EPOCH
    until: datetime | None = None
    forecasts: list[Forecast] = field(default_factory=list)


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

    def __init__(
        self,
        played: PlayedRun,
        principal: Principal,
        *,
        budget: InformationBudget = OBSERVATIONS_ONLY,
        forecasters: Sequence[Forecaster] = (PERSISTENCE,),
    ) -> None:
        self._played = played
        self.principal = principal
        self._budget = budget
        self._forecasters = self._served(budget, forecasters)
        self._lock = threading.Lock()
        self._cursors = Cursors()
        self._observations: _Kept[Observation] = _Kept()
        self._events: _Kept[Event] = _Kept()
        self._outcomes: _Kept[ActionOutcome] = _Kept()
        self._forecasts: _Kept[Forecast] = _Kept()
        self._issued = _Issued()
        # The types its context's sources observe, in an epoch.
        self._observed: tuple[int, frozenset[ObservationType]] = (NO_EPOCH, frozenset())

    def run(self) -> RunDescriptor:
        return run_descriptor(self._played.state())

    def context(self) -> CapabilityContext:
        return self._played.context(self.principal)

    def budget(self) -> InformationBudget:
        return self._budget

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
        answer = self._answer(
            "forecasts",
            self._forecasts,
            self._read_forecasts,
            lambda forecast, _: forecast,
            after=after,
            limit=limit,
        )
        return ForecastBatch(
            run_id=answer.state.run_id,
            epoch=answer.state.epoch,
            after=answer.after,
            next=answer.next,
            simulated_now=answer.state.simulated_now,
            has_more=answer.has_more,
            forecasts=answer.records,
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
        principal reads: from its start again in a new epoch, read again
        until a cut is of the epoch it keeps, however often the run starts
        over meanwhile."""
        while True:
            cut = read(kept.read)
            if cut.state.epoch != kept.epoch:
                kept.epoch, kept.read, kept.records = cut.state.epoch, 0, []
                continue
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

    def _read_forecasts(self, after: int) -> _Cut[Forecast]:
        """Its forecasters' forecasts, asked for what fell due since they
        were last asked, from the observations it has read as far as its
        clock; those of its budget's providers and quantities only."""
        state = self._caught_up(self._observations, self._read_observations, self._observed_now)
        if self._issued.epoch != state.epoch:
            self._issued = _Issued(epoch=state.epoch)
        issued = self._issued
        if issued.until is None or state.simulated_now > issued.until:
            due = [
                forecast
                for forecaster in self._forecasters
                for forecast in forecaster.issue_due(
                    self._observations.records,
                    start=state.started_at,
                    greenhouse_id=state.greenhouse_id,
                    after=issued.until,
                    until=state.simulated_now,
                )
                if readable_forecast(forecast, self._budget)
            ]
            issued.forecasts += sorted(due, key=lambda forecast: forecast.issued_at)
            issued.until = state.simulated_now
        return _Cut(issued.forecasts[after:], len(issued.forecasts), False, state)

    def _served(
        self, budget: InformationBudget, forecasters: Sequence[Forecaster]
    ) -> tuple[Forecaster, ...]:
        """The forecasters that serve `budget`'s providers, each as the
        budget names it; a budget the port cannot serve is refused."""
        if budget.full_state:
            raise InvalidRequest("a port does not give a policy the run's full state")
        serving: list[Forecaster] = []
        observed = self.context().observed_types() if budget.forecasts else frozenset()
        for wanted in budget.forecasts:
            found = next(
                (f for f in forecasters if f.provider.provider_id == wanted.provider_id), None
            )
            if found is None or found.provider.version != wanted.version:
                raise InvalidRequest(
                    f"no forecaster serves provider {wanted.provider_id!r} at version "
                    f"{wanted.version!r}"
                )
            offered = found.provider
            if (
                offered.basis != wanted.basis
                or offered.issued_every_s != wanted.issued_every_s
                or offered.horizon_s != wanted.horizon_s
                or offered.uncertainty != wanted.uncertainty
                or not wanted.quantities <= offered.quantities
            ):
                raise InvalidRequest(
                    f"provider {wanted.provider_id!r} is not served as the budget names it"
                )
            unobserved = wanted.quantities - observed
            if wanted.basis == InformationBasis.OBSERVED and unobserved:
                raise InvalidRequest(
                    f"provider {wanted.provider_id!r} is made from observations, and the run "
                    f"observes no {sorted(unobserved)}"
                )
            serving.append(found)
        return tuple(serving)

    def _observed_now(self, observation: Observation, epoch: int) -> Observation | None:
        if self._observed[0] != epoch:
            self._observed = (epoch, self.context().observed_types())
        return observation if observation.observation_type in self._observed[1] else None

    def _owned(self, outcome: ActionOutcome, epoch: int) -> ActionOutcome | None:
        return outcome if self._played.owner_of(outcome) == self.principal else None


def policy_port(
    playbacks: Playbacks,
    run_id: str,
    principal: Principal,
    *,
    budget: InformationBudget = OBSERVATIONS_ONLY,
) -> RunPolicyPort:
    """A port for `principal` on the run `run_id` played back, under
    `budget`; a run not played back is not found."""
    return RunPolicyPort(playbacks.of_run(run_id), principal, budget=budget)
