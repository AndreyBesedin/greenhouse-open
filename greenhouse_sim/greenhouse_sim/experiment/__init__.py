"""An experiment that steps a run (P15.4, decision 0061): a policy, in the
simulator's process, steering a scenario's run through its port, decision
by decision, at barriers to which the runner moves the run's clock.

An episode is a scenario, a policy and its principal, how far into the run
it goes, and the time a decision may take, on a condition: its run's seed,
its weather and its end (P23.1, decision 0075), each its scenario's own
when none. Its runner owns everything but the policy's memory:

- **the run:** a playback of its own of the scenario's run on the
  condition, served to no one, its clock moved by the runner alone
  (`Playback.step_to`);
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
  it gave and what became of it, what it skipped, and a digest; or its
  record (`record_episode`, P23.2), which names besides the run's
  condition, models and weather, the policy's entry, the software, and
  each decision with what each log delivered, counted and digested; and
  with its record, for the evaluator alone, the run it carried out
  (`carry_out_episode`, P25.2, decision 0082): its scenario's run on its
  condition with the plan the policy's revisions left, handed on once the
  policy has stopped, whose truth `greenhouse_sim.evaluation` reads.

The digest covers what the policy was given and what it gave: every
delivery, every receipt and every outcome. The same scenario, condition and
policy give the same digest when the policy is deterministic, a property
tested of a given policy, not promised of every one.

A sensor's draws are keyed by the run's seed, the sensor and its sample
(`sensors.air`), so two episodes on one condition share every sensor's
noise and drop-outs, whatever their policies do: common random numbers, as
a paired comparison wants. An episode's policy is made already, or made
fresh from its entry (`PolicyEntry`) as the episode starts: its factory,
its settings and its seed, which its record names. A policy held at
barriers in a process of its own comes later (decision 0061, stage C).
"""

import copy
import hashlib
import importlib
import math
import platform
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import version as installed_version
from pathlib import Path
from typing import Final, cast

from greenhouse_protocol import experiment as records
from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBudget
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
from greenhouse_protocol.experiment import Condition as Condition
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import Plan, PlannedAction, Principal
from pydantic import BaseModel, ConfigDict, JsonValue

from greenhouse_sim.domain.parts import Part
from greenhouse_sim.services.forecasts import PERSISTENCE, Forecaster
from greenhouse_sim.services.playback import Playback
from greenhouse_sim.services.policy_port import RunPolicyPort
from greenhouse_sim.services.runs import RunRequest, started_duration_s, started_weather
from greenhouse_sim.services.scenario_files import file_digest
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, run_manifest, scenario
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.system import UNKNOWN_COMMIT, source_commit
from greenhouse_sim.services.weather import SERIES_EVERY_S, series_sha256

# The plan an episode's policy steers by, unless it is named otherwise.
PLAN_ID: Final = "policy"
# The packages that ran an episode, as its record names them.
PRODUCER: Final = "greenhouse-sim"
PROTOCOL: Final = "greenhouse-protocol"
# What a policy is, as its factory gives it: the protocol's `Policy`.
POLICY_MEMBERS: Final = ("identity", "decide_every_s", "start", "decide", "stop")

# A policy's factory: given its settings and its seed, a policy made fresh.
type PolicyFactory = Callable[[dict[str, JsonValue], int | None], Policy]


# The condition of a scenario's own run: its seed, its weather and its days.
SCENARIOS_OWN: Final = Condition()


class PolicyEntry(records.PolicyEntry):
    """A policy's entry in the protocol (`greenhouse_protocol.experiment`),
    which makes it fresh for each episode."""

    def make(self) -> Policy:
        """A policy of its own, from the factory: given a copy of the
        settings, so that what it does with them leaves the entry as it is.
        A factory that cannot be found, or that gives no policy, is
        refused."""
        made = self._factory()(copy.deepcopy(self.settings), self.seed)
        missing = [name for name in POLICY_MEMBERS if not hasattr(made, name)]
        if missing:
            raise TypeError(
                f"{self.factory} gave {type(made).__name__}, not a policy: "
                f"it has no {', '.join(missing)}"
            )
        return made

    def _factory(self) -> PolicyFactory:
        module_name, _, path = self.factory.partition(":")
        try:
            found: object = importlib.import_module(module_name)
            for name in path.split("."):
                found = getattr(found, name)
        except (ImportError, AttributeError) as error:
            raise ValueError(f"there is no policy factory {self.factory}: {error}") from error
        if not callable(found):
            raise TypeError(f"{self.factory} is not a policy factory: it cannot be called")
        return cast(PolicyFactory, found)


