# 0024: Plants take their environment a day at a time, and it only holds growth back

**Status:** Accepted
**Date:** 2026-10-06

## Context

P03.7 couples the organ-level tomato model to its environment. Today the lab
keeps its plants in fixed presets. Later the greenhouse's climate model and
its spatial fields (P04) will say what each plant experiences where it
stands. The model must not care which. Its first responses need only go the
right way, but they must leave room for better ones.

Until now an organ's size was a function of its thermal age alone. Under a
changing environment, growth has to accumulate: a day's growth depends on
that day's conditions, and an organ that grew little in a poor week does not
catch up later.

## Decision

- A plant lives one day at a time, each in a `LocalEnvironment`:
  - the day's mean temperature;
  - its daily light integral of PAR;
  - its CO₂ concentration;
  - its root zone's water status.

  Anything that can say what a plant experienced on a day serves as its
  environment (`Environment.local(plant_id, day)`).
- Temperature sets the pace of development through thermal time, as before.
  Light, CO₂ and water set a day's growth factor, from 0 to 1: the product of
  a saturating response to light, a saturating response to CO₂, and the
  water status.
- The crop's sizes are its potential, reached under the reference conditions
  (25 mol/m²/d of PAR and 800 ppm of CO₂, well watered) or better. The
  environment only ever holds growth back: each response is capped at 1.
- Organs grow by increments: each step, the share of its final size that its
  S-curve adds, times the step's growth factor, never passing its final size.
  Growth lost is not made up.

## Consequences

- The lab, the greenhouse's climate and later spatial fields can all feed
  plants through one interface, and a plant's response to each is the same.
- Under a steady environment, growing in one step or day by day gives the
  same plant to rounding, not exactly, because growth now adds up step by
  step. Tests compare such plants to nine decimals.
- A plant can't grow larger than the crop's potential, however good its
  conditions. Better-than-reference growth would need the potential itself
  to depend on the environment, which a fuller model (assimilate supply and
  demand) can bring later.
- The responses are deliberately simple. Temperature's effects beyond
  thermal time, light's on development, and water's on anything but growth
  are not yet modelled.
