# P23: Experiments: paired episodes, each with its record

**Status:** proposed, not started. Stage 2 of item 7 of the
[research priorities](research-validation-priorities.md), after
[P15](archive/p15-policy-port.md), stage A of decision
[0061](../decisions/0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md).
Part of the [simulator roadmap](README.md).

## Goal

An experiment compares policies on the same conditions. A condition is
what a run is made of besides its scenario: its seed, its weather, how
long it lasts. Every policy runs on every condition, and each pair of
episodes shares its run's weather and its run's chance. Each episode
leaves a record that names everything that made it what it was:
- the scenario, the models and the inputs;
- the policy, its settings and its seed;
- the software;
- what the policy was given and what it gave.

From that record a reader can tell two episodes apart, run one again and
check it, and score it with measures that are not written yet. The
measures are stage 3 of item 7, and the baselines stage 4.

## Where it starts

P15.4's runner, `greenhouse_sim.experiment.run_episode`, runs an `Episode`
(a scenario, a policy and its principal, an end, a compute budget and an
information budget). It returns an `EpisodeSummary`: the scenario, the run
and its epoch, the policy's name and version, its budget, its receipts and
outcomes, its skipped decisions, and a digest of every delivery, receipt and
outcome. What a comparison needs and it does not have:

- **The run's conditions.** An episode's run is its scenario's own. Since
  decision
  [0075](../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md),
  a playback takes a seed, a weather and a shorter end. The runner passes
  none of them, so every episode on a scenario has one weather and one seed.
- **The policy's settings and seed.** `PolicyIdentity` is a name and a
  version, so the same policy with two settings, or two seeds, is named the
  same. P15.4 left an episode's own seed waiting "for scenarios that vary
  it".
- **What the policy gave.** A receipt says whether a revision was taken,
  not which actions it held. A decision that keeps the plan leaves nothing.
  The deliveries are digested, not kept, and a decision's time is recorded
  only when it was too long.
- **The inputs and the software.** The summary names the run's id, whose
  digest covers its scenario, its models and its configuration. It does not
  name the models' versions, the weather's series, or the versions of the
  simulator and the protocol that ran it.
- **A record outside the process.** The summary is an object returned to
  its caller, and nothing writes it down or reads it back.
- **Pairing.** Nothing runs several policies on the same conditions, or a
  policy over several of its own seeds.

## What stays stable

- The policy's contracts: `Policy`, `PolicyPort`, the allowlist, the
  context and the budget, in the process and over HTTP.
- An episode with no condition is the one P15.4 ran: the same run, the same
  deliveries, the same digest. No run id, replay digest or kept opening day
  moves.
- The local API, the consumer interface, the gateway and the ground truth's
  readers.

## Design

### A condition

A condition is a run's seed, its weather and its end. Each is none for the
scenario's own, and each is what decision 0075 already lets a run take: a
seed rides its weather's name, and a weather is one the scenario's summary
lists. A run's start stays its scenario's.

A sensor's draws are keyed by the run's seed, the sensor and the index of
its sample (`sensors.air`), not drawn in turn from one stream. So two
episodes on one condition share every sensor's noise and drop-outs,
whatever their policies make of the house: common random numbers, which a
paired comparison wants. A test holds it of the outside sensors, which no
policy moves.

### A policy, as an experiment makes it

In the process, an experiment makes each episode's policy fresh from an
entry:
- a factory, by its import path (`module:callable`);
- its settings, a JSON object;
- the policy's seed, for a policy that draws.

The factory takes the settings and the seed and returns a `Policy`. The
protocol's `Policy` does not change: a seed and settings are given when the
policy is made, not at `start`. A policy that reads a file, such as a
network's weights, names it in its settings, and the record keeps the
file's SHA-256 beside the settings.

A policy's entry may list several seeds: its repeated trials, each an
episode of its own on every condition.

### An episode's record

A record in the protocol (`greenhouse_protocol.experiment`, with a
published JSON Schema), so that a tool outside the simulator reads it as a
policy reads its port:

- **Its place:** the experiment's id, and the condition, policy and seed it
  pairs.
- **The run:**
  - the scenario, its greenhouse and its layout, and the scenario file's
    digest for a scenario that is not packaged;
  - the run's id and epoch, its seed, its weather and its end;
  - the models its manifest chooses, each with its registered version;
  - the SHA-256 of the weather series it ran under.
- **The policy:**
  - its identity, factory, settings and their digest, its files' digests
    and its seed;
  - its principal, its cadence, its information budget and its compute
    budget.
- **The software:** the versions of `greenhouse_sim`,
  `greenhouse_protocol` and Python, and the commit when it runs from a
  checkout.
