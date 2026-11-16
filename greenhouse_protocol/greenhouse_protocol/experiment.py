"""An episode's record (P23, decision 0061): everything that made an
episode of a policy on a run what it was, so that a reader can tell two
episodes apart, run one again and check it, and score it later.

- **Its place:** the experiment it belongs to, and the condition and the
  policy it pairs; none for an episode run on its own.
- **The run:** its scenario, greenhouse and layout, the scenario file's
  digest when the scenario is not packaged with its producer, its id and
  epoch, its condition (`Condition`: its seed, weather and days) and the
  seed it was at, how long it lasted and where the episode ended, each
  model it ran with its version and, for a model that grows with one, its
  parameter set, and the SHA-256 of the weather it ran under, sampled every
  so often.
- **The policy:** its identity; its entry, if it was made from one
  (`PolicyEntry`: its factory, settings, files and seed), with its
  settings' and files' digests; its principal, cadence, plan, information
  budget and compute budget.
- **The software:** its producer and version, the protocol's version,
  Python's, and the commit when it ran from a checkout.
- **The trace,** by decision: when, what each log delivered (counted and
  digested, `delivered`), the decision, its receipt, its time on the
  runner's timer, and whether it was skipped. Then the outcomes.
- **The digest** of every delivery, receipt and outcome, as the runner
  takes it. The decisions' times are not in it: they vary from one machine
  and run to the next.

The deliveries themselves are not kept here: a season of readings is
large, and the run gives them again.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.budget import InformationBudget, Name, Sha256
from greenhouse_protocol.contracts.gateway import Receipt
from greenhouse_protocol.contracts.policy import Decision, Keep, PolicyIdentity
from greenhouse_protocol.instant import Instant
from greenhouse_protocol.outcome import ActionOutcome
from greenhouse_protocol.plan import Principal

# The record's format, changed when a reader of the last could misread it.
EPISODE_RECORD_VERSION: Final = 1


def settings_sha256(settings: Mapping[str, JsonValue]) -> str:
    """The SHA-256 of a policy's settings, as JSON with its keys sorted and
    nothing between its tokens, so that the same settings, however written,
    have one digest."""
    text = json.dumps(settings, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


class Condition(BaseModel):
    """What a run is made of besides its scenario: its seed, its weather by
    name, and how many whole days it lasts, each its scenario's own when
    none."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: NonNegativeInt | None = None
    weather: Name | None = None
    duration_days: PositiveInt | None = None


class PolicyEntry(BaseModel):
    """A policy as an experiment makes it: its factory, by its import path
    (`module:callable`), given its settings, a JSON object, and its seed,
    none for a policy that does not draw. `files` names the settings that
    are paths to files the policy reads, such as a network's weights."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    factory: str = Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_][\w.]*$")
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    files: tuple[Name, ...] = ()
    seed: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _files_are_settings_naming_paths(self) -> Self:
        for name in self.files:
            if not isinstance(self.settings.get(name), str):
                raise ValueError(f"a policy's file is a setting naming its path, not {name!r}")
        return self


class EpisodePlace(BaseModel):
    """Where an episode stands in its experiment: the experiment, and the
    condition and policy it pairs, by their places in it from 0."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: Identifier
    condition: NonNegativeInt
    policy: NonNegativeInt


class ParameterSetRan(BaseModel):
    """The parameter set a model ran with: its name, version and digest, and
    the version of the model it was made for, which may be another than the
    one run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Name
    version: PositiveInt
    digest: Name
    made_for: PositiveInt


class ModelRan(BaseModel):
    """A part of the run, the model it ran and that model's version, and the
    parameter set it ran with: none for a model that names none, as in every
    record written before sets were named."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    part: Name
    model: Name
    version: PositiveInt
    parameter_set: ParameterSetRan | None = None


class WeatherSeries(BaseModel):
    """The weather a run was under, from its start to its end, every
    `every_s`: the SHA-256 of each moment's state as its producer writes it,
    one line each."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    every_s: PositiveFloat
    sha256: Sha256


class EpisodeRun(BaseModel):
    """The run an episode steered: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    scenario_id: Name
    greenhouse_id: Name
    layout: Name
    # None for a scenario packaged with its producer.
    scenario_file_digest: Name | None
    run_id: Name
    epoch: NonNegativeInt
    condition: Condition
    seed: NonNegativeInt
    start: Instant
    duration_s: PositiveFloat
    episode_end_s: NonNegativeFloat
    models: tuple[ModelRan, ...]
    weather: WeatherSeries

    @model_validator(mode="after")
    def _the_episode_ends_within_its_run(self) -> Self:
        if self.episode_end_s > self.duration_s:
            raise ValueError("an episode ends within its run")
        return self


class PolicyFile(BaseModel):
    """A file a policy read, by the setting naming it, and its SHA-256."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    setting: Name
    sha256: Sha256


class PolicyMade(BaseModel):
    """A policy's entry, and the digests of its settings and its files."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry: PolicyEntry
    settings_sha256: Sha256
    files: tuple[PolicyFile, ...] = ()

    @model_validator(mode="after")
    def _the_digests_are_the_entrys(self) -> Self:
        if self.settings_sha256 != settings_sha256(self.entry.settings):
            raise ValueError("a policy's settings digest is not that of its settings")
        if tuple(file.setting for file in self.files) != self.entry.files:
            raise ValueError("a policy's files are those its entry names, in its order")
        return self


class EpisodePolicy(BaseModel):
    """The policy an episode ran: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    identity: PolicyIdentity
    # None for a policy given to the runner made already.
    made: PolicyMade | None
    principal: Principal
    decide_every_s: PositiveFloat
    plan_id: Identifier
    budget: InformationBudget
    compute_budget_s: PositiveFloat | None


class Software(BaseModel):
    """What ran the episode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    producer: Name
    producer_version: Name
    protocol_version: Name
    python: Name
    # None when it did not run from a checkout.
    commit: Name | None


class Delivered(BaseModel):
    """What one log delivered at a decision: how many records, and the
    SHA-256 of their JSON, one line each, in delivery order (`delivered`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: NonNegativeInt
    sha256: Sha256


def delivered(records: Sequence[BaseModel]) -> Delivered:
    """What a log delivered, counted and digested."""
    digest = hashlib.sha256()
    for record in records:
        digest.update(record.model_dump_json().encode() + b"\n")
    return Delivered(count=len(records), sha256=digest.hexdigest())


class DeliveredLogs(BaseModel):
    """What each of a policy's logs delivered at a decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observations: Delivered
    events: Delivered
    outcomes: Delivered
    forecasts: Delivered


class DecisionTraced(BaseModel):
    """One decision of an episode: see the module. A decision kept, or
    skipped, gave nothing and has no receipt; so has a cancellation of a
    plan never given."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    at: Instant
    delivered: DeliveredLogs
    decision: Decision
    receipt: Receipt | None
    took_s: NonNegativeFloat
    skipped: bool

    @model_validator(mode="after")
    def _only_a_change_given_has_a_receipt(self) -> Self:
        if self.receipt is not None and (self.skipped or isinstance(self.decision, Keep)):
            raise ValueError("a decision kept or skipped gave nothing, and has no receipt")
        return self


class EpisodeRecord(BaseModel):
    """An episode, as its record names it: see the module."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_version: Literal[1] = EPISODE_RECORD_VERSION
    place: EpisodePlace | None = None
    run: EpisodeRun
    policy: EpisodePolicy
    software: Software
    trace: tuple[DecisionTraced, ...]
    outcomes: tuple[ActionOutcome, ...]
    digest: Sha256
