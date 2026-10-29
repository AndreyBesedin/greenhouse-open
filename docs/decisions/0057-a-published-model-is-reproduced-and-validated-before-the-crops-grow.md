# 0057: Published models are reproduced, then integrated, then validated

**Status:** Proposed
**Date:** 2026-10-27

## Context

The simulator's runs are deterministic, their identities and replays
pinned, and from P14 a manifest chooses each part's model from a registry.
That shows a run is the same run every time. It does not show that any of
its models is right: a deterministic test that passes is not evidence that
the crop or the climate behaves as a greenhouse does. The simulator grows
its one crop, the tomato, by two models of its own, the organ model (P03)
and a simple daily model, neither held to a published result or to
measured data.

The roadmap recorded what would come after P11 to P14: crop models from
plant research, a survey of four crops first and the organ model's
processes replaced where the survey supported others; a Modelica
comparison; intelligence components; a second CI pass; a second audit; and
an assistant in the viewer. It did not say which of them leads, and the
crop research began with breadth, four crops at once.

## Decision

- **Reproduce, then integrate, then validate.** The work after the
  projects in progress is, in this order of priority:
  1. the repository audit closed: its table maps each finding to the work
     that answered it, and `AUDIT.1` to `AUDIT.4` close with P14;
  2. the setup builder finished as far as P12.3: its QA scenario run, and
     its open questions answered or carried into P12.4 to P12.6;
  3. P14's registry, and of P11 and P13 only what a first experiment needs
     (below);
  4. two published tomato models reproduced, then made crop models of
     the run (decision 0060);
  5. a validation on measured data, a workflow others can repeat;
  6. a bounded comparison with Modelica, as the roadmap records it;
  7. the evaluation of policies, through the intelligence components'
     interface;
  8. P12.4's crop parameters as versioned assets.

  It is an order of priority, not a chain: a survey or a dataset's
  inventory goes on beside the first three.
- **A published model is a P14 crop model.** It is registered as the organ
  and simple models are (decisions 0054 and 0055), with its parameters,
  each with its source, and its version. Before it grows the run's crop,
  it is reproduced on its own and compared with a reference
  implementation, run on the same inputs: the authors' code where it is
  published, a named later implementation where it is not, said to be
  that, and their published outputs besides. The differences, and what
  causes them, are recorded with it. Its authors, the publication, the
  equations' and the parameters' sources, and the licences of what is
  reused are named.
- **Three milestones, each its own claim:** (A) a model reproduced on its
  own, which shows its implementation agrees with a reference, not that
  the model is right; (B) the model made a crop model of the run, chosen
  by the manifest, its outputs unvalidated predictions; (C) the model
  validated on measured crop data, after which its outputs are claims of
  the strength the validation supports.
- **The organ and simple models are kept,** as baselines beside the
  published ones, the organ model the one of single plants and organs, not
  replaced process by process. Changing either is a version of its own,
  for a reason of its own.
- **Validation is held apart from tests.** A software contract test, a
  deterministic regression test, a published result reproduced and a
  validation on measured data are four things, and each says which it is.
  A validation fixes its calibration and test data before any tuning, by
  held-out compartments or periods; keeps measured, derived and synthetic
  signals apart; and reports its metrics, its sample counts and what is
  missing. A dataset is downloaded, not redistributed, unless its licence
  allows.
- **The other crops wait.** Cucumber, strawberry and sweet pepper, and
  their survey, come after the tomato's reproduction has tested the
  registry's crop interface.
- **Of P11 and P13, only what a first experiment needs.** P13.9's policy
  loop on the run stays, the first user of the policies' evaluation.
  P13.10's recorded QA scenario waits. P11.2, venting and humidity on the
  controller, stays, for a rule-based climate baseline and a matched
  Modelica comparison; the rest of P11 waits. The gateway's speed, which
  bounds a plan at 1,000 occurrences, waits for an experiment that needs
  larger plans.

## Consequences

- The roadmap's crop research is rewritten to match, and the order is kept
  in [the research priorities](../roadmap/research-validation-priorities.md).
- Each published model has to bring what a reproduction needs: equations,
  parameters with their sources, and a reference implementation or
  published outputs to compare with. A model without them is a blocker
  recorded, not a gap filled by guesses.
- A reproduction that fails is a result, and is recorded as one.
- The assistant, the second audit and the second CI pass stay on the
  roadmap, after these.
- Still to decide, each in its own record when it is reached: the first
  dataset's splits and metrics, and how a policy's evaluation is scored.
  Which tomato models, and what counts as reproducing each, is decision
  0060; what a crop model declares for the run to integrate it, decision
  0062.
