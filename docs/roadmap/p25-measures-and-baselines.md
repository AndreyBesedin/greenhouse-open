# P25: A benchmark's measures and baselines

**Status:** proposed, not started: the steps below, with decisions
[0081](../decisions/0081-a-benchmarks-measures-are-versioned-definitions-frozen-before-its-baselines-and-a-baseline-carries-its-provenance.md)
and
[0082](../decisions/0082-the-evaluator-reads-an-episodes-truth-after-its-policy-stops.md),
proposed. Stages 3 and 4 of item 7 of the
[research priorities](research-validation-priorities.md), and the start of
its stage 5 with one published controller, after
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
beside its objectives, and also weighed with them into one priced score,
in money, labelled as such and never shown in their place. A portfolio of
baselines, from simple rules to a published conventional controller and a
grower's practice, each with its provenance and a test that holds it to
its source, is run on it with one published economic controller, and the
first result is committed as written.

The first benchmark is climate-only: the air's temperature and humidity,
and the heat given. Its crop's harvest is reported beside each policy's
scores as the crop model's prediction, never compared. Claims on yield or
economics wait for the crop models of item 4, as item 7 and decision 0061
have it.

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
  has no licence or is not public. Of those, Panagopoulos et al. (2025), a
  cascaded economic NMPC that chooses a rule-based controller's lines, is
  the one the memo rates high in fidelity from its paper alone: its rules
  transfer, its crop (lettuce, van Henten's model) does not, and its code
  has no licence file, so it is written from the paper. AGC4, read since
  through its adapter ([the AGC4 memo](../research/agc4-coverage.md)),
  records its Reference compartment's heating and ventilation temperature
  setpoints and its humidity deficit every 5 minutes, under CC BY 4.0,
  though setpoint columns are often empty.

## When

As P23 finishes: P25.1 and P25.2 need only P23.2's record, which is
merged; P25.3's command reads P23.3's output directory. P25.4 freezes the
first benchmark, and nothing after it starts before it is merged: that is
decision 0061's "measures before baselines". The published controller
(P25.9) needs the conventional controller (P25.6) and the priced score
(P25.1). It goes on beside
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
  interface or the context. The context changes only to fill the goals,
  and gains a version, 2, for a goal's window of hours.
- **The local API:** people still read the truth there (decision 0036).
- **The packaged scenarios' runs:** the first benchmark's scenario is a new
  one; no packaged scenario's manifest, run id or screenshot moves.
- **The controller's loops** keep their equations; they become a labelled
  reference, not a baseline.

## Design

### A measure, defined (decision 0081)

A measure is a definition before it is a number, a packaged file read
through a schema in the protocol, `greenhouse_protocol.benchmark`, read
outside the simulator as an episode's record is:

- **its name and version;** a published version never changes, and a
  correction is a new version, as a crop parameter set's is (decision
  [0077](../decisions/0077-a-crop-parameter-set-is-a-file-named-and-versioned-and-told-apart-by-its-digest.md));
- **its class:** `climate`, `record` (what the episode's record alone
  says), `crop`, `economic`, or `priced` (a weighing of other measures in
  money);
- **what it measures,** its unit and its denominator (per m² of floor, per
  day, per device);
- **its window and aggregation:** over the episode, less a warm-up its
  benchmark states; summed, integrated through time, counted, or a
  quantile;
- **its source:** a field of the episode's record, one of the evaluator's
  instruments by name, or, for a priced score, the measures it weighs;
- **what it is not:** the processes it leaves out, in words (the heat
  given is not fuel, electricity, cost or emissions);
- **its digest:** SHA-256 of its JSON, keys sorted, as P23's settings
  digest, named with every value scored by it.

A value scored is a number, or *not comparable* with its reason, as
decision 0061 has it for a measure with no common basis. A benchmark of
the `climate` class compares only `climate`, `record` and `priced`
measures. It may name a `crop` measure as *reported*: the crop model's
prediction, shown beside each policy's scores and never compared, ranked
or priced. An `economic` measure, or a `crop` measure to compare, is
refused by it.

### A benchmark, frozen before its baselines (decision 0081)

A benchmark is a file, named and versioned, with its digest:

