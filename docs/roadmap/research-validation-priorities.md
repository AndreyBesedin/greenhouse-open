# Research validation and experiment priorities (proposal)

**Status:** Proposed, 2026-10-27, with
[decision 0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md).
It orders the work after the projects in progress; it changes no numbered
project's scope. The projects' own documents ([P11](p11-climate-setpoints.md),
[P12](p12-setup-builder.md), [P13](p13-actions.md),
[P14](p14-models-by-manifest.md)) and the [roadmap](README.md)'s future
work hold the plans it orders.

## Why now

The simulator has deterministic runs, the protocol's records for what a
greenhouse observes and what is done to it, a setup builder, adapters for
recorded datasets, two tomato models of its own, and a registry of models
under way (P14). Its runs are reproducible, and its models can be swapped.
Neither shows that a model is right. The next milestone is a result that
others can check: a published model reproduced, then held to measured
data.

## Priority order

1. **Close the audit.** The [repository audit](../audits/2026-10-13-repository-audit.md)'s
   table maps each of its 30 findings to the work that answered it;
   `AUDIT.1` to `AUDIT.4` close with P14. Nothing else is planned for it.
   A finding found open again is fixed as any defect is, and the second
   audit, on the roadmap, is the next look.
2. **Finish the setup builder as far as P12.3.** P12.0 to P12.3 are done.
   What is left of them is [P12](p12-setup-builder.md)'s QA scenario, run
   in the browser and recorded, and its open questions, answered or
   carried into P12.4 to P12.6. Nothing more is added to the viewer for
   now, and no assistant.
3. **Finish what a first experiment needs of P14, P11 and P13.** Of
   [P14](p14-models-by-manifest.md), each model registered with its
   identity, version, parameters, checkpoint state and conformance tests,
   and chosen by the manifest. Of [P13](p13-actions.md), P13.9's policy loop
   on the run, the first user of item 7; P13.10's recorded QA scenario
   waits. Of [P11](p11-climate-setpoints.md), P11.2, venting and humidity
   on the controller, for a rule-based climate baseline and a matched
   Modelica comparison; the rest waits. The gateway's speed, which bounds a
   plan at 1,000 occurrences, waits for an experiment that needs larger
   plans.
4. **Reproduce two published tomato models, then make them crop models of
   the run.** Reduced-State TOMGRO, five daily states, a compact and fast
   model, and Vanthoor's model as Katzin simplified it, a richer one with
   sub-daily dynamics, answer different questions: both are planned, and
   neither waits on the other's success (decision
   [0060](../decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md),
   after [the tomato model memo](../research/tomato-model-feasibility.md)).
   Each goes through three milestones, each its own claim:
   - **(A) Reproduced on its own,** outside the packages, from the
     publications, and compared on the same inputs with a pinned reference
     implementation, named for what it is: GreenLight, the Katzin group's,
     for Vanthoor's model; Oliveira et al.'s, a later implementation, not
     the 1999 authors', for Reduced-State TOMGRO. Agreement shows the
     implementation, not the model.
   - **(B) A crop model of the run,** registered with its parameters, each
     with its source, and its version (decisions 0054 and 0055), chosen by
     the manifest, integrated as decision
     [0062](../decisions/0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md)
     has it (a declared scope and reference area, a named driver profile,
     declared capabilities), checkpointed and replayed, held to a
     conformance test, and shown in a documented scenario; its outputs are
     predictions until (C).
   - **(C) Validated on measured crop data** (item 5).
   The organ and simple models stay, as baselines. Done: Reduced-State
   TOMGRO's milestone A,
   [`research/reproductions/reduced_tomgro`](../../research/reproductions/reduced_tomgro/README.md),
   which agrees with Oliveira et al.'s implementation on every state and
   day of a synthetic season; and Vanthoor's model's,
   [`research/reproductions/vanthoor_katzin`](../../research/reproductions/vanthoor_katzin/README.md),
   whose rates agree with GreenLight's at the same states, and whose run
   agrees with GreenLight's, both converged, on every output and hour of
   the same season. At GreenLight's default solver settings, the run
   reproduces neither GreenLight's answer nor GreenLight's own answer to
   the declared tolerances.
