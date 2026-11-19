# Run and read an experiment

An experiment compares policies on the same conditions
([P23](../roadmap/archive/p23-experiments.md),
[decision 0061](../decisions/0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md)).
Every policy runs on every condition. The episodes on one condition share
their run's weather and its chance, so what differs between them is the
policies'. Each episode leaves a record of what made it what it was.

Example 06 (`examples/06_run_an_experiment.py`) runs one from end to end:
example 03's rule at two bands, on the climate box's own weather and the
cold spring day, each at seeds 1 and 2. This guide follows it. Given a
folder, it leaves there the experiment's file, its grant and its results,
for the commands below to be tried on; without one, it works in a
temporary folder. It takes about half a minute.

```bash
uv run python examples/06_run_an_experiment.py my-experiment
```

## The policy

An experiment makes each episode's policy fresh, from an entry:

- **`factory`:** a callable, by its import path (`module:callable`). It is
  called with the settings and the seed, and returns a `Policy`
  (`greenhouse_protocol.contracts.policy`).
- **`settings`:** a JSON object, without NaN or infinity. Each episode's
  policy is given a copy of its own.
- **`files`:** the settings that are paths to files the policy reads, such
  as a network's weights. The record keeps each file's SHA-256, and `check`
  refuses a file that has changed since.
- **`seeds`:** the seeds of its trials, each an episode of its own on every
  condition. None is one trial, at no seed, for a policy that draws
  nothing.

The runner imports the factory's module by its name, so the module must be
one Python can import where the runner runs. Example 06's policy is
`naive_heating:NaiveHeating`, in `examples/naive_heating.py`: example 03's
rule with its band as its settings, `on_below_c` and `off_above_c`, 15 and
17 °C for example 03's own. An example's file name begins with a number,
which no import path can, so the policy has a module of its own. The
commands below find it with `PYTHONPATH=examples`.

## The experiment's file

A JSON file, as `Experiment` (`greenhouse_sim.experiment.paired`) reads
it; its schema is `greenhouse_sim/greenhouse_sim/experiment/experiment.schema.json`.
Example 06 writes this one:

```json
{
  "experiment_id": "heating_bands",
  "scenario_id": "climate_box",
  "principal": {"kind": "policy", "id": "naive_heating"},
  "end_s": 1800.0,
  "conditions": [
    {"seed": 1},
    {"seed": 2},
    {"seed": 1, "weather": "cold_spring_day"},
    {"seed": 2, "weather": "cold_spring_day"}
  ],
  "policies": [
    {"factory": "naive_heating:NaiveHeating",
     "settings": {"on_below_c": 15.0, "off_above_c": 17.0}},
    {"factory": "naive_heating:NaiveHeating",
     "settings": {"on_below_c": 17.0, "off_above_c": 19.0}}
  ],
  "keep_deliveries": [0]
}
```

- **`experiment_id`, `scenario_id`, `layout`:** the experiment, and the
  scenario and layout every episode runs on; no layout is the scenario's
  own.
- **`principal`:** who the policies act as, in every episode.
- **`end_s`:** where each episode ends, in seconds from the run's start.
- **`conditions`:** each a run's `seed`, `weather` and `duration_days`,
  each the scenario's own when left out (decision
  [0075](../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md)).
  A weather is one the simulator has, by its name alone: a preset, a
  recorded file or `default`, without the `@` or `~` marks the viewer's
  QA takes. Every condition is checked before any episode runs: an
  unknown weather, more days than the scenario's, or a run that ends
  before `end_s`, refuses the whole experiment.
- **`policies`:** the entries above.
- **`plan_id`, `budget`, `compute_budget_s`:** the plan the policies give,
  their information budget and their compute budget; by default the plan
  `policy`, observations only, and no decision skipped for its time.
- **`keep_deliveries`:** the episodes whose deliveries are kept, by
  number (below).

The episodes run one after another, in the file's order: for each
condition, each policy, each of its seeds. They are numbered from 0 in
that order. Example 06 has four conditions and two policies at no seed, so
an episode's number is `2 × condition + policy`: 0 and 1 are the two bands
on the first condition, 6 and 7 on the last.

## Who may act