- **its scenario,** layout and models, by the scenario's manifest, and the
  scenario file's digest when it is not packaged;
- **its conditions,** split in two: *tuning*, on which a baseline that
  has settings to choose may be tuned, its tuning recorded; and
  *held-out*, run once for a result. They differ by seed and weather;
- **its episodes:** their end, the warm-up their measures leave out, the
  policy's cadence bounds, its compute budget and its information budget
  (decision 0061's matched budgets);
- **its principal's grants:** what a policy may act on, the same for
  every policy;
- **its goals:** the objectives and constraints, given to each policy in
  its context, and each constraint's tolerance;
- **its prices:** the heat's, and each constraint's penalty, each with its
  source and date;
- **its measures,** by name and version, each *compared* or *reported*.

An experiment (P23.3) names the benchmark it runs, by name, version and
digest. The runner then takes the benchmark's scenario, conditions, end and
budgets, refuses an experiment that differs from them, and fills each
policy's context's goals from it. Results on two versions of a benchmark
are not compared.

### Constraints, reported apart, and one priced score

- **A constraint is a goal within bounds:** the air's temperature within a
  band by day and another by night, its relative humidity below a limit.
  Each is given to the policy in its context, and scored by two measures
  of its own: the hours outside its bounds and the integral of how far
  outside (K·h, or %·h).
- **Feasible, by a tolerance:** an episode meets a constraint when its
  integral is within the tolerance its benchmark states, zero or more.
  Infeasible episodes are reported, not dropped.
- **Apart, as a trade-off:** objectives (the heat given) and constraints
  are reported side by side, and a comparison is a trade-off: each
  policy's heat against its time outside its bounds, with the policies no
  other beats on both marked. Morcego et al. (2023) show a degenerate
  policy scoring well on one economic number alone, the memo's reason for
  this.
- **And one priced score, labelled as such:** a `priced` measure, in money
  per m² of floor over the episode's window: the heat given at the
  benchmark's price for it, plus each constraint's integral at the penalty
  price the benchmark states (per K·h by day, per K·h by night, per %·h of
  humidity). The heat's price comes from a stated fuel price, its
  calorific value and a boiler's efficiency, each with its source and
  date; the penalty prices are a convention the benchmark states, not a
  loss a greenhouse measured, and the score says so. It is reported beside
  the measures it weighs, never in their place, and the report ranks the
  policies by it at the stated penalty prices and at half and double them,
  so that a ranking that turns on the penalties shows it. The equipment's
  electricity is left out until devices state their power, and the score
  names what it leaves out.
- **The day and the night:** each goal may name the hours of the day it
  holds in, an optional window on the protocol's `Goal`, the context's
  version moving to 2.

### The evaluator's instrumentation (decision 0082)

The evaluator reads the truth of an episode's run in
`greenhouse_sim.evaluation` alone, once the episode's policy has stopped:

- **the run as carried out:** the scenario's run on the episode's
  condition with the plan its revisions left, which the runner hands the
  evaluator as a `RunRequest` once the policy has stopped (the playback's
  run, made readable for it);
- **the house's air through time:** the air the run draws, averaged over
  the house's air cells, every minute through the episode: temperature,
  relative humidity and CO₂;
- **the heat given:** the heaters' heat to the air, from the house's own
  count (`heated_j`), over any window, to the second;
- **the equipment's states through time:** each device's level from the
  run's start, each switch with its moment, its level, and whether the
  controller's loop or a command set it;
- **the crop's harvest:** the run's `HARVEST` events, for the harvest
  reported as a prediction.

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
  and says so. The record does not change. A new version of a measure is
  scored this way on records already written.
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
| The priced score | priced | the heat given and the constraints' integrals, at the benchmark's prices | money per m² of floor, over the window | a greenhouse's cost or margin: its penalties are a convention, its heat is priced through a stated efficiency, not a modelled boiler; no electricity, crop or labour | first, labelled, beside the measures it weighs |
| Harvest | crop | the run's `HARVEST` events | fresh g per m² of floor | dry matter, fruit standing; a measured yield | first, reported as the crop model's prediction, not compared |
| Yield or resources across crop models | crop | each model's outputs, by decision 0062's conversions | its declared basis, or *not comparable* | — | after item 4, not in P25 |
| Fuel, electricity, cost, margin, emissions | economic | not modelled | — | — | once modelled, not in P25 |
| CO₂ | climate | no CO₂ source in the run | — | — | once a source and the crop's uptake exist, not in P25 |
| Labour | crop | the crew's hands and times | — | hours paid, cost | when a comparison needs it, not in P25 |

Every measure marked *first* is climate-only, the record's, or a priced
weighing of those, and runs on P25's benchmark; the harvest is reported
beside them. The class field and the refusal make a crop or economic
measure to compare a definition to add later, not a design.

### Baselines, each with its provenance (decision 0081)

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
  may), or *oracle* (it is given what no one could know then, such as a
  perfect forecast);
