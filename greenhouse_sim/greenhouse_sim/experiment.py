"""An experiment that steps a run (P15.4, decision 0061): a policy, in the
simulator's process, steering a scenario's run through its port, decision
by decision, at barriers to which the runner moves the run's clock.

An episode is a scenario, a policy and its principal, how far into the run
it goes, and the time a decision may take. Its runner owns everything but
the policy's memory:

- **the run:** a playback of the scenario's run of its own, served to no
  one, its clock moved by the runner alone (`Playback.step_to`);
- **the port,** opened for the principal (`services.policy_port`), its
  logs read on at each decision;
- **the plan:** one, named by the runner, each decision that changes it a
  revision given through the port. A revision refused as stale, because
  another principal that may manage plans revised it meanwhile, is given
  once more, after the revision in force;
- **the barriers,** at each decision moment from the run's start, every
  `decide_every_s` of the policy's, to the episode's end:
  1. advance: the run worked out to the moment, its clock moved there;
  2. observe: what reached the port since the last decision (`Delivery`);
  3. act: the policy's decision, turned into its plan's next revision or
     its cancellation, given, and its receipt recorded;
- **the compute budget:** a decision that takes longer than the episode
  allows is not acted on, and the skip is recorded;
- **its end:** the policy stopped, and an episode's summary returned: its
  scenario, run and epoch, the policy and its principal, its budget, what
  it gave and what became of it, what it skipped, and a digest.

The digest covers what the policy was given and what it gave: every
delivery, every receipt and every outcome. The same scenario and policy
give the same digest when the policy is deterministic, a property tested
of a given policy, not promised of every one. The run's own randomness is
its scenario's seed. An episode's record as an experiment names it, and
a policy held at barriers in a process of its own, come later (decision
0061, stage C).
"""

import hashlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
)
from greenhouse_protocol.contracts.gateway import Receipt
from greenhouse_protocol.contracts.policy import (
    CancelPlan,
    Delivery,
    Keep,
    Policy,
    PolicyIdentity,
    PolicyPort,
    Revise,
)
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import Plan, PlannedAction, Principal
from pydantic import BaseModel, ConfigDict

from greenhouse_sim.services.playback import Playback
from greenhouse_sim.services.policy_port import RunPolicyPort
from greenhouse_sim.services.simulator import Simulator

# The plan an episode's policy steers by, unless it is named otherwise.
PLAN_ID: Final = "policy"


@dataclass(frozen=True)
class Episode:
    """A policy and its principal on a scenario's run, from its start to
    `end_s` into it; `layout`, the scenario's own unless named; each
    decision given `compute_budget_s` of the runner's timer, or any time if
    None."""

    scenario_id: str
    policy: Policy
    principal: Principal
    end_s: float
    layout: str | None = None
    plan_id: Identifier = PLAN_ID
    compute_budget_s: float | None = None


class Given(BaseModel):
    """What the runner gave the run at a decision, and its receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: Instant
    receipt: Receipt


class Skipped(BaseModel):
    """A decision not acted on: it took longer than its budget."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    at: Instant
    took_s: float


