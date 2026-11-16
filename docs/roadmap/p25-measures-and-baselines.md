# P25: A benchmark's measures and baselines

**Status:** proposed, not started: the steps below, with decisions
[0081](../decisions/0081-a-benchmarks-measures-are-versioned-definitions-frozen-before-its-baselines.md),
[0082](../decisions/0082-the-evaluator-reads-an-episodes-truth-after-its-policy-stops.md)
and
[0083](../decisions/0083-a-baseline-is-a-policy-with-its-provenance-and-a-reference-test.md),
proposed. Stages 3 and 4 of item 7 of the
[research priorities](research-validation-priorities.md), after
[P23](p23-experiments.md); stages B and C of decision
[0061](../decisions/0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md).
Part of the [simulator roadmap](README.md).

## Goal

A benchmark compares greenhouse decisions by what they did to the house,
not only by what they gave. Its measures are defined exactly, each with its
source, unit, denominator and what it leaves out, and fixed with the
benchmark before any baseline is run on it. Its evaluator reads the truth
a policy never sees: the house's air through time, the heat its heaters
gave, and every switch of its equipment. Its constraints are reported
beside its objectives, never folded into one number. A portfolio of
baselines, from simple rules to a published conventional controller and a
grower's practice, each with its provenance and a test that holds it to
its source, is run on it, and the first result is committed as written.

The first benchmark is climate-only: the air's temperature and humidity,
and the heat given. Claims on yield or economics wait for the crop models
of item 4, as item 7 and decision 0061 have it.

## Where it starts