@dataclass(frozen=True)
class Episode:
    """A policy and its principal on a scenario's run, on `condition`, from
    its start to `end_s` into it; `layout`, the scenario's own unless named;
    each decision given `compute_budget_s` of the runner's timer, or any
    time if None; its policy given `budget`, which the run's port must be
    able to serve."""

    scenario_id: str
    # Made already, or made fresh from its entry as the episode starts.
    policy: Policy | PolicyEntry
    principal: Principal
    end_s: float
    layout: str | None = None
    # The run's seed, weather and end.
    condition: Condition = SCENARIOS_OWN
    plan_id: Identifier = PLAN_ID
    compute_budget_s: float | None = None
    # What it is given besides the observations and the clock.
    budget: InformationBudget = OBSERVATIONS_ONLY


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
    simulator: Simulator,
    episode: Episode,
    *,
    timer: Callable[[], float] = time.perf_counter,
    forecasters: Sequence[Forecaster] = (PERSISTENCE,),
) -> EpisodeSummary:
    """Runs `episode` on a run of its own of the simulator's: see the
    module. `timer` measures each decision's time against its budget, and
    `forecasters` are the providers its budget may name. A condition is
    checked as a run started from it is: a weather the simulator does not
    have, or one named with a mark, is refused, as are more days than its
    scenario's."""
    return _play(simulator, episode, timer, forecasters).summary


def record_episode(
    simulator: Simulator,
    episode: Episode,
    *,
    place: records.EpisodePlace | None = None,
    timer: Callable[[], float] = time.perf_counter,
    forecasters: Sequence[Forecaster] = (PERSISTENCE,),
    kept: Callable[[Delivery], None] | None = None,
) -> records.EpisodeRecord:
    """Runs `episode` as `run_episode` does, and gives its record
    (`greenhouse_protocol.experiment`), at `place` in its experiment if it
    has one, each decision's delivery given to `kept` if asked. The files
    its policy's entry names are digested before it starts, so that the
    record names those it was made with."""
    return carry_out_episode(
        simulator, episode, place=place, timer=timer, forecasters=forecasters, kept=kept
    ).record


@dataclass(frozen=True)
class EpisodeCarriedOut:
    """An episode's record, and the run it carried out (decision 0082): its
    scenario's run on its condition, with the plan its policy's revisions
    left, as a run is asked for, the same from the run's start to the
    episode's end as the run its policy steered. For the evaluator alone,
    once the policy has stopped: it is what the evaluator's instruments
    read (`greenhouse_sim.evaluation.instruments`), and never the policy's."""

    record: records.EpisodeRecord
    run: RunRequest


def carry_out_episode(
    simulator: Simulator,
    episode: Episode,
    *,
    place: records.EpisodePlace | None = None,
    timer: Callable[[], float] = time.perf_counter,
    forecasters: Sequence[Forecaster] = (PERSISTENCE,),
    kept: Callable[[Delivery], None] | None = None,
) -> EpisodeCarriedOut:
    """Runs `episode` and gives its record, as `record_episode` does, and
    the run it carried out, read once its policy has stopped."""
    made = made_from(episode.policy) if isinstance(episode.policy, PolicyEntry) else None
    ran = _play(simulator, episode, timer, forecasters, kept)
    summary = ran.summary
    record = records.EpisodeRecord(
        place=place,
        run=_run_recorded(simulator, episode, ran.played, summary),
        policy=records.EpisodePolicy(
            identity=summary.policy,
            made=made,
            principal=episode.principal,
            decide_every_s=ran.decide_every_s,
            plan_id=episode.plan_id,
            budget=summary.budget,
            compute_budget_s=episode.compute_budget_s,
        ),
        software=_software(),
        trace=ran.trace,
        outcomes=summary.outcomes,
        digest=summary.digest,
    )
    # Its policy stopped as it was played.
    return EpisodeCarriedOut(record=record, run=ran.played.run_carried_out())


def made_from(entry: PolicyEntry) -> records.PolicyMade:
    """An entry, as a record names it: with its settings' digest and those
    of the files it names, as they are now. A file that cannot be read is
    refused."""
    return records.PolicyMade(
        entry=records.PolicyEntry.model_validate(entry.model_dump()),
        settings_sha256=records.settings_sha256(entry.settings),
        files=tuple(_policy_file(entry, name) for name in entry.files),
    )


@dataclass(frozen=True)
class _Played:
    """An episode played: its summary, its run, its policy's cadence and
    its trace."""

    summary: EpisodeSummary
    played: Playback
    decide_every_s: float
    trace: tuple[records.DecisionTraced, ...]


