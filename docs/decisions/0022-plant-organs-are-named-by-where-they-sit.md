# 0022: Plant organs are named by where they sit, and draw from a seed hierarchy

**Status:** Accepted
**Date:** 2026-10-06

## Context

P03 builds an organ-level tomato model: a plant as its stem, phytomers,
internodes, leaves, trusses, flowers and fruits. Every visible organ must
keep its identity from one day to the next and from one run to the next, so
that a fruit can be followed as it grows and ripens, an action can name the
leaf it prunes, and a later camera or tracker can be scored against the
truth. The model is stochastic, and its runs must replay exactly.

The simulator's engine already runs a simple daily tomato model, whose
plants feed the sensors, actions, ground truth and the reference baselines
the scenarios are tuned to. An organ-level plant fits none of them as they
stand.

## Decision

- An organ's identifier says where it sits in the plant, never anything
  else: `p01_n05` is plant `p01`'s fifth phytomer from the bottom,
  `p01_n05_leaf` its leaf, `p01_t02` the plant's second truss in order of
  appearance, `p01_t02_fl04` its fourth flower from the base, and
  `p01_t02_fr04` the fruit that flower set. A pruned leaf or harvested fruit
  keeps its place, so identifiers are never reused.
- Every organ records when it appeared as the plant's accumulated thermal
  time then; its thermal age follows. `Plant.problems` states the
  structure's rules, and tests hold every plant to them.
- Randomness follows a hierarchy of identifiers under one seed. There is one
  seed, the simulation's, and each draw's generator is derived from it and a
  hash of the plant, then, for an organ's own draws, the organ, then the
  process. One plant's or organ's draws never depend on another's existence
  or order. The hash is of identifiers, never of state: a drawer's state
  changes as it grows, and its draws must not.
- The organ-level model (`greenhouse_sim.biology.tomato.organ`) is built and
  shown in a plant lab first: a service (`greenhouse_sim.services.plants`)
  and its routes, and a viewer page. It is not yet one of the engine's plant
  models. P09's integrated scenario connects it to the engine, the sensors
  and the actions, when its contracts have settled.

## Consequences

- An organ can be followed, inspected or acted on by name, across days and
  runs, and its draws replay exactly.
- Until P09, the scenarios keep the simple model, and their baselines stay
  as they are; the organ model's behaviour is seen and tested in the lab.
- Connecting it to the engine means mapping its organs to what the sensors
  and actions read today, or moving them to read organs: P09 decides which.
