# 0081: A benchmark's measures are versioned definitions, frozen before its baselines

**Status:** Proposed, with [P25](../roadmap/p25-measures-and-baselines.md)'s plan
**Date:** 2026-11-16

## Context

- **Decision 0061 asks for measures defined by what they measure:** each
  with its source, unit and denominator, and its missing processes; a
  benchmark's objectives, constraints, units and a minimal implementation
  of its measures fixed before any baseline is tuned or compared, "so that
  no score moves with a controller"; constraints and trade-offs reported,
  not one opaque reward; and climate-only comparisons apart from crop and
  economic ones until the crop models are validated.
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
  economic indicator alone.
- **The options weighed:** measures as code alone, versioned with the
  package; or as definitions, data with a schema, each named and
  versioned. Code alone changes a score silently when the package moves;
  a definition can be digested and named with every value.

## Decision

- **A measure is a definition,** a packaged file read through a schema:
  its name and version; its class (`climate`, `record`, `crop` or
  `economic`); what it measures, its unit and its denominator; its window
  and aggregation; its source, a field of the episode's record or one of
  the evaluator's instruments by name (decision 0082); and what it leaves
  out, in words. Its digest is the SHA-256 of its JSON, keys sorted.
- **A published version never changes.** A correction is a new version,
  as a crop parameter set's is (decision 0077).
- **A benchmark is a file, named and versioned, with its digest:** its
  scenario, layout and models; its conditions, split into tuning and
  held-out; its episodes' end and warm-up, cadence bounds, compute and
  information budgets; its principal's grants; its goals, objectives and
  constraints, each constraint with a tolerance; and its measures, by name
  and version. An experiment names the benchmark it runs, by name, version
  and digest, and the runner refuses one that departs from it.
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
  trade-off, with no single score.
- **By class:** a benchmark of the `climate` class names only `climate`
  and `record` measures. A `crop` or `economic` measure is scored only by
  a benchmark whose crop models are validated (decision 0060) and whose
  measures state their basis (decision 0062).

## Consequences

- **The protocol gains a module** for measures, benchmarks and scores, each
  with a published schema, as the episode's record has one.
- **A score names everything it depends on:** the record, the benchmark
  and each measure's definition, by digest; a reader can tell two scores
  apart without the code that made them.
- **A measure can be re-scored** on records already written, at a new
  version, beside the old one.
- **Tuning is visible:** a baseline tuned on a benchmark's tuning
  conditions records it, and the held-out conditions are run once.
- **What it costs:** a definition is written before its code, and a
  measure's change is a new file rather than an edit.
- **Worth revisiting:** if a measure cannot be stated as data without
  restating its code, such as one whose aggregation is a model of its own;
  or if crop and economic measures need a basis the class field cannot
  carry.
