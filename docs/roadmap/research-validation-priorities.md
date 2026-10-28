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
4. **Reproduce a published tomato model.** Survey the tractable published
   tomato models, Reduced-State TOMGRO and a richer one among them, for
   their equations, parameters and sources, inputs, time steps, published
   outputs and licences, and choose one, in a decision. It is written as a
   P14 crop model, registered with its parameters, each with its source,
   and its version (decisions 0054 and 0055). Before an experiment uses
   it, it is compared with the original implementation: the authors' code,
   run on the same inputs, where it is published, and their published
   outputs otherwise, with the differences and their causes recorded. The
   organ model stays, as a baseline. The roadmap's crop models from plant
   research hold the rest of the plan. The survey is
   [the tomato model memo](../research/tomato-model-feasibility.md), and
   decision [0060](../decisions/0060-the-first-tomato-model-reproduced-is-vanthoors-as-greenlight-runs-it.md)
   proposes the first model.
5. **Validate on measured data, as a workflow others can repeat.** Begin
   with the WUR AGC4 dataset, through its adapter, where what it measures
   and its licence allow: inventory what it records (weather, climate,
   CO₂, light, equipment, crop and yield measurements), its sampling and
   what is missing. Fix the calibration and test data before any tuning,
   by held-out compartments or periods. Report the metrics, sample counts,
   missing data and run times, and compare crop or climate outputs only
   where their definitions and units match.
6. **Compare with Modelica, bounded.** As the roadmap's greenhouse R&D
   workflows and Modelica comparison plan it: one documented, measured
   interval of TiGwerLib reproduced in OpenModelica, then compared on
   matched inputs, its blockers recorded rather than worked around.
7. **Evaluate policies.** Through the intelligence components' interface,
   as the roadmap plans it: a policy reads observations and the run's
   clock, never the ground truth, and acts through the protocol's plans;
   the evaluation alone reads the truth. A documented rule-based baseline
   comes first, and others are compared with it on the same scenarios,
   seeds and budgets. The contract is in
   [the policy evaluation memo](../research/policy-evaluation-contract.md),
   which decision [0061](../decisions/0061-a-policy-acts-on-a-run-as-a-consumer-and-is-scored-from-outside-it.md)
   proposes.
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

- A survey of tomato models, and the first one chosen, in a decision.
- That model reproduced as a P14 crop model, compared with its original
  implementation, the differences explained.
- An inventory of the AGC4 dataset for that model, with its calibration
  and test data fixed.
- TiGwerLib's documented interval reproduced in OpenModelica, or its
  blockers recorded.
- The policies' evaluation decided, then its rule-based baseline.

## Not now

No assistant or other natural-language interface; no proprietary
modelling software required; no four crops at once; the organ model not
replaced; and no claim that the simulator does what Modelica does.

## To decide before the work starts

Which tomato model comes first, and what counts as reproducing it; which
of AGC4's measurements constrain it; the first splits and metrics; and how
a policy's evaluation is scored.