The runs are the simulator's, and who may do what on them is its
authorisation (decision
[0052](../decisions/0052-a-simulators-authorisation-is-a-file-it-is-given.md)).
By default only the local operator may act, so a policy that acts as its
own principal needs a grant. It is a JSON file, as
`greenhouse_protocol/greenhouse_protocol/schemas/authorisation-config.schema.json`
describes; example 06 writes one that lets its policy set levels and do
nothing else:

```json
{
  "version": 1,
  "groups": [
    {"group_id": "policies",
     "principals": [{"kind": "policy", "id": "naive_heating"}],
     "grants": [{"kinds": ["set_level"]}]}
  ]
}
```

Without it the experiment still runs, but every action the policy gives is
refused, and its records say so in their outcomes.

## Run it

```bash
PYTHONPATH=examples uv run python -m greenhouse_sim.experiment \
  --authorisation my-experiment/authorisation.json \
  run my-experiment/experiment.json --out results/
```

`--authorisation` comes before `run` or `check`: it is the command's, not
the subcommand's. `--out` is a folder that does not exist yet or is empty.
The command says each episode's digest as it ends:

```text
episode 0: condition 0, policy 0, seed None: digest 3c9248fbd0d61848
episode 1: condition 0, policy 1, seed None: digest 57f9e1f03cd61ebe
...
```

The seed it names is the policy's; a condition's seed is in its record.
It exits 1, saying why, for a file that is not an experiment, a condition
refused or a factory it cannot import. The conditions are checked before
anything is written, but a factory is imported only as its first episode
starts: a run refused for one leaves its folder begun, to be removed
before the experiment runs again.

An episode of half an hour of the climate box takes about four seconds.
Each revision a policy gives works the run's day out again under the new
plan, so a policy that changes its mind often takes longer than one that
does not.

## What it writes

```text
results/
  experiment.json      the file, byte for byte as given
  experiment.sha256    its SHA-256, as sha256sum writes it
  episodes/
    0.json             each episode's record, by its number
    ...
    7.json
  deliveries/
    0.jsonl            what episode 0's policy was given, kept on request
```

`sha256sum -c experiment.sha256`, in the folder, checks that the file is
still the one that ran.

## What a record holds

An `EpisodeRecord` (`greenhouse_protocol.experiment`), published as
`greenhouse_protocol/greenhouse_protocol/schemas/episode-record.schema.json`
so that a tool outside the simulator reads it:

- **`place`:** the experiment's id, and the condition and the policy the
  episode pairs, by their places in the file from 0.
- **`run`:** its scenario, greenhouse and layout, and the scenario file's
  digest for one that is not packaged; the run's id and epoch, its
  condition and the seed it ran at; its start, its length and where the
  episode ended; each part's model and its version, and a crop's parameter
  set; and `weather`, the SHA-256 of the weather it ran under, every 600 s
  through its end.
- **`policy`:** its identity, the entry it was made from (`made`) with the
  digest of its settings (`settings_sha256`, of the settings as sorted,
  compact JSON) and of its files; its principal, its cadence, its plan,
  and its information and compute budgets.
- **`software`:** the versions of `greenhouse-sim`, the protocol and
  Python, and the commit, when it ran from a checkout.
- **`trace`:** each decision in turn: when (`at`), what each of its logs
  delivered, counted and digested (`delivered`), the decision itself
  (`keep`, `revise` with its actions, or a cancellation), its receipt, its
  time on the runner's timer (`took_s`) and whether it was skipped.
- **`outcomes`:** what became of every action the policy gave.
- **`digest`:** of every delivery, receipt and outcome. The decisions'
  times are not in it, since they vary from one machine and run to the
  next.

Two records name the same episode when their digests agree. A record has
no measures of its own yet: they come in a later stage, beside a record
rather than inside its digest.

## Compare records

A record reads back from its file as it was written:

```python
from pathlib import Path

from greenhouse_protocol.experiment import EpisodeRecord

episodes = Path("results/episodes")
records = [
    EpisodeRecord.model_validate_json(path.read_text())
    for path in sorted(episodes.iterdir(), key=lambda path: int(path.stem))
]
```

