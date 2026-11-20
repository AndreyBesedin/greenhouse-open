# 0081: A benchmark's measures are versioned definitions, frozen before its baselines, and a baseline carries its provenance

**Status:** Accepted, with [P25](../roadmap/p25-measures-and-baselines.md)'s third step
**Date:** 2026-11-16

## Context

- **Decision 0061 asks for measures defined by what they measure:** each
  with its source, unit and denominator, and its missing processes; a
  benchmark's objectives, constraints, units and a minimal implementation
  of its measures fixed before any baseline is tuned or compared, "so that
  no score moves with a controller"; constraints and trade-offs reported,
  not one opaque reward; and climate-only comparisons apart from crop and
  economic ones until the crop models are validated.
- **It asks as well for a portfolio of baselines,** each named with its
  source and version, how faithful it is (exact, adapted or a proxy), its
  parameters, its sensors and actions, and a reference test: the example's
  rule as a smoke test; an observation-driven conventional controller as
  the matched baseline; documented grower practice as a labelled proxy,
  never a counterfactual; published controllers once their sources are
  checked; and the climate controller's loops, which read the true air, as
  a labelled privileged reference.
- **An episode's record holds no measure** (P23.2,
  `greenhouse_protocol.experiment.EpisodeRecord`). P23 leaves them to
  stage 3 of item 7 of the research priorities, "each with its definition
  and its version, beside a record and not inside its digest".
- **The context has a place for goals** (`greenhouse_protocol.context.Goal`:
  minimise, maximise, or within bounds, with a unit), empty in every run.
- **What the records measure honestly is narrow** (the
  [policy evaluation memo](../research/policy-evaluation-contract.md)): the
  heat given to the air, not fuel or cost; fresh fruit harvested, per
  plant per event; the policy's own actions, not the equipment's switches.
  The crop models' outputs are predictions: their test on AGC4 found that
  neither beats its baseline (decision 0076).
- **Morcego et al. (2023)** show a degenerate policy scoring well on one
  economic indicator alone. A single number is still what a reader, a
  grower or an economic controller weighs decisions by.
- **What exists for baselines:** example 03's rule, and the controller's
  loops (P11.2, decision 0058), exploratory heuristics by their own
  module's words. No baseline has a source recorded beside it. A policy is
  already made from an entry (P23): a factory by its import path, its
  settings and its seed, which an episode's record names.
- **The sources' licences differ** (the memo): GreenLight is BSD 3-Clause
  Clear; GreenLight-Gym is AGPL-3.0; several published controllers' code
  has no licence. AGC4's data are CC BY 4.0.
- **The options weighed:** measures as code alone, versioned with the
  package; or as definitions, data with a schema, each named and
  versioned. Code alone changes a score silently when the package moves;
  a definition can be digested and named with every value. The baselines'
  provenance was weighed as a decision of its own; it is one rule with the
  measures' (what a result depends on is named and fixed before it is
  run), so it is decided here.

## Decision

### Measures and benchmarks

- **A measure is a definition,** a packaged file read through a schema:
  its name and version; its class (`climate`, `record`, `crop`,
  `economic` or `priced`); what it measures, its unit and its denominator;
  its window and aggregation; its source, a field of the episode's record,
  one of the evaluator's instruments by name (decision 0082), or, for a
  priced score, the measures it weighs; and what it leaves out, in words.
  Its digest is the SHA-256 of its JSON, keys sorted.
- **A published version never changes.** A correction is a new version,
  as a crop parameter set's is (decision 0077).
- **A benchmark is a file, named and versioned, with its digest:** its
  scenario, layout and models; its conditions, split into tuning and
  held-out; its episodes' end and warm-up, cadence bounds, compute and
  information budgets; its principal's grants; its goals, objectives and
  constraints, each constraint with a tolerance; its prices, each with its
  source and date; and its measures, by name and version, each either
  *compared* or *reported*. An experiment names the benchmark it runs, by
  name, version and digest, and the runner refuses one that departs from
  it.
- **Frozen before its baselines:** no baseline is scored on a benchmark
  before its file is merged, and a change to it is a new version. Results
  on two versions are not compared.
- **The goals are the policy's to read:** the runner fills each policy's
  context's goals from its benchmark.