class EpisodeSummary(BaseModel):
    """An episode, as its runner returns it: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    scenario_id: str
    run_id: str
    epoch: int
    policy: PolicyIdentity
    principal: Principal
    budget: InformationBudget
    decisions: int
    given: tuple[Given, ...]
    outcomes: tuple[ActionOutcome, ...]
    skipped: tuple[Skipped, ...]
    digest: str


class Steering:
    """A policy's plan, as its runner gives it through its port: named, its
    revisions counted on from the one in force."""

    def __init__(self, port: PolicyPort, plan_id: str) -> None:
        self._port = port
        self.plan_id = plan_id
        self.revision = 0

    def revise(self, actions: tuple[PlannedAction, ...]) -> Receipt:
        """Gives the plan's next revision. Refused as stale, because the
        revision in force is as new or newer, it is given once more after
        that one."""
        receipt = self._give(actions)
        if not receipt.accepted and self._caught_up():
            receipt = self._give(actions)
        return receipt

    def cancel(self) -> Receipt | None:
        """Cancels the plan in force, what of it has not started, as its
        revision in force stands, whoever gave that; none if it has no
        revision yet."""
        if self.revision == 0:
            return None
        self._caught_up()
        return self._port.cancel_plan(
            self.plan_id, revision=self.revision, epoch=self._port.run().epoch
        )

    def _give(self, actions: tuple[PlannedAction, ...]) -> Receipt:
        run = self._port.run()
        receipt = self._port.submit(
            Plan(
                plan_id=self.plan_id,
                run_id=run.run_id,
                epoch=run.epoch,
                revision=self.revision + 1,
                actions=actions,
            )
        )
        if receipt.accepted:
            self.revision += 1
        return receipt

    def _caught_up(self) -> bool:
        """Whether the revision in force is as new as the one it gave or
        newer: then it counts on from that one."""
        in_force = self._port.plan(self.plan_id)
        if in_force is None or in_force.plan.revision <= self.revision:
            return False
        self.revision = in_force.plan.revision
        return True


def run_episode(
    simulator: Simulator, episode: Episode, *, timer: Callable[[], float] = time.perf_counter
) -> EpisodeSummary:
    """Runs `episode` on a run of its own of the simulator's: see the
    module. `timer` measures each decision's time against its budget."""
    played = Playback(simulator, episode.scenario_id, layout=episode.layout)
    policy = episode.policy
    if not 0.0 <= episode.end_s <= played.end_s:
        raise ValueError(
            f"an episode ends within its run, 0 to {played.end_s:.15g} s, "
            f"not at {episode.end_s:.15g} s"
        )
    moments = _decision_moments(policy.decide_every_s, episode.end_s, played.end_s)
    port = RunPolicyPort(played, episode.principal)
    budget = port.budget()
    policy.start(port.context(), budget)
    steering = Steering(port, episode.plan_id)
    read = _Reader(port)
    given: list[Given] = []
    skipped: list[Skipped] = []
    digest = hashlib.sha256()
    decisions = 0
    try:
        for moment_s in moments:
            at = played.start + timedelta(seconds=moment_s)
            played.step_to(moment_s)
            delivered = read.since_last()
            digest.update(delivered.model_dump_json().encode())
            started = timer()
            decision = policy.decide(at, delivered)
            took_s = timer() - started
            decisions += 1
            if episode.compute_budget_s is not None and took_s > episode.compute_budget_s:
                skipped.append(Skipped(at=at, took_s=took_s))
            else:
                receipt = _act(steering, decision)
                if receipt is not None:
                    given.append(Given(at=at, receipt=receipt))
                    digest.update(receipt.model_dump_json().encode())
        # The rest of the episode, to its end, without deciding again.
        played.step_to(episode.end_s)
    finally:
        policy.stop()
    outcomes = read.outcomes_to_date()
    for outcome in outcomes:
        digest.update(outcome.model_dump_json().encode())
    run = port.run()
    return EpisodeSummary(
        scenario_id=episode.scenario_id,
        run_id=run.run_id,
        epoch=run.epoch,
        policy=policy.identity,
        principal=episode.principal,
        budget=budget,
        decisions=decisions,
        given=tuple(given),
        outcomes=outcomes,
        skipped=tuple(skipped),
        digest=digest.hexdigest(),
    )


def _decision_moments(every_s: float, end_s: float, run_end_s: float) -> list[float]:
    """The moments a policy decides at, in seconds into the run: every
    `every_s` from its start, through the episode's end, but not at the
    run's own end, after which its gateway takes nothing more. A cadence
    that would not move the clock on, at a datetime's resolution, is
    refused."""
    if not math.isfinite(every_s) or timedelta(seconds=every_s) <= timedelta(0):
        raise ValueError(f"a policy decides every so many seconds, more than none: not {every_s!r}")
    return [
        moment
        for moment in (n * every_s for n in range(math.floor(end_s / every_s) + 1))
        if moment <= end_s and moment < run_end_s
    ]


def _act(steering: Steering, decision: Keep | Revise | CancelPlan) -> Receipt | None:
    match decision:
        case Keep():
            return None
        case Revise(actions=actions):
            return steering.revise(actions)
        case CancelPlan():
            return steering.cancel()


class _Reader:
    """A port's logs, read on from where the last decision left them."""

    def __init__(self, port: PolicyPort) -> None:
        self._port = port
        self._observed = self._happened = self._ended = self._issued = 0
        self._outcomes: list[ActionOutcome] = []

    def since_last(self) -> Delivery:
        """What reached the port since the last call, in delivery order."""
        observed = _drained(self._port.observations, self._observed)
        happened = _drained(self._port.events, self._happened)
        issued = _drained(self._port.forecasts, self._issued)
        self._observed, self._happened, self._issued = (
            observed[-1].next,
            happened[-1].next,
            issued[-1].next,
        )
        return Delivery(
            observations=tuple(o for batch in observed for o in batch.observations),
            events=tuple(e for batch in happened for e in batch.events),
            outcomes=tuple(self._outcomes_since()),
            forecasts=tuple(f for batch in issued for f in batch.forecasts),
        )

    def outcomes_to_date(self) -> tuple[ActionOutcome, ...]:
        """Every outcome the port gave, up to its clock."""
        self._outcomes_since()
        return tuple(self._outcomes)

    def _outcomes_since(self) -> list[ActionOutcome]:
        ended = _drained(self._port.outcomes, self._ended)
        self._ended = ended[-1].next
        new = [outcome for batch in ended for outcome in batch.outcomes]
        self._outcomes += new
        return new


def _drained[BatchT: (ObservationBatch, EventBatch, OutcomeBatch, ForecastBatch)](
    read: Callable[[int], BatchT], after: int
) -> list[BatchT]:
    """Every batch of a log from `after` on, read again at once while the
    port says it cut one short."""
    batches = [read(after)]
    while batches[-1].has_more:
        batches.append(read(batches[-1].next))
    return batches