Group them by `place.condition`. The episodes on one condition share
`run.run_id` and `run.weather.sha256`, and their sensors give them the
same draws: a sensor's noise is keyed by the run's seed, the sensor and
the sample, not drawn in turn, so the outside readings are the same
whatever the policies did. Tell their policies apart by `place.policy` and
`policy.made.settings_sha256`, and compare what they did by their traces
and outcomes. Example 06 prints:

```text
condition 0: its own weather, seed 1; run climate_box-climate-eeef710d, weather 8297c5ac5383
  15-17 °C: revisions 3, carried out 3, heater on 20 of 30 min
  17-19 °C: revisions 2, carried out 2, heater on 30 of 30 min
...
condition 2: cold_spring_day, seed 1; run climate_box-climate-15b8582b, weather 2a5fdcd9c7ff
  15-17 °C: revisions 1, carried out 1, heater on 25 of 30 min
  17-19 °C: revisions 1, carried out 1, heater on 30 of 30 min
```

The climate box's own weather is a still, constant night, which draws
nothing: its two seeds give two runs, but one weather digest. The cold
spring day's wind is gusty, so each of its seeds is a weather of its own.
On that colder night both bands keep the heater on from their first
reading.

## Check a record

```bash
PYTHONPATH=examples uv run python -m greenhouse_sim.experiment \
  --authorisation my-experiment/authorisation.json \
  check results/episodes/4.json
```

`check` makes the policy again from the record's entry, its files checked
against their digests first, runs the episode again on the record's run,
condition, principal, plan and budgets, and compares the digests. It says
`the same digest, …` and exits 0, or `another digest: …` and exits 1. It
is the test of a deterministic replay, not a promise for every policy: a
policy that draws gives its record again only at the same seed, and one
that reads the wall clock perhaps not at all. Under a compute budget, a
decision skipped for its time changes the digest, so a record checked on
a slower machine may give another.

It refuses, exiting 1 and saying why:
- a record that is not one, such as one whose settings were changed by
  hand (`a policy's settings digest is not that of its settings`);
- a policy given to the runner made already, which has no entry;
- a factory it cannot import (`there is no policy factory …`);
- a file the policy names that is not the one it ran with.

A check needs the grant the run had. Without it the policy's actions are
refused, and `check` reports another digest, not why: the record does not
name the authorisation its run was given.

## Keep the deliveries

A record counts and digests what each decision was given, but does not
keep it: a season of a compartment's readings is large, and the run gives
them again. `keep_deliveries` names the episodes whose deliveries are kept,
in `deliveries/N.jsonl`: one `Delivery`
(`greenhouse_protocol.contracts.policy`) a line, a line a decision. Each
line's logs, counted and digested with `delivered`
(`greenhouse_protocol.experiment`), are that decision's `delivered` in the
record:

```python
from greenhouse_protocol.contracts.policy import Delivery
from greenhouse_protocol.experiment import delivered

lines = Path("results/deliveries/0.jsonl").read_text().splitlines()
for traced, line in zip(records[0].trace, lines, strict=True):
    delivery = Delivery.model_validate_json(line)
    assert traced.delivered.observations == delivered(delivery.observations)
```

Example 06's half hour keeps 82 readings over 7 decisions, about 34 kB; a
record is about 10 to 15 kB.

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_paired_experiment.py \
  greenhouse_sim/tests/test_episode_record.py greenhouse_sim/tests/test_experiment.py
uv run pytest greenhouse_sim/tests/test_policy_in_its_own_process.py -k same_rule
uv run pytest tests/test_examples.py -m slow -k 06
```

The first are the runner's, the record's and the episode's; the second
holds `examples/naive_heating.py` to example 03's rule, by its digest on
the same run; the last runs example 06, which the fast checks leave out.

## What else to know

- **The policy's code is named, not kept.** A record names its factory by
  its import path, and the software by its versions and commit. A policy
  whose code changes under the same name and settings checks as another
  digest, so raise its identity's version when its code changes. The
  commit says nothing of changes not yet committed.
- **One process.** The episodes run one after another in the runner's
  process. A policy in a process of its own, over the port, steers a run
  on the wall clock instead, and the runner does not step it.
- **The start.** A condition changes a run's seed, weather and length,
  not its start: every episode starts at its scenario's start.
