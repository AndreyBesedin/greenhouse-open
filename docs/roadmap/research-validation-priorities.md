# Research validation and experiment priorities (proposal)

**Status:** Proposed, 2026-10-27. This is a priority update, not an implementation decision or a change to the numbered P11–P14 scopes. See [the roadmap](README.md), [P12](p12-setup-builder.md), [P13](p13-actions.md), [P14](p14-models-by-manifest.md), and the [repository audit](../audits/2026-10-13-repository-audit.md).

## Why now

The simulator already has deterministic runs, canonical observation/action contracts, a usable installation builder, dataset adapters, two tomato crop-model paths, and a model registry under construction. Software reproducibility and model interchangeability are necessary, but do not establish scientific validity. The next research milestone is a *reproduced, measured, independently checkable experiment*, rather than another model implemented only for a visually plausible demo.

## Priority order and gates

1. **Close post-audit maintenance.** Reconcile the audit's finding table with merged fixes and open follow-ups; resolve remaining correctness, contract, and test-order defects. Do not declare the audit closed merely because most work has landed. Keep the review and CI gates.
2. **Finish the viewer workspace currently in progress.** Deliver a coherent navigation and interaction space for the existing simulator, builder, scenarios and runs. This is a bounded UI completion milestone, not permission to expand into a chat assistant or new knowledge interface.
3. **Finish the minimum model-registry work needed for scientific comparisons (P14).** Independently registered model identity, version, parameters, checkpoints, manifest resolution and conformance. Finish the relevant P11 climate targets and P13 action/plan execution contracts as needed for controlled experiments, without blocking research on every remaining feature.
4. **Reproduce published tomato models.** Survey and select a tractable established tomato growth model first; preferably compare a simpler and a richer model, subject to equations, parameter availability and reproduction feasibility. Reproduce an author's reference result independently before integration. Keep the existing organ-level model as a separate baseline. Document the original authors, DOI, equations, units, assumptions, parameter provenance, code/data licences and deviations.
5. **Make scientific validation a reusable workflow.** Prepare recorded datasets, beginning with the available WUR AGC4 adapter where coverage and permissions permit. Define calibration/validation splits before tuning, including held-out compartments or periods; document sensor availability, missingness, sampling and uncertainty. Record metrics, plots, manifests, seeds, versions and execution environment. Compare crop yield/phenology and climate only when the data and output definitions genuinely match.
6. **Reproduce a bounded climate/energy baseline and compare research workflows.** Continue the existing Modelica/TiGwerLib investigation: reproduce a documented measured interval in OpenModelica if compatible; compare temperature/humidity and other outputs only with matched inputs and definitions. Measure workflow friction as well as accuracy and runtime; seek researcher feedback. FMI/FMU integration requires an actual use case and a separate decision.
7. **Establish policy evaluation contracts.** A policy reads observations and clock, never hidden truth; issues protocol actions/plans; forecasts are separately versioned records; evaluation reads ground truth on a separate path. Start with reproducible rule-based baselines and a general harness, then compare RL or external agents with identical scenarios, observations, action budgets and metrics. No requirement to implement an LLM interface.
8. **Complete P12.4's versioned crop-parameter editing when model registration supports it.** Parameter sets should be portable and tied to runs; calibration should not silently mutate a model's published default.
9. **Defer broad expansion.** Keep cucumber, sweet pepper and strawberry modelling on the roadmap, with source/sink and organ-level research as candidates, but do not schedule implementation until tomato reproduction has tested the model contracts. P12.5 mixed-crop runs, P12.6 publication, crop work within the day, richer equipment/physics, and the viewer's natural-language/knowledge assistant remain later, driven by evidence.

The order is a *priority order*, not a strict serial dependency chain. Scientific survey and dataset inventory can run alongside final UI/audit closure. No additional audit or UI polish should indefinitely postpone the first measured reproduction.

## Definition of a scientifically reproducible result

A reference experiment has: (a) precise publication and author attribution; (b) data and parameter provenance with licence review, without unlicensed redistribution; (c) documented input/output units and time alignment; (d) an executable, pinned recipe and model version; (e) calibration and held-out evaluation clearly distinguished; (f) numerical metrics and known discrepancies; (g) explicit limits on claims and on which physical processes are absent. Deterministic replay is necessary but is not independent validation. Avoid claiming measured accuracy from synthetic data.

## First small deliverables

- A model survey/selection decision with feasibility and licensing notes, including TOMGRO and richer tomato candidates.
- A self-contained reproduction of one published tomato result, with its reference curves or metrics and stated mismatches.
- A data coverage and permission report for an AGC4 experiment, with a fixed train/validation/test protocol.
- A bounded TiGwerLib/OpenModelica reproduction report, recording compatibility blockers if it cannot run.
- An interface/metrics decision for comparing policies; only then implement its minimal baseline.

## Explicit non-goals now

No natural-language knowledge interface, no assistant-driven greenhouse editing, no compulsory proprietary modelling software, no simultaneous implementation of four crops, no blanket replacement of the existing tomato model, and no claim that this simulator supersedes Modelica.

## Review before implementation

Decide which tomato model(s) have sufficient published material for an honest reproduction; which AGC4 observations actually constrain them; which current P14/P11/P13 steps are indispensable; and what threshold counts as a successful first benchmark. Update the existing project documents rather than duplicating their technical specifications.
