# 0060: Two published tomato models become crop models of the run

**Status:** Accepted
**Date:** 2026-10-29

## Context

Decision 0057 puts published tomato models, reproduced and compared with a
reference implementation, before the simulator grows a crop by them, and
leaves which models, and what counts as reproducing each, to a record of
its own. The [tomato model memo](../research/tomato-model-feasibility.md)
weighs two, with their sources:

- **Reduced-State TOMGRO** (Jones, Kenig and Vallejos 1999): five states,
  updated once a day, a compact model. No code by its authors was found.
  Oliveira et al. publish a later implementation, under MIT, whose forms
  follow a spreadsheet of Jones's where it and the paper differ, and
  measured greenhouse tomato data (CC BY-NC 4.0).
- **Vanthoor's tomato yield model** (Vanthoor et al. 2011; the thesis's
  chapter 9), as Katzin (2021) simplified it: six ODE states over a
  sub-daily course, with a carbohydrate buffer. GreenLight, by Katzin and
  collaborators, implements that simplified model, under the BSD 3-Clause
  Clear licence, and runs the crop alone from given drivers.

They answer different questions: a fast, lower-complexity model of a
canopy's growth and yield, and a richer one of how the day's climate
drives them. Both grow a crop per unit of ground area, which the run's
crop part, built for single plants, cannot integrate as it stands
(decision 0062).

## Decision

- **Both become crop models of the run,** distinct, versioned and chosen
  by the manifest, beside the simple and organ models, which stay as
  baselines. Neither waits on the other's success; the work is sequenced
  as it is practical.
- **The variants reproduced are named:**
  - **Reduced-State TOMGRO, as Oliveira et al. implement it** (release
    v0.4.0, commit `b9b2c80`, [doi:10.5281/zenodo.13294322](https://doi.org/10.5281/zenodo.13294322)):
    five states, N, LAI, W, Wf and Wm, updated once a day; photosynthesis,
    maintenance respiration and the node rate worked out from the day's
    hourly temperature and PPFD and summed; one CO₂ value a day. Where its
    forms follow Jones's spreadsheet rather than the 1999 paper, each is
    listed in the memo. The 1999 paper's own forms, where they differ, are
    a second variant, for when its full text has been read. Fink et al.'s
    daily formulation is a different model, and is not this one.
  - **Vanthoor's model as Katzin simplified it, as GreenLight implements
    it** (its crop definition, its standalone extension and its
    composition file, at a pinned commit): six ODE states, `cBuf`,
    `cFruit`, `cLeaf`, `cStem`, `tCanSum` and `tCan24`, the last a
    first-order filter of the canopy's temperature; the leaf area index
    derived from `cLeaf`; driven by the canopy's temperature, the PAR above
    the canopy, from which the extension works out the PAR absorbed, and
    the CO₂. Oliveira et al.'s Vanthoor implementation, with its fruit
    development stages, is another variant, and not this one's reference.
- **Three milestones, each its own claim** (decision 0057):
  - **(A) Reproduced on its own,** outside the packages: implemented from
    the documented equations, the publications' and those the reference
    code documents, never by transplanting its source; and compared, on the
    same inputs, with the reference run at its pinned version. It shows
    that the implementation agrees with the reference, not that the model
    is right for a greenhouse; and it is a claim about that forcing, which
    does not carry over to the model driven by the run.
  - **(B) A crop model of the run,** as decision 0062 has it: registered
    with its version and a named, sourced parameter set, on a declared
    reference area, driven through a named driver profile whose effect is
    measured against the reference's own forcing, kept in checkpoints and
    replayed, held to its conformance test, chosen by the manifest, and
    shown in a documented scenario with its outputs. Its outputs are
    predictions, unvalidated, until milestone C.
  - **(C) Validated on measured crop data,** with its calibration and test
    data, and its metrics, fixed before any tuning (item 5 of the
    priorities): Oliveira et al.'s observations and AGC4's are the
    candidates, each assessed for its fit and its licence.
- **What a reproduction fixes before it runs,** for each model: the
  variant and the reference's version and checksum; the parameter set and
  the initial state, each value with its unit and source; the input series,
  with its units, time zone, step, any resampling, and its checksum, every
  transformation applied alike to both implementations; the solver and its
  step; the outputs compared and, for each, an absolute and a relative
  tolerance; and the commands. Then:
  - **Reduced-State TOMGRO:** its five states, day by day.
  - **Vanthoor's model:** its six states at the reference's output step,
    the leaf area index derived, and the harvested carbohydrate equivalent
    (mg CH₂O m⁻²) accumulated from its rate the same way in both: its
    native quantities, never called dry matter.
  - Each difference beyond its tolerance is reported with its cause, or as
    unexplained; an equation is never changed to force agreement, and a
    failed reproduction is recorded as a result.
- **Like is compared with like:** each model in its native quantities and
  on its own reference area; carbohydrate equivalents with carbohydrate
  equivalents, dry matter with dry matter, never either with fresh market
  yield; harvested with harvested, never with fruit standing; per m² of one
  area with per m² of the same area, never with per plant. A conversion
  between them is named, sourced and given its uncertainty.
- **The run's day is not either model's input as it stands:** a day's mean
  temperature and PAR integral (`LocalEnvironment`) is not what either
  reference takes. Decision 0062 gives a model its drivers through a
  named, versioned profile, whose effect is measured: any aggregation of
  the drivers, or substitution of one quantity for another, is a documented
  approximation with a test of what it changes.
- **Each licence kept apart:** GreenLight's BSD 3-Clause Clear; Oliveira
  et al.'s code, MIT on its repository (its Zenodo record says CC BY 4.0;
  the mismatch is recorded); the GreenLight trial's data on 4TU, CC BY-SA
  4.0; Oliveira et al.'s measured data, CC BY-NC 4.0, whose non-commercial
  term is assessed before anything derived from it is published. The
  references are run apart, at pinned versions; no code or data is copied
  into the repository.

## Consequences

- **Two references of different standing:** GreenLight is the simplifying
  author's group's own implementation; Oliveira et al.'s is an independent
  later one, following an unpublished spreadsheet. Agreement with it shows
  agreement with that variant, not with the 1999 paper.
- **The crop part is generalised** over instances and the capabilities
  they declare, as decision 0062 has it; the simple and organ models'
  runs do not change.
- **What a consumer observes of these crops** comes from measurement
  models, not from their state, which stays the evaluation's truth
  (decision 0062).
- **Worth revisiting:** if the 1999 paper's forms and the spreadsheet
  variant's differ enough to change a comparison's outcome; if a
  reproduction cannot be brought within tolerances declared beforehand;
  or if measured data shows either model unfit for the crops the simulator
  grows.