- **Scores are a record of their own,** beside an episode's: the record's
  digest, the benchmark's name, version and digest, each measure's name,
  version, digest and value, and the evaluator's software. They are never
  digested into the episode's record. A value is a number, or *not
  comparable* with its reason.
- **Constraints are reported apart:** each scored by the time outside its
  bounds and the integral of how far outside; an episode is feasible by
  its benchmark's tolerance; objectives and constraints are compared as a
  trade-off.
- **And also one priced score, labelled as such:** a `priced` measure that
  weighs the benchmark's measures in money, per m² of floor: the heat
  given at its stated price, and each constraint's integral at a penalty
  price the benchmark states. It is reported beside the measures it
  weighs, never in their place, with its prices and their sources, and
  its ranking at half and at double its penalty prices. Its penalties are
  a convention the benchmark states, not a loss a greenhouse measured.
- **By class:** a benchmark of the `climate` class compares only
  `climate`, `record` and `priced` measures, and a priced score in it
  weighs only those. A `crop` measure may be named in it as *reported*: a
  prediction of the crop model, shown beside each policy's scores and
  never compared, ranked or priced. A `crop` or `economic` measure is
  compared only by a benchmark whose crop models are validated (decision
  0060) and whose measures state their basis (decision 0062).

### Baselines

- **A baseline is a policy like any other:** the protocol's `Policy`, made
  from a `PolicyEntry`, reading only its port. Baselines live in
  `greenhouse_sim.baselines`, which the dependency test holds to what the
  policy port's modules may import.
- **Each carries a provenance file** beside its code, read through a
  schema:
  - its name and version, and its source: the publication or dataset, its
    DOI or address, its licence, its version or commit, and the file or
    section its rules come from;
  - its fidelity: *exact*, *adapted* with each departure listed, *proxy*,
    or *own rule*;
  - its information: *matched*, *privileged* (it reads what no policy
    may), or *oracle* (it is given what no one could know then, such as a
    perfect forecast);
  - its parameters, each with its value, unit and source;
  - the sensors it reads and the actions it gives;
  - its reference test, by name.
- **A reference test holds it to its source** on the same inputs: a
  published controller's levels against the source's own functions, its
  expected values generated apart and committed as decision 0063 has it;
  where the source publishes no function to run, its parts against cases
  worked out by hand and its departures listed; a rule of the
  repository's own against levels worked out by hand.
- **Privileged and oracle references are reported beside** the matched
  baselines, never ranked with them.
- **A logged trace of a grower's setpoints is a proxy,** labelled so, and
  never compared as a counterfactual.
- **Code is written from its source,** or ported with its licence's notice
  where the licence allows; nothing under the AGPL or with no licence is
  copied. Data are fetched, never committed, unless decision 0063 says
  otherwise.
- **Its settings come from its source,** or are tuned on a benchmark's
  tuning conditions only, with the tuning recorded.

## Consequences

- **The protocol gains a module** for measures, benchmarks, scores and
  provenance, each with a published schema, as the episode's record has
  one.
- **A score names everything it depends on:** the record, the benchmark
  and each measure's definition, by digest; a reader can tell two scores
  apart without the code that made them.
- **A result names what each baseline is:** a reader sees where a rule
  comes from, how far it departs from it, and what it could see.
- **A measure can be re-scored** on records already written, at a new
  version, beside the old one.
- **Tuning is visible:** a baseline tuned on a benchmark's tuning
  conditions records it, and the held-out conditions are run once.
- **A version moves when its provenance's parameters move,** as the
  policy's identity names it in every episode's record.
- **Adding a measure or a baseline is a recipe:** a definition file, or a
  baseline's code, its provenance file and its reference test.
- **A priced ranking can be read alone,** and its sensitivity to the
  penalty prices beside it says how far to trust it.
- **What it costs:** a definition is written before its code, and a
  measure's change is a new file rather than an edit; a published
  controller is a reproduction of its own, with its source checked before
  it is compared; a benchmark's prices are a choice it must source and
  date.
- **Worth revisiting:** if a measure cannot be stated as data without
  restating its code, such as one whose aggregation is a model of its own;
  if crop and economic measures need a basis the class field cannot
  carry; if the priced score's penalties come to be read as a greenhouse's
  losses; or if a remote baseline needs its provenance served rather than
  packaged.