def _play(
    simulator: Simulator,
    episode: Episode,
    timer: Callable[[], float],
    forecasters: Sequence[Forecaster],
    kept: Callable[[Delivery], None] | None = None,
) -> _Played:
    condition = episode.condition
    played = Playback(
        simulator,
        episode.scenario_id,
        layout=episode.layout,
        seed=condition.seed,
        weather=started_weather(condition.weather),
        end_s=started_duration_s(
            scenario(simulator.catalogue, episode.scenario_id), condition.duration_days
        ),
    )
    if not 0.0 <= episode.end_s <= played.end_s:
        raise ValueError(
            f"an episode ends within its run, 0 to {played.end_s:.15g} s, "
            f"not at {episode.end_s:.15g} s"
        )
    policy = episode.policy.make() if isinstance(episode.policy, PolicyEntry) else episode.policy
    moments = _decision_moments(policy.decide_every_s, episode.end_s, played.end_s)
    port = RunPolicyPort(played, episode.principal, budget=episode.budget, forecasters=forecasters)
    budget = port.budget()
    policy.start(port.context(), budget)
    steering = Steering(port, episode.plan_id)
    read = _Reader(port)
    given: list[Given] = []
    skipped: list[Skipped] = []
    trace: list[records.DecisionTraced] = []
    digest = hashlib.sha256()
    try:
        for moment_s in moments:
            at = played.start + timedelta(seconds=moment_s)
            played.step_to(moment_s)
            delivered = read.since_last()
            if kept is not None:
                kept(delivered)
            digest.update(delivered.model_dump_json().encode())
            started = timer()
            decision = policy.decide(at, delivered)
            took_s = timer() - started
            late = episode.compute_budget_s is not None and took_s > episode.compute_budget_s
            receipt = None
            if late:
                skipped.append(Skipped(at=at, took_s=took_s))
            else:
                receipt = _act(steering, decision)
                if receipt is not None:
                    given.append(Given(at=at, receipt=receipt))
                    digest.update(receipt.model_dump_json().encode())
            trace.append(
                records.DecisionTraced(
                    at=at,
                    delivered=_delivered_logs(delivered),
                    decision=decision,
                    receipt=receipt,
                    took_s=took_s,
                    skipped=late,
                )
            )
        # The rest of the episode, to its end, without deciding again.
        played.step_to(episode.end_s)
    finally:
        policy.stop()
    outcomes = read.outcomes_to_date()
    for outcome in outcomes:
        digest.update(outcome.model_dump_json().encode())
    run = port.run()
    summary = EpisodeSummary(
        scenario_id=episode.scenario_id,
        run_id=run.run_id,
        epoch=run.epoch,
        policy=policy.identity,
        principal=episode.principal,
        budget=budget,
        decisions=len(trace),
        given=tuple(given),
        outcomes=outcomes,
        skipped=tuple(skipped),
        digest=digest.hexdigest(),
    )
    return _Played(summary, played, policy.decide_every_s, tuple(trace))


def _delivered_logs(delivered: Delivery) -> records.DeliveredLogs:
    return records.DeliveredLogs(
        observations=records.delivered(delivered.observations),
        events=records.delivered(delivered.events),
        outcomes=records.delivered(delivered.outcomes),
        forecasts=records.delivered(delivered.forecasts),
    )


def _policy_file(entry: PolicyEntry, setting: str) -> records.PolicyFile:
    """A file a policy's entry names, digested; one that cannot be read is
    refused before the episode starts."""
    path = Path(str(entry.settings[setting]))
    try:
        with path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
    except OSError as error:
        raise ValueError(f"the policy's file {setting} cannot be read: {error}") from error
    return records.PolicyFile(setting=setting, sha256=sha256)


def _run_recorded(
    simulator: Simulator, episode: Episode, played: Playback, summary: EpisodeSummary
) -> records.EpisodeRun:
    """The run an episode played, as its record names it."""
    catalogue = simulator.catalogue
    own = scenario(catalogue, episode.scenario_id)
    weather = played.weather or DEFAULT_WEATHER
    # Its models, and its crop's parameter set, as its manifest answer gives them.
    manifest = run_manifest(catalogue, episode.scenario_id, weather)
    crop_set = manifest.parameter_set
    grown_with = None if crop_set is None else records.ParameterSetRan(**crop_set.model_dump())
    seeded = RunRequest(episode.scenario_id, weather=weather, seed=played.seed)
    return records.EpisodeRun(
        scenario_id=episode.scenario_id,
        greenhouse_id=played.greenhouse_id,
        layout=played.layout,
        scenario_file_digest=file_digest(catalogue, simulator.runs, episode.scenario_id),
        run_id=summary.run_id,
        epoch=summary.epoch,
        condition=episode.condition,
        seed=own.random_seed if played.seed is None else played.seed,
        start=played.start,
        duration_s=played.end_s,
        episode_end_s=episode.end_s,
        models=tuple(
            records.ModelRan(
                part=part,
                model=ran.model,
                version=ran.version,
                parameter_set=grown_with if part == Part.CROP else None,
            )
            for part, ran in manifest.models.items()
        ),
        weather=records.WeatherSeries(
            every_s=SERIES_EVERY_S,
            sha256=series_sha256(
                catalogue, episode.scenario_id, seeded.weather_name(catalogue), played.end_s
            ),
        ),
    )


def _software() -> records.Software:
    commit = source_commit()
    return records.Software(
        producer=PRODUCER,
        producer_version=installed_version(PRODUCER),
        protocol_version=installed_version(PROTOCOL),
        python=platform.python_version(),
        commit=None if commit == UNKNOWN_COMMIT else commit,
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
