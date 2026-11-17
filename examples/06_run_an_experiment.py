"""Run an experiment, and read its records back.

    python examples/06_run_an_experiment.py [FOLDER]

An experiment compares policies on the same conditions (P23): every policy
runs on every condition, and the episodes on one condition share their
run's weather and its chance. Each episode leaves a record of what made it
what it was.

Here the policy is example 03's rule at two bands, its heater on below
15 °C and off above 17 °C, or on below 17 °C and off above 19 °C. Its
conditions are the climate box's own weather and the cold spring day, each
at seeds 1 and 2: four conditions, so eight episodes of half an hour each.
The rule is made from its factory, `naive_heating:NaiveHeating`, a module
beside this file, with its band as its settings.

The example writes the experiment's file and the grant its policy acts
under, runs the experiment, and reads its records back: the two episodes
on each condition share their run id and their weather's digest, and the
two bands did different things on them. It keeps the first episode's
deliveries and compares them with what its record counts and digests.

Given a FOLDER, new or empty, it leaves everything there, for the
experiment's commands to be tried on (`docs/guides/run-an-experiment.md`).
Without one, it works in a temporary folder.
"""

import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import Final

from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.contracts.policy import Delivery, Revise
from greenhouse_protocol.experiment import Condition, EpisodeRecord, delivered
from greenhouse_protocol.outcome import ActionOutcome, OutcomeStatus
from greenhouse_protocol.plan import Principal, PrincipalKind
from greenhouse_sim.experiment.paired import (
    DELIVERIES,
    EPISODES,
    Experiment,
    ExperimentPolicy,
    run_experiment,
)
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "climate_box"
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="naive_heating")
# The policy may set levels and do nothing else.
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)
# The two bands, each a policy's settings: on below, off above, in °C.
BANDS: Final = ((15.0, 17.0), (17.0, 19.0))
# The scenario's own weather, and a preset; each at two seeds.
WEATHERS: Final = (None, "cold_spring_day")
SEEDS: Final = (1, 2)
END_S: Final = 1800.0
# The episode whose deliveries are kept: the first band's on the first
# condition.
KEPT: Final = 0

EXPERIMENT: Final = Experiment(
    experiment_id="heating_bands",
    scenario_id=SCENARIO,
    principal=POLICY,
    end_s=END_S,
    conditions=tuple(Condition(weather=w, seed=s) for w in WEATHERS for s in SEEDS),
    policies=tuple(
        ExperimentPolicy(
            factory="naive_heating:NaiveHeating",
            settings={"on_below_c": on, "off_above_c": off},
        )
        for on, off in BANDS
    ),
    keep_deliveries=(KEPT,),
)


def band(record: EpisodeRecord) -> str:
    """The band a record's policy ran at, from its settings."""
    assert record.policy.made is not None
    settings = record.policy.made.entry.settings
    return f"{settings['on_below_c']:g}-{settings['off_above_c']:g} °C"


def carried_out(record: EpisodeRecord) -> list[ActionOutcome]:
    """The levels a record's episode set, as its outcomes say they were
    carried out, in the order they started."""
    done = [
        o
        for o in record.outcomes
        if o.status == OutcomeStatus.EXECUTED and isinstance(o.action, SetLevel)
    ]
    return sorted(done, key=lambda o: o.started_at or o.resolved_at)


def heated_s(record: EpisodeRecord) -> float:
    """How long the heater ran in a record's episode: each level carried
    out, from when it started to the next or to the episode's end."""
    end = record.run.start + timedelta(seconds=record.run.episode_end_s)
    level, since, heated = 0.0, record.run.start, 0.0
    for outcome in carried_out(record):
        # The rule sets a level, and never hands the heater back to a loop.
        assert isinstance(outcome.action, SetLevel) and isinstance(outcome.action.level, float)
        assert outcome.started_at is not None
        heated += level * (outcome.started_at - since).total_seconds()
        level, since = outcome.action.level, outcome.started_at
    return heated + level * (end - since).total_seconds()


def compare(records: list[EpisodeRecord]) -> None:
    """Each condition's episodes, side by side: their run and its weather,
    which they share, and what each band did."""
    for at, condition in enumerate(EXPERIMENT.conditions):
        paired = [r for r in records if r.place is not None and r.place.condition == at]
        runs = {(r.run.run_id, r.run.weather.sha256) for r in paired}
        assert len(runs) == 1, f"condition {at}'s episodes ran on different runs"
        run_id, weather = runs.pop()
        print(
            f"condition {at}: {condition.weather or 'its own weather'}, seed {condition.seed}; "
            f"run {run_id}, weather {weather[:12]}"
        )
        for record in paired:
            revisions = sum(isinstance(t.decision, Revise) for t in record.trace)
            print(
                f"  {band(record)}: revisions {revisions}, carried out {len(carried_out(record))}, "
                f"heater on {heated_s(record) / 60:.0f} of {END_S / 60:.0f} min"
            )


def read_kept(results: Path, record: EpisodeRecord) -> None:
    """An episode's kept deliveries, as its record counts and digests them."""
    lines = (results / DELIVERIES / f"{KEPT}.jsonl").read_text().splitlines()
    kept = [Delivery.model_validate_json(line) for line in lines]
    assert len(kept) == len(record.trace)
    for traced, delivery in zip(record.trace, kept, strict=True):
        assert traced.delivered.observations == delivered(delivery.observations)
        assert traced.delivered.outcomes == delivered(delivery.outcomes)
    readings = sum(len(d.observations) for d in kept)
    print(
        f"episode {KEPT}'s deliveries: {readings} readings over {len(kept)} decisions, "
        "as its record counts and digests them"
    )


def main(folder: Path) -> None:
    started_s = time.perf_counter()
    folder.mkdir(parents=True, exist_ok=True)
    experiment = folder / "experiment.json"
    experiment.write_text(EXPERIMENT.model_dump_json(indent=2, exclude_defaults=True))
    (folder / "authorisation.json").write_text(AUTHORISATION.model_dump_json(indent=2))
    results = folder / "results"
    with Simulator(authorisation=AUTHORISATION) as simulator:
        run_experiment(simulator, experiment.read_bytes(), results)
    took_s = time.perf_counter() - started_s
    # The records, as a reader outside the runner reads them: from their
    # files, by their episode's number.
    records = [
        EpisodeRecord.model_validate_json(path.read_text())
        for path in sorted((results / EPISODES).iterdir(), key=lambda path: int(path.stem))
    ]
    print(f"{len(records)} records in {results}, in {took_s:.0f} s\n")
    compare(records)
    print()
    read_kept(results, records[KEPT])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]))
    else:
        with tempfile.TemporaryDirectory() as temporary:
            main(Path(temporary))
