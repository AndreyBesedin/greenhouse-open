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
  counts and digests;
- `scores/N.json`, each episode's scores (P25.3, decisions 0081 and 0082),
  worked out by the evaluator once its policy has stopped, from its record
  and the run it carried out (`evaluation.scoring`): beside its record,
  never in its digest.

A record is checked by running its episode again from what it names, its
policy made again from its entry, and comparing the digests
(`check_record`): the test of a deterministic replay decision 0061 asks of
a given policy, not a promise of every one. A record is scored later the
same way (`score_record`): its episode run again, and scored on the run it
carries out again only if its digest is the record's, so that a new
version of a measure scores records already written; `score_experiment`
scores a directory's records so. Who may do what on the runs is the
simulator's (decision 0052), given to `run`, `check` and `score` alike.
"""

import hashlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Final, Self, TextIO

from greenhouse_protocol import experiment as records
from greenhouse_protocol.actions import Identifier
from greenhouse_protocol.benchmark import EpisodeScores
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
    ValidationError,
    model_validator,
)

from greenhouse_sim.evaluation.scoring import score_episode
from greenhouse_sim.experiment import (
    PLAN_ID,
    Episode,
    EpisodeCarriedOut,
    PolicyEntry,
    carry_out_episode,
    made_from,
)
from greenhouse_sim.json_schemas import JSON_SCHEMA_DIALECT
from greenhouse_sim.services.errors import ServiceError
from greenhouse_sim.services.runs import started_duration_s, started_weather
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.simulator import Simulator

# What the runner writes in its directory.
EXPERIMENT_FILE: Final = "experiment.json"
DIGEST_FILE: Final = "experiment.sha256"
EPISODES: Final = "episodes"
DELIVERIES: Final = "deliveries"
SCORES: Final = "scores"


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
    each episode as it ends, its scores written."""
    experiment = Experiment.model_validate_json(given)
    _check_conditions(simulator, experiment)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} holds files already: an experiment is written where none are")
    (out / EPISODES).mkdir(parents=True)
    (out / SCORES).mkdir()
    (out / EXPERIMENT_FILE).write_bytes(given)
    digest = hashlib.sha256(given).hexdigest()
    (out / DIGEST_FILE).write_text(f"{digest}  {EXPERIMENT_FILE}\n")
    written = []
    for number, (place, episode) in enumerate(experiment.episodes()):
        if number in experiment.keep_deliveries:
            (out / DELIVERIES).mkdir(exist_ok=True)
            with (out / DELIVERIES / f"{number}.jsonl").open("w") as kept:
                carried = carry_out_episode(
                    simulator, episode, place=place, kept=lambda d: _keep(kept, d)
                )
        else:
            carried = carry_out_episode(simulator, episode, place=place)
        record = carried.record
        (out / EPISODES / f"{number}.json").write_text(record.model_dump_json(indent=2))
        # Its policy stopped: the evaluator reads the run it carried out.
        _write_scores(out, number, score_episode(simulator, record, carried.run))
        assert record.policy.made is not None
        said(
            f"episode {number}: condition {place.condition}, policy {place.policy}, "
            f"seed {record.policy.made.entry.seed}: digest {record.digest[:16]}"
        )
        written.append(record)
    return written


def _keep(file: TextIO, delivered: Delivery) -> None:
    file.write(delivered.model_dump_json() + "\n")


def _write_scores(out: Path, number: int, scores: EpisodeScores) -> None:
    (out / SCORES / f"{number}.json").write_text(scores.model_dump_json(indent=2))


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
    return Checked(recorded=record.digest, again=_again(simulator, record).record.digest)


def score_record(simulator: Simulator, record: records.EpisodeRecord) -> EpisodeScores:
    """A record's scores, as the runner writes them beside it: its episode
    run again, as `check_record` runs it, and scored from the record as it
    was written and the run it carries out again, if its digest is the
    record's. Refused, saying why, when it is another, and as
    `check_record` refuses a record."""
    again = _again(simulator, record)
    if again.record.digest != record.digest:
        raise ValueError(
            f"it replays to another digest: the record's {record.digest},"
            f" again {again.record.digest}"
        )
    return score_episode(simulator, record, again.run)


def score_experiment(
    simulator: Simulator, out: Path, *, said: Callable[[str], None] = print
) -> tuple[int, ...]:
    """Scores again each record of an experiment's directory `out`, in the
    order of their numbers (`score_record`), and writes the scores of each
    that replays to its digest into `scores/N.json`, in place of those
    there; `said` is told of each. Gives the numbers of the records not
    scored: one that cannot be read as a record, that replays to another
    digest, or that `check_record` refuses, each said with why. The scores
    already beside a record not scored are left as they are. Refused for a
    directory that holds no record."""
    numbered = sorted(
        (int(path.stem), path) for path in (out / EPISODES).glob("*.json") if path.stem.isdecimal()
    )
    if not numbered:
        raise ValueError(f"{out} holds no episode's record to score")
    (out / SCORES).mkdir(exist_ok=True)
    not_scored = []
    for number, path in numbered:
        try:
            record = records.EpisodeRecord.model_validate_json(path.read_bytes())
            scores = score_record(simulator, record)
        except (OSError, ValueError, ServiceError) as error:
            said(f"episode {number}: not scored: {refusal(error)}")
            not_scored.append(number)
            continue
        _write_scores(out, number, scores)
        said(f"episode {number}: scored, the same digest {record.digest[:16]}")
    return tuple(not_scored)


def refusal(error: Exception) -> str:
    """Why a command, or a record, was refused: each field a record's
    validation refused, by its place in the record, or the error's
    message."""
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
    if isinstance(error, ServiceError):
        return error.message
    return str(error)


def _again(simulator: Simulator, record: records.EpisodeRecord) -> EpisodeCarriedOut:
    """A record's episode run again from what it names, with the run it
    carries out. Refused as `check_record` refuses a record."""
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
    return carry_out_episode(simulator, episode, place=record.place)