- **The trace,** by decision:
  - when it was decided;
  - what each log delivered, counted and digested;
  - the decision itself: kept, a revision with its actions, or a
    cancellation;
  - its receipt;
  - its time on the runner's timer;
  - whether it was skipped.

  After the last decision come the outcomes. The deliveries themselves are
  kept only on request, in a file of their own: a season of a
  compartment's readings is large, and the run gives them again.
- **The digest:** P15.4's, of the deliveries, the receipts and the
  outcomes, so that an episode P15 ran keeps its digest. The decisions'
  times are left out of it, since they vary from one machine and run to
  the next.
- **No measures yet:** stage 3 adds them, each with its definition and its
  version, beside a record and not inside its digest.

`EpisodeSummary` stays for the runner's callers. The record is built from
the same episode, with what the summary does not hold.

### An experiment

An experiment is a JSON file with a published schema. It holds:
- its id;
- its scenario and layout, its principal and its end;
- its conditions;
- its policies' entries.

The runner runs every policy, at each of its seeds, on every condition, in
an order the file fixes, each episode on a run of its own. It writes:
- a directory holding the experiment as given, with its digest;
- a record per episode;
- for each episode asked to keep them, its deliveries.

```bash
python -m greenhouse_sim.experiment run experiment.json --out results/
python -m greenhouse_sim.experiment check results/episodes/3.json
```

`check` runs a record's episode again from what the record names and
compares the digests. It is the test of a deterministic replay that
decision 0061 asks of a given policy, not a promise of every one. A
stochastic policy's records, over its seeds, are what its repeatability is
measured from.

Episodes run one after another in the runner's process. Running them
apart, in processes or on workers of their own, waits for an experiment
large enough to need it, within P18's limits.

### What it leaves

- **A policy in a process of its own,** stepped at the runner's barriers,
  which P15 left as a design of its own. Until then such a policy steers a
  run on the wall clock, and the record names what it declares of itself.
- **A later start.** A held-out period that begins after the scenario's
  start needs a run that starts from a state part-way through. A
  condition's weather and seed vary a run, but its start does not.
- **The measures, the evaluator's instrumentation and the statistics over
  repeated trials:** stages 3 and 5 of item 7.

## Steps

| Step | Scope | Pull request | Status |
| --- | --- | --- | --- |
| P23.1 | An episode's condition: its run's seed, weather and end given to its playback; a policy made from its factory, settings and seed. With no condition, P15.4's episodes and digests unchanged. Tests: a condition's run id is the one decision 0075 gives; two policies on one condition share every outside reading. | `feat(sim): an episode's condition and a policy's settings` | Proposed |
| P23.2 | The episode's record in the protocol, with its schema; the runner builds it, with the models' versions, the weather's digest, the software and the trace by decision. | `feat(protocol): an episode's record` | Proposed |
| P23.3 | The experiment's file and schema; the paired runner, its output directory and its two commands; the deliveries kept on request. | `feat(sim): an experiment of paired episodes` | Proposed |
| P23.4 | An example and a guide: example 03's rule at two bands, on two weathers and two seeds, its records read back and compared. | `docs: run and read an experiment` | Proposed |
| P23.5 | The QA scenario below, run and recorded. | `test: an experiment's QA scenario` | Proposed |

## Acceptance criteria

- An experiment of two policies on two conditions writes four records.
  Each names its run's seed, weather and end, the models' versions, the
  weather's digest, the policy's identity, settings digest and seed, the
  software, and its trace by decision.
- Two episodes on one condition have one run id, one weather digest, and
  the same outside readings.
- `check` gives the same digest for a deterministic policy's record. A
  policy's settings changed give another settings digest and another
  record.
- Every record and experiment file validates against its published schema.
- An episode with no condition gives P15.4's digest. No run id, replay
  digest or kept opening day changes.

## Final QA scenario

On the climate box, with example 03's rule:
1. An experiment of the rule at two bands, on the scenario's own weather
   and a preset, with two seeds, runs from the command into a directory.
2. Its eight records are read back: their conditions, policies and seeds
   are as the file has them, and each pair shares its run id and weather
   digest.
3. `check` passes on one record. With the record's settings changed by
   hand, it fails, and says why.
4. One episode's deliveries are kept and read: their counts and digests
   are those its record gives.
5. The time the experiment took, and its records' size, are recorded.

## Open questions

1. **Where the record lives:** in the protocol (proposed), so that tools
   outside the simulator read it, or in `greenhouse_sim` alone until a
   second producer needs it.
2. **The deliveries:** kept on request (proposed), or always.
3. **A policy's seed:** given to its factory (proposed), or to `start`,
   which would change the protocol's `Policy`.