- **The episode's record** (P23.2,
  `greenhouse_protocol/greenhouse_protocol/experiment.py`): an
  `EpisodeRecord` names the run (scenario, layout, run id and epoch, its
  condition and seed, each model and version, the weather's SHA-256), the
  policy (identity, entry, settings' and files' digests, principal,
  cadence, budgets), the software, and the trace by decision: what each
  log delivered, counted and digested, the decision, its receipt, its time
  and whether it was skipped; then the outcomes and a digest. It holds no
  measure: P23 leaves them to stage 3, "beside a record and not inside its
  digest".
- **The runner** (`greenhouse_sim.experiment`, P15.4 and P23):
  `record_episode` runs an episode on a playback of its own and returns its
  record. P23.3 (#736) adds the paired runner, its output directory
  (`experiment.json`, `episodes/N.json`, deliveries on request) and
  `check`, which runs a record's episode again and compares the digests.
- **What a record alone can score:** the policy's actions by status, from
  its outcomes; its decisions skipped and their times; its receipts taken
  and refused. Nothing of the house.
- **What an evaluator needs and does not have:**
  - *The run as carried out.* The truth of a run a policy steered is that
    of the scenario's run with the plan its revisions left: the playback
    holds it (`Playback._run()`, private), and `ground_truth(simulator,
    run, until_s, named=...)` scores a steered run's readings under the
    playback's name (`test_observation_accuracy.py`). The runner hands it
    to no one.
  - *The air through time.* `greenhouse_sim.ground_truth` gives what each
    point sensor truly sampled, at its sample moments, and what the crop's
    walk truly found: not the air between samples, and not the house's
    air as a whole (the memo's "the truth is the sensors' sampled
    readings"). The run has the rest: the house's air as one volume
    (`climate.house.HouseAir`: temperature, humidity, CO₂ and the heat
    given so far, `heated_j`), every minute through
    `services.climate_readings.house_air`; the grid's air at a moment,
    `climate.house.grid_mean`; the field at any moment,
    `services.fields.air_through_a_run`. People read these through the
    local API (decision 0036); no evaluator does.
  - *The heat given.* The heat records (`services.heat_log`) give the
    heaters' heat to the air each hour, in MJ per m² of floor, modelled
    from their rated output and levels, and reach a policy as a heat
    meter's observation (`services.policy_context`). They are hourly, so
    an episode that ends within an hour loses its last part; `heated_j`
    does not.
  - *The equipment's switches.* Each loop's state is kept with the house's
    air (`HouseAir.heating`, `vent_stage`, `dehumidifying`); the levels the
    controller runs its devices at are `WholeHouse.controlled_at`; the
    commands a run applied are `climate.commands`' `applied` log; a command
    takes a device over from its loop (`ClimateRun.controls`). None is a
    log an evaluator reads (the memo: "recorded nowhere a consumer or an
    evaluator reads").
  - *The goals.* The capability context has a place for them
    (`greenhouse_protocol.context.Goal`: an id, a description, a unit, and
    minimise, maximise or within bounds), empty in every run, as P15 left
    it "until stage B fixes a scenario's". A goal has no time of day, so a
    band by day and another by night are two goals told apart in words.
- **The baselines there are:**
  - example 03's rule: the heater on below 15 °C and off above 17 °C, by
    one sensor, on the climate box; a smoke test, by the memo;
  - the climate controller's loops (`climate/control.py`, P11.2, decision
    [0058](../decisions/0058-a-climate-controller-switches-each-loop-at-its-edge.md),
    proposed): staged heating, venting, circulation and dehumidifying with
    hysteresis, which read the house's true air, "exploratory heuristics"
    by their own module's words; a privileged reference, not a comparator.
  - No conventional controller from a published source, and no grower's
    practice.
- **The scenarios there are:** the reference greenhouse runs its heater on
  the controller's heating loop and its vents and fans by daily commands
  (future work's P11.5 would turn them into targets); the climate box is
  shut and still under a constant 8 °C. Neither is a benchmark as it
  stands: in the first, the loop runs the heater until a policy's first
  command takes it over; the second's weather does not vary.
- **Held-out periods:** a run cannot start part-way through its scenario
  (P23's "what it leaves"). A condition varies a run's seed, weather and
  end (decision
  [0075](../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md)),
  so held-out data are held-out conditions.
- **The evaluation package:** `greenhouse_sim.evaluation` holds
  `observation_accuracy` and `sensor_truth`, and is the only importer of
  `greenhouse_sim.ground_truth` (`tests/test_dependencies.py`). The policy
  port's modules import neither (`POLICY_PORT_MODULES` there).
- **The crop models:** both tomato models are crop models of the run, and
  their test on AGC4, run once, found that neither beats its baseline (item
  4, milestone C; decision
  [0076](../decisions/0076-the-tomato-models-are-calibrated-on-agc4s-pre-trial-and-tested-once-on-its-challenge.md)).
  Their outputs are predictions.
- **The candidates for the portfolio** are the
  [policy evaluation memo](../research/policy-evaluation-contract.md)'s:
  GreenLight's rule-based controls for Katzin (2021)
  (`controls_katzin_2021.json`, BSD 3-Clause Clear) as the matched
  conventional baseline; AGC2's growers as a labelled proxy, whose archive
  could not be read; the published MPC and learning controllers, whose code
  has no licence or is not public. AGC4, read since through its adapter
  ([the AGC4 memo](../research/agc4-coverage.md)), records its Reference
  compartment's heating and ventilation temperature setpoints and its
  humidity deficit every 5 minutes, under CC BY 4.0, though setpoint
  columns are often empty.

## When

As P23 finishes: P25.1 and P25.2 need only P23.2's record, which is
merged; P25.3's command reads P23.3's output directory. P25.4 freezes the
first benchmark, and nothing after it starts before it is merged: that is
decision 0061's "measures before baselines". It goes on beside
[P24](p24-house-components-and-a-multi-node-climate.md), which adds a model
of the house's air and moves no packaged run: a benchmark names its
scenario's models by version, so P24 changes none of its numbers, and a
later version of the benchmark may choose P24's model.

## What stays stable

- **P23's record, its digest and `check`:** scores are a record of their
  own, beside an episode's, never inside its digest. No episode's digest,
  run id, replay digest or kept opening day moves.
- **What a policy reads:** the port, its allowlist, its budget and its
  context. No instrument of the evaluator's reaches the port, the consumer
  interface or the context. The context changes only to fill the goals
  (and, if P25.4 takes the proposed window, gains a version: open question
  7).
- **The local API:** people still read the truth there (decision 0036).
- **The packaged scenarios' runs:** the first benchmark's scenario is a new
  one; no packaged scenario's manifest, run id or screenshot moves.
- **The controller's loops** keep their equations; they become a labelled
  reference, not a baseline.

## Design

### A measure, defined (decision 0081)

A measure is a definition before it is a number, a packaged file read
through a schema in the protocol:

- **its name and version;** a published version never changes, and a
  correction is a new version, as a crop parameter set's is (decision
  [0077](../decisions/0077-a-crop-parameter-set-is-a-file-named-and-versioned-and-told-apart-by-its-digest.md));
- **its class:** `climate`, `record` (what the episode's record alone
  says), `crop` or `economic`;
- **what it measures,** its unit and its denominator (per m² of floor, per
  day, per device);
- **its window and aggregation:** over the episode, less a warm-up its
  benchmark states; summed, integrated through time, counted, or a
  quantile;
- **its source:** a field of the episode's record, or one of the
  evaluator's instruments by name;
- **what it is not:** the processes it leaves out, in words (the heat
  given is not fuel, electricity, cost or emissions);
- **its digest:** SHA-256 of its JSON, keys sorted, as P23's settings
  digest, named with every value scored by it.

A value scored is a number, or *not comparable* with its reason, as
decision 0061 has it for a measure with no common basis. A `crop` or
`economic` measure is refused by a benchmark of the `climate` class.

### A benchmark, frozen before its baselines (decision 0081)

A benchmark is a file, named and versioned, with its digest:

- **its scenario,** layout and models, by the scenario's manifest, and the
  scenario file's digest when it is not packaged;
- **its conditions,** split in two: *tuning*, on which a baseline that
  has settings to choose may be tuned, its tuning recorded; and
  *held-out*, run once for a result;
- **its episodes:** their end, the warm-up their measures leave out, the
  policy's cadence bounds, its compute budget and its information budget
  (decision 0061's matched budgets);
- **its principal's grants:** what a policy may act on, the same for
  every policy;
- **its goals:** the objectives and constraints, given to each policy in
  its context, and each constraint's tolerance;
- **its measures,** by name and version.

An experiment (P23.3) names the benchmark it runs, by name, version and
digest. The runner then takes the benchmark's scenario, conditions, end and
budgets, refuses an experiment that differs from them, and fills each
policy's context's goals from it. Results on two versions of a benchmark
are not compared.

### Constraints, reported apart

- **A constraint is a goal within bounds:** the air's temperature within a
  band by day and another by night, its relative humidity below a limit.
  Each is given to the policy in its context, and scored by two measures
  of its own: the hours outside its bounds and the integral of how far
  outside (K·h, or %·h).
- **Feasible, by a tolerance:** an episode meets a constraint when its
  integral is within the tolerance its benchmark states, zero or more.
  Infeasible episodes are reported, not dropped.
- **No single score:** objectives (the heat given) and constraints are
  reported side by side, and a comparison is a trade-off: each policy's
  heat against its time outside its bounds, with the policies no other
  beats on both marked. Morcego et al. (2023) show a degenerate policy
  scoring well on one economic number alone, the memo's reason for this.
- **The day and the night:** each goal may name the hours of the day it
  holds in, an optional window on the protocol's `Goal` (open question 7).

### The evaluator's instrumentation (decision 0082)

The evaluator reads the truth of an episode's run in
`greenhouse_sim.evaluation` alone, once the episode's policy has stopped:

- **the run as carried out:** the scenario's run on the episode's
  condition with the plan its revisions left, which the runner hands the
  evaluator as a `RunRequest` once the policy has stopped (the playback's
  run, made readable for it);
- **the house's air through time:** the air the run draws (the grid's,
  averaged over its air cells, or the whole house's), every minute through
  the episode: temperature, relative humidity and CO₂ (open question 3);
- **the heat given:** the heaters' heat to the air, from the house's own
  count (`heated_j`), over any window, to the second;
- **the equipment's states through time:** each device's level from the
  run's start, each switch with its moment, its level, and whether the
  controller's loop or a command set it.

None is served through the port, the consumer interface or the context;
`tests/test_dependencies.py` holds the policy port's modules, and the
baselines', to importing none of them. The local API serves people the
truth as it does today.

### Scoring an episode

- **In the runner's process:** an experiment on a benchmark scores each
  episode after its policy stops, and writes `scores/N.json` beside
  `episodes/N.json`: the record's digest, the benchmark's name, version and
  digest, each measure's name, version, digest and value, and the
  evaluator's software.
- **Later, from a record:** `python -m greenhouse_sim.experiment score
  results/` runs each episode again as `check` does, and scores it only if
  its digest is the record's; a record that does not replay is not scored,
  and says so. A new version of a measure is scored this way on records
  already written (open question 4).
- **Scores are not digested into the record,** and two scores of one record
  by one measure's version are the same.

### Which measures come first

| Measure | Class | Source | Unit and denominator | What it is not | When |
| --- | --- | --- | --- | --- | --- |
| Heat given | climate | the evaluator's heat given | MJ per m² of floor, over the window | fuel, electricity, cost, emissions | first |
| Temperature outside its band, by day and by night | climate | the house's air through time | K·h, and h | a leaf's or a fruit's temperature; the air at one place | first |
| Humidity above its limit | climate | the house's air through time | %·h, and h | condensation on the crop | first |
| Switches, and hours run, of each device | climate | the equipment's states through time | switches per day; level-hours per day | wear, electricity | first |
| The policy's actions by status: done, late, missed, refused | record | the record's outcomes | actions | the equipment's own switches | first |
| Decisions skipped, and their time | record | the record's trace | decisions; s, median and largest | — | first, reported, not compared across machines |
| Harvest | crop | `HARVEST` events | fresh g per m² of floor | dry matter, fruit standing | after item 4, not in P25 |
| Yield or resources across crop models | crop | each model's outputs, by decision 0062's conversions | its declared basis, or *not comparable* | — | after item 4, not in P25 |
| Fuel, electricity, cost, margin, emissions | economic | not modelled | — | — | once modelled, not in P25 |
| CO₂ | climate | no CO₂ source in the run | — | — | once a source and the crop's uptake exist, not in P25 |
| Labour | crop | the crew's hands and times | — | hours paid, cost | when a comparison needs it, not in P25 |

Every measure marked *first* is climate-only or the record's, and runs on
P25's benchmark. The class field and the refusal make a crop or economic
measure a definition to add later, not a design.

### Baselines, each with its provenance (decision 0083)

A baseline is a policy like any other: the protocol's `Policy`, made by a
factory from its settings and seed (P23's `PolicyEntry`), reading only its
port. It lives in a package of the simulator's, `greenhouse_sim.baselines`,
held by the dependency test to what the port's modules may import, and
carries a provenance file beside its code:

- its name and version, and its source: the publication or dataset, its
  DOI or address, its licence, its version or commit, and the file or
  section the rules come from;
- **its fidelity:** *exact*, *adapted* (each departure listed), *proxy*,
  or *own rule*;
- **its information:** *matched*, or *privileged* (it reads what no policy
  may), or *oracle*;
- its parameters, each with its value, unit and source;
- the sensors it reads and the actions it gives;
- **its reference test,** which holds it to its source on the same inputs.

A privileged reference is reported beside the matched ones, never ranked
with them. A logged trace of a grower's setpoints is a proxy, never a
counterfactual. A baseline's code is written from its source, or ported
keeping its licence's notice where the licence allows; nothing under the
AGPL or with no licence is copied (the memo).

| Baseline | Fidelity and information | Source | Reference test |
| --- | --- | --- | --- |
| Nothing on | own rule, matched | — | its levels stay at 0 |
| Example 03's rule | own rule, matched; a smoke test | the repository | its levels on a hand-made series of readings |
| A thermostat and a vent rule, with hysteresis | own rule, matched | the repository, after the loops' structure | its levels on a hand-made series |
| The conventional controller | adapted, matched | GreenLight's rule-based controls for Katzin (2021), `controls_katzin_2021.json`, its heating and ventilation lines with their smoothed proportional bands, for the heater and the roof vents | its levels against GreenLight's own control functions on the same inputs, computed under `research/` and committed as expected values (decision [0063](../decisions/0063-a-data-file-is-generated-committed-or-fetched-by-one-rule.md)) |
| A grower's practice | proxy, matched | AGC4's Reference compartment: its heating and ventilation temperature setpoints and humidity deficit, by hour of the day over a stated period of the challenge, through its adapter, driving the conventional controller's rules (open question 9) | its setpoints read back as the adapter gives them; fetched, never committed |
| The controller's loops | privileged | the simulator's own (P11.2, decision 0058) | its loops' own tests; run as the benchmark scenario's controller with a policy that keeps everything |

### Comparisons, and their statistics

- **Paired:** on each condition, each policy's measures against the
  matched conventional baseline's, the difference per condition. A
  stochastic policy's seeds are averaged within a condition, and their
  spread reported.
- **Over conditions:** the mean paired difference over the held-out
  conditions, with a 95 % interval by bootstrap over conditions, and the
  number of conditions, fixed in the benchmark before it runs.
- **Run once:** the held-out conditions are run once for the result,
  after every baseline's settings are fixed; the result is committed as
  written, as item 5's test on AGC4 was.
- **A report:** a table per measure and a trade-off of heat against time
  outside the band, generated from an experiment's directory, with the
  benchmark's version, the records' digests and the software, and the
  time the experiment took.

### Stage 5: a project of its own (proposed)

Item 7's stage 5, comparisons with policies of increasing complexity, is
left to a later project; P25 ends with its portfolio's comparison. Why:

- **Its policies need what P25 does not build:** an MPC needs a prediction
  model given as a versioned asset in its information budget (decision
  0061), and a learned policy its weights and training budget; both may
  need a policy in a process of its own, held at the runner's barriers,
  which P23 leaves as a design of its own.
- **Its sources need checking first:** of the published controllers the
  memo lists, Panagopoulos et al.'s code has no licence file, Morcego et
  al.'s is not public, and van Laatum et al.'s has none and depends on an
  AGPL file. Each is a reproduction, as item 4's models were, with its
  fidelity to measure before it is compared.
- **Its crop and economic scenarios wait for item 4:** their measures are
  P25's `crop` and `economic` classes, which no benchmark scores until the
  crop models are validated.
- **P25's benchmark is what it would compare on:** its measures,
  instrumentation, statistics and baselines are the ground the richer
  policies are compared against.

The [future work](future-work.md#intelligence-components)'s intelligence
components record it until it has a project.

### What it leaves

- **Stage 5,** above.
- **Crop and economic measures,** and fuel, electricity and cost, which
  are not modelled.
- **A later start,** for held-out periods within a season (P23 leaves it).
- **Measures at each place in the house,** from the grid's cells, beyond
  the house's mean (open question 3).
- **CO₂ control,** which waits for a CO₂ source and the crop's uptake.

## Steps

Each step is a pull request. P25.1 to P25.4 are decision 0061's
"measures before baselines": none of P25.5 to P25.10 is merged before
P25.4.

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P25.1 | **Measures defined** (decision 0081): `greenhouse_protocol.benchmark` with the measure's definition and an episode's scores, each with its published schema; the first measures as packaged files: heat given, temperature outside its band, humidity above its limit, switches and hours run, actions by status, decisions skipped and their time | Each measure, on hand-made series, gives its value worked out by hand: air 2 K under its band for 3 h gives 6 K·h and 3 h; a definition changed gives another digest; a `crop` measure in a `climate` benchmark is refused; every file validates against its schema | Proposed |
| P25.2 | **The evaluator's instruments** (decision 0082): the run as carried out handed to the evaluator once the policy stops; in `greenhouse_sim.evaluation`, the house's air through time, the heat given and the equipment's states through time | The heat given over whole hours equals the sum of the heat records; the reference greenhouse's heating loop's switches are those its `HouseAir` states give; a command that takes a device over shows as the command's switch; the dependency test holds the port's modules to importing none of it; on a steered run, the instruments read the steered air, not the scenario's own | Proposed |
| P25.3 | **Scoring:** an experiment's episodes scored after each policy stops, `scores/N.json` written; the `score` command, which replays a record and scores it if its digest matches | Example 03's rule, scored, gives the values its instruments give by hand; a record with its settings changed is not scored, and says why; scoring twice gives the same scores; no episode's digest moves | Proposed |
| P25.4 | **The first benchmark, frozen** (decision 0081): its scenario (open question 5), its tuning and held-out conditions, its episodes' end and warm-up, its budgets and grants, its goals and tolerances in the context (open question 7), its measures; an experiment that names it | An experiment on it that differs from it is refused, naming what differs; each policy's context lists its goals; its file's digest is in every score; no packaged run id moves | Proposed |
| P25.5 | **Simple rules** (decision 0083): nothing on, example 03's rule, and a thermostat and vent rule with hysteresis, each with its provenance file | Each passes its reference test; each runs on the benchmark's tuning conditions and is scored; the provenance files validate against their schema | Proposed |
| P25.6 | **The conventional controller,** from GreenLight's rules for Katzin (2021): its heating and ventilation lines with their smoothed proportional bands, for the heater and the roof vents, its parameters each with its source, its departures listed | Its levels agree with GreenLight's control functions on the same inputs within a tolerance stated before; it runs and is scored on the tuning conditions | Proposed |
| P25.7 | **The privileged reference:** the benchmark's scenario with the controller's loops chosen by its manifest, a policy that keeps everything, labelled privileged | It runs on every condition, paired with the matched baselines by condition; the report puts it apart from them | Proposed |
| P25.8 | **A grower's practice, as a proxy:** AGC4's Reference compartment's setpoints by hour of the day, over a period of the challenge stated first, through its adapter, driving the conventional controller's rules, labelled proxy, its source attributed as CC BY 4.0 asks. The setpoints' coverage of that period is counted first; if too much is empty, the step records it and the proxy waits | Its setpoints are those the adapter gives for the period it names, with their gaps counted; the data are fetched, not committed; it runs and is scored on the tuning conditions | Proposed |
| P25.9 | **Statistics and the report:** paired differences, their mean and bootstrap interval over conditions, seeds' spread, feasibility by tolerance, the trade-off of heat against time outside the band; a report from an experiment's directory | On made-up scores with a known difference, the interval holds it; a policy beaten on both measures is not marked on the trade-off; the report names the benchmark's version and every record's digest | Proposed |
| P25.10 | **The first result:** the portfolio run on the held-out conditions, once, its report committed as written under `research/`, with its time and size | The report is committed with its experiment file, the records' digests and the commit that ran it; it says what it shows and what it does not: how each policy did in this simulator, not in a greenhouse | Proposed |
| P25.11 | **An example and a guide:** an experiment on the benchmark, scored and reported; a recipe for adding a measure and one for adding a baseline | The example runs in CI's time; each recipe names the files it touches and the test to run | Proposed |
| P25.12 | The QA scenario below, run and recorded | Each step passes as it says | Proposed |

## QA scenario (proposed)

From a clean checkout:
1. Run an experiment on the first benchmark with nothing on and the
   conventional controller, on two tuning conditions, from the command into
   a directory. Each episode has its record and its scores.
2. Read one episode's scores: the heat given, the hours outside the band by
   day and by night, the humidity above its limit, the switches; check the
   heat given against the sum of its heat records over the same whole
   hours.
3. Score the directory again from its records with `score`: the same
   scores. Change one record's settings by hand: it is not scored, and the
   command says why.
4. Change one measure's definition: the benchmark's digest changes, and an
   experiment naming the old digest is refused.
5. Read a policy's context: its goals are the benchmark's.
6. Generate the report: the paired differences against the conventional
   controller, their intervals, the trade-off, the privileged reference
   apart, and the time the experiment took.
7. Read the committed first result, and run one of its held-out episodes
   again with `check`: the same digest.

## Open questions

1. **Stage 5:** a later project of its own (proposed, for the reasons
   above), or P25's closing step with one published controller.
2. **Where the definitions, the benchmark and the scores live:** in the
   protocol, `greenhouse_protocol.benchmark` (proposed), so that a reader
   outside the simulator reads them as it reads an episode's record; or in
   `greenhouse_sim` alone until a second producer needs them.
3. **Which air the climate measures read:** the air the run draws,
   averaged over the house's air cells, every minute (proposed); or the
   true air at each inside sensor's position, which `ground_truth` already
   gives at the sensors' sample moments; or the worst cell of the grid.
4. **A record scored later:** run again to its digest, then scored
   (proposed), with no change to the record; or the run as carried out
   written into the record, a version 2, so that it is scored without
   being run again.
5. **The first benchmark's scenario:** a new packaged scenario with the
   reference greenhouse's house, its heater, vents, fans, dehumidifier and
   sensors, no controller and no daily commands, under its seasonal weather
   at several seeds (proposed); or the reference greenhouse as it is, whose
   heating loop and daily commands run its devices until a policy takes
   each over; or the climate box, whose weather does not vary.
6. **Held-out data:** conditions held out by seed and weather, run once
   (proposed); or held-out periods, which wait for a run that starts
   part-way through.
7. **Day and night in a goal:** an optional window of hours on the
   protocol's `Goal`, the context's version moving to 2 (proposed); or a
   goal by day and one by night, told apart in their descriptions.
8. **Constraints:** reported apart, with a tolerance each, and no single
   score (proposed); or also a single score with the constraints as
   penalties at stated weights, labelled as such.
9. **A grower's practice:** AGC4's Reference compartment's setpoints,
   through its adapter, CC BY 4.0 (proposed); or AGC2's growers, CC0, whose
   archive could not be read.
10. **Crop measures:** left to the later project (proposed); or harvest
    defined in P25, reported as a prediction and not compared.
11. **The decisions:** three (proposed); or the baselines' provenance
    folded into 0081.
