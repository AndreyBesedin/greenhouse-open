"""An experiment of paired episodes (P23.3): policies compared on the same
conditions, each episode leaving its record.

An experiment is a JSON file (`Experiment`, `experiment.schema.json`): its
id, its scenario and layout, its principal and its episodes' end, its
conditions, and its policies' entries, each with the seeds of its trials.
The runner runs every policy, at each of its seeds, on every condition, in
the file's order: for each condition, each policy, each seed. Each episode
is numbered from 0 in that order and runs on a run of its own. It writes
into a directory of its own:

- `experiment.json`, the file as given, and `experiment.sha256`, its digest
  as `sha256sum` writes it;
- `episodes/N.json`, each episode's record, its place filled;
- `deliveries/N.jsonl`, for each episode the file asks to keep them, what
  each decision was given, a `Delivery` a line, which the record's trace
  counts and digests.

A record is checked by running its episode again from what it names, its
policy made again from its entry, and comparing the digests
(`check_record`): the test of a deterministic replay decision 0061 asks of
a given policy, not a promise of every one. Who may do what on the runs is
the simulator's (decision 0052), given to `run` and `check` alike.
"""

import hashlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Final, Self, TextIO

from greenhouse_protocol import experiment as records
from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.budget import OBSERVATIONS_ONLY, InformationBudget
from greenhouse_protocol.contracts.policy import Delivery
from greenhouse_protocol.plan import Principal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    PositiveFloat,
    model_validator,
)

from greenhouse_sim.experiment import PLAN_ID, Episode, PolicyEntry, made_from, record_episode
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.services.runs import started_duration_s, started_weather
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.simulator import Simulator

# What the runner writes in its directory.
EXPERIMENT_FILE: Final = "experiment.json"
DIGEST_FILE: Final = "experiment.sha256"
EPISODES: Final = "episodes"
DELIVERIES: Final = "deliveries"


class ExperimentPolicy(BaseModel):
    """A policy's entry in an experiment: as a `PolicyEntry`, with the seeds
    of its trials, each an episode on every condition; none, one trial at
    no seed, for a policy that does not draw."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    factory: str
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    files: tuple[str, ...] = ()
    seeds: Annotated[tuple[NonNegativeInt, ...], Field(max_length=1000)] = ()

    def entries(self) -> list[PolicyEntry]:
        """Its entry at each of its seeds, in order."""
        fields = self.model_dump(exclude={"seeds"})
        return [PolicyEntry(**fields, seed=seed) for seed in self.seeds or (None,)]

    @model_validator(mode="after")
    def _its_entries_are_entries(self) -> Self:
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("a policy's trials are at seeds each its own")
        self.entries()
        return self


class Experiment(BaseModel):
    """An experiment, as its file holds it: see the module. `keep_deliveries`
    names, by number, the episodes whose deliveries are kept."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    experiment_id: Identifier
    scenario_id: Annotated[str, Field(min_length=1)]
    layout: str | None = None
    principal: Principal
    end_s: PositiveFloat
    conditions: Annotated[tuple[records.Condition, ...], Field(min_length=1)]
    policies: Annotated[tuple[ExperimentPolicy, ...], Field(min_length=1)]
    plan_id: Identifier = PLAN_ID
    compute_budget_s: PositiveFloat | None = None
    budget: InformationBudget = OBSERVATIONS_ONLY
    keep_deliveries: tuple[NonNegativeInt, ...] = ()

    def episodes(self) -> Iterator[tuple[records.EpisodePlace, Episode]]:
        """Each episode, with its place, in the file's order."""
        for at, condition in enumerate(self.conditions):
            for which, policy in enumerate(self.policies):
                for entry in policy.entries():
                    place = records.EpisodePlace(
                        experiment_id=self.experiment_id, condition=at, policy=which
                    )
                    yield place, self._episode(entry, condition)

    def _episode(self, entry: PolicyEntry, condition: records.Condition) -> Episode:
        return Episode(
            scenario_id=self.scenario_id,
            policy=entry,
            principal=self.principal,
            end_s=self.end_s,
            layout=self.layout,
            condition=condition,
            plan_id=self.plan_id,
            compute_budget_s=self.compute_budget_s,
            budget=self.budget,
        )

    @model_validator(mode="after")
    def _kept_are_its_episodes(self) -> Self:
        count = len(self.conditions) * sum(len(p.entries()) for p in self.policies)
        beyond = [n for n in self.keep_deliveries if n >= count]
        if beyond:
            raise ValueError(f"an experiment of {count} episodes has no episode {beyond[0]}")
        return self