5. **Validate on measured data, as a workflow others can repeat.** Begin
   with the WUR AGC4 dataset, through its adapter, where what it measures
   and its licence allow: inventory what it records (weather, climate,
   CO₂, light, equipment, crop and yield measurements), its sampling and
   what is missing, and
   assess Oliveira et al.'s greenhouse tomato observations the same way,
   their licence (non-commercial) included. Fix the calibration and test
   data before any tuning, by held-out compartments or periods. Report the metrics, sample counts,
   missing data and run times, and compare crop or climate outputs only
   where their definitions and units match.
6. **Compare with Modelica, bounded.** As the roadmap's greenhouse R&D
   workflows and Modelica comparison plan it: one documented, measured
   interval of TiGwerLib reproduced in OpenModelica, then compared on
   matched inputs, its blockers recorded rather than worked around.
7. **Benchmark greenhouse decisions, repeatably.** Not only an interface
   and a rule: a capability to compare decisions fairly (decision
   [0061](../decisions/0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md),
   after [the policy evaluation memo](../research/policy-evaluation-contract.md)).
   A policy reads observations and the run's clock, never the truth, and
   acts through the protocol's plans; the evaluation alone reads the
   truth. In stages:
   1. the contracts: observations, actions, capabilities, identity and
      security, and the clock, for policies in the process and remote;
   2. an experiment harness: the policy's identity, its actions' trace,
      paired seeds and weather;
   3. the measures, defined exactly, with the evaluator's instrumentation
      and the constraints' handling;
   4. a portfolio of baselines, from the literature and from growers'
      practice and simple rules, each with its provenance;
   5. comparisons with policies of increasing complexity.
   Climate-only experiments can run early; claims on yield or economics
   wait for the crop models of item 4. Forecasts and perception stay with
   the intelligence components, on the same foundation.
8. **P12.4, crop parameters as versioned assets,** once the registry and
   the first published model carry versioned parameters. A calibration
   never changes a model's published defaults.

It is an order of priority, not a chain: a model survey or a dataset's
inventory goes on beside items 1 to 3, and no audit or viewer work holds
up the first reproduction.

**Later, as the roadmap records them:** cucumber, strawberry and sweet
pepper, after the tomato's reproduction has tested the registry's crop
interface; P12.5's rows of different crops and P12.6's publication; crop
work within the day; the CO₂ and light targets; the second CI pass; the
second audit; and the assistant in the viewer, after it.

## A reproducible result

A reproduction or a validation says which it is, and has:

- the publication, its authors and DOI, and the dataset's identifier and
  version;
- each parameter's value, unit and source, and each reused artefact's
  licence, with nothing redistributed that its licence does not allow;
- its inputs, their units, time steps and alignment;
- a recipe that runs it, with the model's version and the commit;
- its calibration and test data told apart;
- its metrics, its known differences, and the processes it leaves out.

A deterministic test that passes is not a validation, and a synthetic
signal is not a measurement.

## First deliverables

- A survey of tomato models, and the two chosen, in a decision (0060), with
  how a crop model declares its scope, drivers, outputs and capabilities
  (0062).
- Both models reproduced on their own, each compared with its pinned
  reference implementation, the differences explained (milestone A).
- Both made crop models of the run, chosen by the manifest (milestone B).
- An inventory of the AGC4 dataset, and an assessment of Oliveira et al.'s
  observations, for those models, with their calibration and test data
  fixed.
- TiGwerLib's documented interval reproduced in OpenModelica, or its
  blockers recorded.
- The benchmark decided (0061), then its contracts and harness, then its
  baselines.

## Not now

No assistant or other natural-language interface; no proprietary
modelling software required; no four crops at once; the organ model not
replaced; and no claim that the simulator does what Modelica does.

## To decide before the work starts

Each reproduction's tolerances, stated before its run (decision 0060);
which measured data constrain the models, AGC4's or Oliveira et al.'s; the
first splits and metrics; and which baselines and measures a first
benchmark uses.
