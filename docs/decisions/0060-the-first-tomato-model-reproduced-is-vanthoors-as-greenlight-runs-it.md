# 0060: The first tomato model reproduced is Vanthoor's, as GreenLight runs it

**Status:** Proposed
**Date:** 2026-10-28

## Context

Decision 0057 puts one published tomato model, reproduced and compared with
its original implementation, before the simulator grows a crop by it, and
leaves which model, and what counts as reproducing it, to a record of its
own. The [feasibility memo](../research/tomato-model-feasibility.md) weighs
two candidates on what a reproduction needs:

- **Reduced-State TOMGRO** (Jones et al. 1999): five states, a daily step,
  small. Its equations and parameters are in a paper behind a subscription
  and restated in open papers. No implementation by its authors, and none
  of its validation data, was found published, so a reproduction can only
  be compared with published values.
- **Vanthoor's tomato yield model** (Vanthoor et al. 2011; the thesis's
  chapter 9, open), as Katzin (2021) simplified it: seven states, a
  sub-daily step, about thirty parameters, each cited to its table. Its
  authors' group runs it in GreenLight, open source under the BSD 3-Clause
  Clear licence, which runs the crop alone from given drivers. The
  GreenLight trial's climate data are open (CC BY-SA 4.0); its crop
  measurements are not.

The run gives a crop model one day at a time: the day's mean temperature,
PAR integral and CO₂. Reduced-State TOMGRO fits that day; Vanthoor's model
needs the day's course of temperature, light and CO₂.

## Decision

- **Vanthoor's model, as GreenLight runs it, is reproduced first.** It is
  the only candidate whose original implementation can be run on the same
  inputs, which is decision 0057's stronger comparison.
- **The reproduction is independent:** written from the thesis's chapter 9
  and Katzin (2021)'s simplifications, not ported from GreenLight's model
  definitions, and kept in a research folder outside the simulator's
  packages until it is reproduced.
- **What counts as reproducing it:** driven by the same series of canopy
  temperature, PAR and CO₂ as a standalone GreenLight crop run, at a pinned
  GreenLight version, each state's trajectory and the harvested dry matter
  lie within a tolerance stated before the run. Every difference beyond it
  is reported with its cause, or reported as unexplained. A reproduction
  that fails is recorded as a result.
- **It is recorded as an experiment:** a manifest of the model and both
  implementations' versions, the drivers and their checksum, the solver and
  its tolerances, the command and the results, as the research priorities
  ask.
- **It shows the implementation, not the model's truth:** a reproduced
  model is held to measured crop data only by the validation that follows
  (item 5 of the priorities).
- **Reduced-State TOMGRO comes second,** as the simple daily model beside
  it, compared with published values.
- **The crop part's contract changes after, not before:** a rung given its
  day's course of air and light, so that the reproduced model can grow the
  run's crop, is P14's work once the reproduction holds.

## Consequences

- GreenLight is a reference the experiment runs, at a pinned version, not
  a dependency of the packages. The 4TU data are downloaded when it runs,
  never committed, and anything derived from them that is published keeps
  their licence and attribution.
- Its result is a statement about the implementation: that the equations
  as read give what the authors' code gives. A model that is right for a
  greenhouse is the validation's question, on measured data.
- The run's house holds CO₂ with no crop taking it up and nothing
  enriching it. A model whose growth answers CO₂ will show that once it
  grows the run's crop, and the climate may need it then.
- **Worth revisiting:** if the reproduction finds the published equations
  and GreenLight's code disagree beyond what the simplifications explain,
  or if an open source of Reduced-State TOMGRO's parameters and a
  published output on public inputs turn up, which would make it the
  smaller first result.