def experiment_json_schema() -> dict[str, JsonValue]:
    """The JSON Schema an experiment's file follows."""
    return {"$schema": JSON_SCHEMA_DIALECT, **Experiment.model_json_schema()}


def run_experiment(
    simulator: Simulator, given: bytes, out: Path, *, said: Callable[[str], None] = print
) -> list[records.EpisodeRecord]:
    """Runs the experiment `given`, a file's bytes, into `out`, a directory
    that does not exist or is empty: see the module. Every condition is
    checked against the scenario before any episode runs. `said` is told of
    each episode as it ends."""
    experiment = Experiment.model_validate_json(given)
    _check_conditions(simulator, experiment)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} holds files already: an experiment is written where none are")
    (out / EPISODES).mkdir(parents=True)
    (out / EXPERIMENT_FILE).write_bytes(given)
    digest = hashlib.sha256(given).hexdigest()
    (out / DIGEST_FILE).write_text(f"{digest}  {EXPERIMENT_FILE}\n")
    written = []
    for number, (place, episode) in enumerate(experiment.episodes()):
        if number in experiment.keep_deliveries:
            (out / DELIVERIES).mkdir(exist_ok=True)
            with (out / DELIVERIES / f"{number}.jsonl").open("w") as kept:
                record = record_episode(
                    simulator, episode, place=place, kept=lambda d: _keep(kept, d)
                )
        else:
            record = record_episode(simulator, episode, place=place)
        (out / EPISODES / f"{number}.json").write_text(record.model_dump_json(indent=2))
        assert record.policy.made is not None
        said(
            f"episode {number}: condition {place.condition}, policy {place.policy}, "
            f"seed {record.policy.made.entry.seed}: digest {record.digest[:16]}"
        )
        written.append(record)
    return written


def _keep(file: TextIO, delivered: Delivery) -> None:
    file.write(delivered.model_dump_json() + "\n")


def _check_conditions(simulator: Simulator, experiment: Experiment) -> None:
    """Each condition is one a run can be started on (decision 0075), and
    long enough for the experiment's end."""
    config = scenario(simulator.catalogue, experiment.scenario_id)
    for at, condition in enumerate(experiment.conditions):
        started_weather(condition.weather)
        if started_duration_s(config, condition.duration_days) < experiment.end_s:
            raise ValueError(f"condition {at} ends before the experiment's end")


class Checked(BaseModel):
    """A record checked: the digest it names, the one its episode gave
    again, and whether they agree."""

    model_config = ConfigDict(frozen=True)

    recorded: str
    again: str

    @property
    def same(self) -> bool:
        return self.recorded == self.again


def check_record(simulator: Simulator, record: records.EpisodeRecord) -> Checked:
    """Runs a record's episode again from what it names and gives both
    digests. Refused if its policy was not made from an entry, or a file
    its entry names is not the one it ran with."""
    made = record.policy.made
    if made is None:
        raise ValueError("its policy was given made already: there is no entry to make it again")
    entry = PolicyEntry(**made.entry.model_dump())
    if made_from(entry).files != made.files:
        raise ValueError("a file its policy names is not the one it ran with")
    run = record.run
    episode = Episode(
        scenario_id=run.scenario_id,
        policy=entry,
        principal=record.policy.principal,
        end_s=run.episode_end_s,
        layout=run.layout,
        condition=run.condition,
        plan_id=record.policy.plan_id,
        compute_budget_s=record.policy.compute_budget_s,
        budget=record.policy.budget,
    )
    again = record_episode(simulator, episode, place=record.place)
    return Checked(recorded=record.digest, again=again.digest)