- its parameters, each with its value, unit and source;
- the sensors it reads and the actions it gives;
- **its reference test,** which holds it to its source on the same inputs.

A privileged or oracle reference is reported beside the matched ones,
never ranked with them. A logged trace of a grower's setpoints is a proxy,
never a counterfactual. A baseline's code is written from its source, or
ported keeping its licence's notice where the licence allows; nothing under
the AGPL or with no licence is copied (the memo).

| Baseline | Fidelity and information | Source | Reference test |
| --- | --- | --- | --- |
| Nothing on | own rule, matched | — | its levels stay at 0 |
| Example 03's rule | own rule, matched; a smoke test | the repository | its levels on a hand-made series of readings |
| A thermostat and a vent rule, with hysteresis | own rule, matched | the repository, after the loops' structure | its levels on a hand-made series |
| The conventional controller | adapted, matched | GreenLight's rule-based controls for Katzin (2021), `controls_katzin_2021.json`, its heating and ventilation lines with their smoothed proportional bands, for the heater and the roof vents | its levels against GreenLight's own control functions on the same inputs, computed under `research/` and committed as expected values (decision [0063](../decisions/0063-a-data-file-is-generated-committed-or-fetched-by-one-rule.md)) |
| A grower's practice | proxy, matched | AGC4's Reference compartment: its heating and ventilation temperature setpoints and humidity deficit, by hour of the day over a stated period of the challenge, through its adapter, driving the conventional controller's rules | its setpoints read back as the adapter gives them; fetched, never committed |
| The published economic controller | adapted, oracle | Panagopoulos et al. (2025), [doi:10.1016/j.ifacol.2025.11.828](https://doi.org/10.1016/j.ifacol.2025.11.828): a cascaded economic NMPC choosing a rule-based controller's lines, written from the paper | its rule layer's levels on a hand-made series; its optimiser, on a case whose best lines are worked out by hand, finds them within a tolerance stated first; its departures listed |
| The controller's loops | privileged | the simulator's own (P11.2, decision 0058) | its loops' own tests; run as the benchmark scenario's controller with a policy that keeps everything |

### Stage 5's start: one published controller

Item 7's stage 5, comparisons with policies of increasing complexity,
starts in P25 with one published controller, run on the benchmark beside
the portfolio:

- **Which:** Panagopoulos et al. (2025), the published controller the memo
  rates high in fidelity from its paper alone. Its upper level is an
  economic NMPC that chooses, over a horizon, the lines of the rule-based
  controller below it; its rules transfer to this greenhouse, and its
  crop, lettuce on van Henten's model, does not.
- **Written from its paper:** its code repository has no licence file, so
  nothing of it is copied; the paper (CC BY-NC-ND 4.0) is cited, not
  reproduced.
- **What it departs from:** its economic objective is the benchmark's
  priced score, the heat at its price and the constraints at their
  penalties, with no crop's revenue, since its crop does not transfer and
  P25 compares no crop measure; its prediction model is a model of this
  house's climate, given as a versioned asset in its information budget
  (decision 0061); each departure is listed in its provenance.
- **What it sees:** as in its paper, the true state and a perfect forecast
  of the weather, so it is labelled *oracle* and reported apart from the
  matched baselines, never ranked with them. A matched version, from the
  observations a policy gets and a forecast with its errors, is left to
  the future work.
- **Where it runs:** in the runner's process, as every other policy
  (P23), within the benchmark's compute budget; if its horizon cannot fit,
  the step shortens it and lists the departure. Its solver is a dependency
  whose licence allows it, as an optional extra, so the simulator's own
  install does not grow.

The other published controllers, a matched MPC, learned policies, and the
crop and economic benchmarks they would need, stay in the
[future work](future-work.md#intelligence-components)'s intelligence
components.

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
- **A report:** a table per measure; the trade-off of heat against time
  outside the band; the priced score's ranking at its penalty prices and at
  half and double them; the harvest each policy's run predicted, marked as
  a prediction; the privileged and oracle references apart; generated from
  an experiment's directory, with the benchmark's version, the records'
  digests and the software, and the time the experiment took.

### What it leaves

- **The rest of stage 5:** published controllers beyond the one above, a
  matched version of it, and learned policies.
- **Crop and economic measures to compare,** and fuel, electricity and
  cost, which are not modelled.
- **A later start,** for held-out periods within a season (P23 leaves it).
- **Measures at each place in the house,** from the grid's cells, beyond
  the house's mean.
- **CO₂ control,** which waits for a CO₂ source and the crop's uptake.

## Steps

Each step is a pull request. P25.1 to P25.4 are decision 0061's
"measures before baselines": none of P25.5 to P25.11 is merged before
P25.4.

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P25.1 | **Measures defined** (decision 0081): `greenhouse_protocol.benchmark` with the measure's definition and an episode's scores, each with its published schema; the first measures as packaged files: heat given, temperature outside its band, humidity above its limit, switches and hours run, actions by status, decisions skipped and their time, the priced score, and the harvest as a reported prediction | Each measure, on hand-made series, gives its value worked out by hand: air 2 K under its band for 3 h gives 6 K·h and 3 h; the priced score of hand-made measures at stated prices is their weighted sum; a definition changed gives another digest; a `crop` measure compared in a `climate` benchmark is refused, and named as reported is taken; every file validates against its schema | Proposed |
| P25.2 | **The evaluator's instruments** (decision 0082): the run as carried out handed to the evaluator once the policy stops; in `greenhouse_sim.evaluation`, the house's air through time, the heat given, the equipment's states through time and the crop's harvest | The heat given over whole hours equals the sum of the heat records; the reference greenhouse's heating loop's switches are those its `HouseAir` states give; a command that takes a device over shows as the command's switch; the dependency test holds the port's modules to importing none of it; on a steered run, the instruments read the steered air, not the scenario's own | Proposed |
| P25.3 | **Scoring:** an experiment's episodes scored after each policy stops, `scores/N.json` written; the `score` command, which replays a record and scores it if its digest matches | Example 03's rule, scored, gives the values its instruments give by hand; a record with its settings changed is not scored, and says why; scoring twice gives the same scores; no episode's digest moves | Proposed |
| P25.4 | **The first benchmark, frozen** (decision 0081): a new packaged scenario with the reference greenhouse's house, its heater, vents, fans, dehumidifier and sensors, no controller and no daily commands, under its seasonal weather; its tuning and held-out conditions by seed and weather; its episodes' end and warm-up, its budgets and grants; its goals and tolerances in the context, with a goal's window of hours and the context's version 2; its prices with their sources; its measures, compared or reported; an experiment that names it | An experiment on it that differs from it is refused, naming what differs; each policy's context lists its goals, by day and by night; its file's digest is in every score; no packaged run id moves | Proposed |
| P25.5 | **Simple rules** (decision 0081): nothing on, example 03's rule, and a thermostat and vent rule with hysteresis, each with its provenance file | Each passes its reference test; each runs on the benchmark's tuning conditions and is scored; the provenance files validate against their schema | Proposed |
| P25.6 | **The conventional controller,** from GreenLight's rules for Katzin (2021): its heating and ventilation lines with their smoothed proportional bands, for the heater and the roof vents, its parameters each with its source, its departures listed | Its levels agree with GreenLight's control functions on the same inputs within a tolerance stated before; it runs and is scored on the tuning conditions | Proposed |
| P25.7 | **The privileged reference:** the benchmark's scenario with the controller's loops chosen by its manifest, a policy that keeps everything, labelled privileged | It runs on every condition, paired with the matched baselines by condition; the report puts it apart from them | Proposed |
| P25.8 | **A grower's practice, as a proxy:** AGC4's Reference compartment's setpoints by hour of the day, over a period of the challenge stated first, through its adapter, driving the conventional controller's rules, labelled proxy, its source attributed as CC BY 4.0 asks. The setpoints' coverage of that period is counted first; if too much is empty, the step records it and the proxy waits | Its setpoints are those the adapter gives for the period it names, with their gaps counted; the data are fetched, not committed; it runs and is scored on the tuning conditions | Proposed |
| P25.9 | **The published economic controller** (stage 5's start): Panagopoulos et al. (2025), written from its paper, its objective the benchmark's priced score, its prediction model a versioned asset, the true state and a perfect forecast, labelled adapted and oracle, its departures listed, its solver an optional extra | Its rule layer passes its hand-made series; its optimiser finds the hand-worked best lines within the tolerance stated first; it runs within the benchmark's compute budget and is scored on the tuning conditions; the report puts it apart from the matched baselines | Proposed |
| P25.10 | **Statistics and the report:** paired differences, their mean and bootstrap interval over conditions, seeds' spread, feasibility by tolerance, the trade-off of heat against time outside the band, the priced ranking at its penalty prices and at half and double them, the harvest reported as a prediction; a report from an experiment's directory | On made-up scores with a known difference, the interval holds it; a policy beaten on both measures is not marked on the trade-off; a ranking that turns on the penalty prices shows it; the report names the benchmark's version and every record's digest | Proposed |
| P25.11 | **The first result:** the portfolio and the published controller run on the held-out conditions, once, its report committed as written under `research/`, with its time and size | The report is committed with its experiment file, the records' digests and the commit that ran it; it says what it shows and what it does not: how each policy did in this simulator, not in a greenhouse; the priced score's penalties as a convention; the harvest as a prediction | Proposed |
| P25.12 | **An example and a guide:** an experiment on the benchmark, scored and reported; a recipe for adding a measure and one for adding a baseline | The example runs in CI's time; each recipe names the files it touches and the test to run | Proposed |
| P25.13 | The QA scenario below, run and recorded | Each step passes as it says | Proposed |

## QA scenario (proposed)

From a clean checkout:
1. Run an experiment on the first benchmark with nothing on and the
   conventional controller, on two tuning conditions, from the command into
   a directory. Each episode has its record and its scores.
2. Read one episode's scores: the heat given, the hours outside the band by
   day and by night, the humidity above its limit, the switches, the
   priced score with its prices, and the harvest marked as a prediction;
   check the heat given against the sum of its heat records over the same
   whole hours, and the priced score against its measures at its prices.
3. Score the directory again from its records with `score`: the same
   scores. Change one record's settings by hand: it is not scored, and the
   command says why.
4. Change one measure's definition: the benchmark's digest changes, and an
   experiment naming the old digest is refused.
5. Read a policy's context: its goals are the benchmark's, with their
   hours, at the context's version 2.
6. Generate the report: the paired differences against the conventional
   controller, their intervals, the trade-off, the priced ranking at its
   three penalty prices, the privileged reference and the published
   controller apart, and the time the experiment took.
7. Read the committed first result, and run one of its held-out episodes
   again with `check`: the same digest.

## Open questions

None: the questions it was proposed with are answered in its design and in
decisions 0081 and 0082. Stage 5 starts in P25 with one published
controller; the measures, benchmarks and scores live in the protocol; the
climate measures read the air the run draws, averaged over the house's air
cells, every minute; a record scored later is replayed to its digest first;
the first benchmark's scenario is a new one, with no controller and no daily
commands; held-out data are conditions held out by seed and weather; a goal
may name its hours, the context's version moving to 2; constraints are
reported apart and also weighed into one priced score, labelled as such; a
grower's practice is AGC4's Reference compartment's setpoints; the harvest
is reported as a prediction and not compared; and the baselines' provenance
is decided in 0081, so there are two decisions.
