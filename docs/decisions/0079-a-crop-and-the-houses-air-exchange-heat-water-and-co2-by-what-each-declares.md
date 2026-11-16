# 0079: A crop and the house's air exchange heat, water and CO₂, by what each declares

**Status:** Proposed, with [P24](../roadmap/p24-house-components-and-a-multi-node-climate.md)'s plan
**Date:** 2026-11-16

## Context

- **The crop reads the air; the air does not answer.** Decision 0062
  lets a crop model declare the fluxes it gives the air (transpiration
  and its latent heat, CO₂ taken up, radiation exchanged) as typed ports,
  and leaves the house's taking them to a climate decision of its own.
  Until then the coupling is one-way, from the air to the crop, by a
  declared profile.
- **The first driver profile substitutes the air for the canopy.**
  `house_hours`, version 1, gives Vanthoor's model the air's temperature
  where it reads its canopy's. Measured on GreenLight's greenhouse, that
  moves its temperature sum by about 2% and its harvest by under 0.3%
  ([`research/integrations/driver_profiles`](../../research/integrations/driver_profiles/README.md)).
- **The first comparison with TiGwerLib** found the simulator 3.7 K
  warmer on July's days, with no transpiring crop among the blockers it
  recorded, and could not compare the air's relative humidity at all,
  since the simulator's air takes no water from a crop
  ([`research/modelica`](../../research/modelica/README.md)).
- **Where the canopy's balance lives.** In Vanthoor's climate model, as
  GreenLight implements it, and in TiGwerLib's, the canopy is a node of
  the climate: its temperature, its transpiration (after Stanghellini) and
  its exchanges of heat are the climate's, and the crop model gives it its
  leaf area and takes CO₂ by its assimilation. The other way, each crop
  model working out its own canopy's balance, would give every crop model
  a climate's equations and a climate's step.
- **The run's parts step at their own rates.** The climate advances by
  stretches of at most a minute; Vanthoor's crop by the hour and
  Reduced-State TOMGRO's by the day (decision 0064).
- **Most crop models will not couple soon.** The organ and simple crops
  have no leaf area per m² of floor, and a study may want a one-way crop
  in a house that transpires, or a canopy matched to a reference's.

## Decision

**The canopy is a node of the climate,** in a house air model that has
one (`multi_node`, decision 0078). Its temperature, its transpiration by
Stanghellini's stomatal resistance as Vanthoor's model has it, its
convection with the air and its radiation with the cover, the screens,
the pipes, the floor and the sky are the climate's.

**A crop model declares two ports,** each a typed field of its
registration (decision 0055), optional, in its units, on its reference
area, converted to the floor's explicitly (decision 0062):

- **its leaf area,** per m² of floor, as the canopy's;
- **its CO₂ uptake,** the assimilation it takes from the air through its
  step.

A model that declares neither is not coupled.

**The manifest chooses the canopy:** none, prescribed, or the crop's.

- **None:** the house has no canopy node, as today.
- **Prescribed:** the house air's parameters give a leaf area, a constant
  or a recorded series, and no CO₂ is taken; for a crop that does not
  couple, or a comparison that matches its reference's canopy.
- **The crop's:** the crop's declared ports; a crop that declares none is
  refused, naming the port it lacks.

Several scopes, such as rows, give one canopy, their leaf areas summed
over the floor; a canopy per scope waits for rows of different crops
(P21).

**The crop reads its canopy back** through a driver profile of its own,
`house_canopy`, version 1: the canopy's temperature, the PAR above it and
the air's CO₂, substituting nothing. `house_hours` stays for one-way
runs.

**In turn, at the crop's step.** Through a crop's step, the climate runs
with the leaf area and uptake the crop gave at the step's start, held;
then the crop steps on the climate's means through it. The order is fixed,
so a run is the same when repeated and resumed. The split's effect is
measured against GreenLight's coupled solve, and reported.

**Conserved, and tested:** the water the canopy transpires is the water
the air takes, less what condenses on the cover and the screens; the CO₂
the air loses to the canopy is what the crop's step declares it took; the
latent heat of what transpires leaves the canopy's balance.

**In the run's identity:** the canopy's source, the driver profile and
their versions, as decision 0062 has a profile's.

## Consequences

- **Decision 0062's one-way coupling becomes a choice,** the default, not
  the only way: every run that chooses no canopy, and every crop model
  that declares no port, runs as it does today, with the same ids and
  digests.
- **Vanthoor's model and Reduced-State TOMGRO gain their ports:** both
  their leaf areas, and Vanthoor's its uptake, in versions that change no
  number of a one-way run.
- **The air's relative humidity can be compared** with a reference's once
  the canopy transpires.
- **The crop's checkpoint and the climate's stay apart,** each under its
  model's name and version; the order of their steps is the run's.
- **What it gives up:** within a crop's step the crop does not see the
  climate change, and the climate does not see the crop grow. For an
  hourly step that is small; for a daily one it may not be, and is
  measured.
- **Worth revisiting:**
  - if the split's effect at a daily step is larger than its reference
    allows, which would ask for a shorter coupling step or an iteration;
  - if a crop model computes its own canopy's balance, such as one with
    a 3D canopy, and needs to give the climate its fluxes rather than its
    leaf area.

## Open questions

1. **Whose balance:** the canopy's in the climate (proposed), or each
   crop model's own.
2. **The coupling step:** the crop's own, explicit (proposed), or shorter,
   or iterated to agreement within a step.
3. **The organ crop:** whether its plants' leaf area, summed over its
   scope, should couple, or it stays one-way.
