# 0078: A multi-node climate is a model of the house's air, chosen by the manifest

**Status:** Proposed, with [P24](../roadmap/p24-house-components-and-a-multi-node-climate.md)'s plan
**Date:** 2026-11-16

## Context

- **The house's air has two models,** both of the house air part
  (decision 0054): `whole_house`, one well-mixed volume solved exactly
  between moments (`climate/house.py`), and `grid`, the air cell by cell
  beside it, the default, which follows the whole house's air and its
  decisions (`climate/run.py`, `climate/day.py`). Each loop of the
  controller switches at the moment the whole house's air reaches its edge,
  found in closed form or by halving (decision 0058).
- **Only the air holds heat.** The glass has no heat capacity and passes
  U times the difference between the air inside and out, its U set by
  the wind. There is no floor, soil, screen, canopy or pipe, and no sky:
  the roof does not radiate to it.
- **The first comparison with a Modelica model** (item 6 of the research
  priorities, [`research/modelica`](../../research/modelica/README.md))
  set the whole house against TiGwerLib's (Sourisseau et al. 2026) on
  matched weather, geometry, roof windows and heating. No day of 11 in
  January or 11 in July came within the bar stated before the runs, a
  day's RMSE of 1.6 K: the whole house ran 5.7 K colder on January's
  nights and 3.7 K warmer on July's days. Among the blockers it recorded,
  the heat stored in the floor, soil and structure, the screens and the
  sky are each a node or a boundary that a one-volume model cannot have.
- **Lumped multi-node models are the field's practice.** Vanthoor's
  (2011) greenhouse climate model, as GreenLight implements and Katzin
  (2021) extends it, and TiGwerLib's, each give the air, the cover, the
  screens, the canopy, the floor and soil layers and the heating pipes a
  temperature of their own, with the sky, the outside and the deep soil
  as boundaries. GreenLight 2.0.7 already runs in the research environment
  as a reference, and solves its model with scipy's BDF.
- **The roadmap's first principle is modular fidelity:** a richer model
  sits beside the current one, chosen by the manifest, and the current
  one stays.
- **Options weighed for the solver:**
  - a general stiff solver (scipy's BDF or Radau) with event location:
    what GreenLight does, but its steps and the moments its events are
    found at depend on its tolerances and its history, which a checkpoint
    would then keep;
  - fixed small steps of an implicit method: simple, but slow where the
    cover's small heat capacity makes the system stiff, and its edges
    found only to a step;
  - the equations linearised over each stretch and solved exactly, as the
    whole house solves its linear ones today: deterministic, with no step
    history, and each edge found on an exact course.

## Decision

**A third model of the house air part.** `multi_node`, version 1, is
registered beside `grid` and `whole_house`, its parameters under the
manifest's `climate` section with `multi_node` as their `kind`. `grid`
stays the default. A manifest that does not name it runs as it ran.

**Its nodes follow the house's description** (decision 0080): the inside
air, with its temperature, water and CO₂; the air above a drawn screen,
with the same; the cover, which holds the structure's heat with its
own; each screen; the canopy (decision 0079); the
floor and its soil layers; each pipe network. Its boundaries are the
outside air, the sky, the deep soil at a fixed temperature, and each
space a wall faces. A component the house does not describe has no node.
It takes the cover's own area, its roof's slopes and not their
projection, and the volume the envelope encloses.

**Its equations are published ones,** each flux with its source in its
module: Vanthoor's (2011) as GreenLight implements them, and TiGwerLib's
where a component is its own, such as a wall on a corridor. They are
written from the publications. Code ported beyond an equation keeps its
source's notice and is named where it is used.

**The sky is the weather's.** The weather gains a sky temperature, a
downward longwave radiation and a diffuse radiation as optional
quantities, and the protocol gains them as outside observation types. A
weather that records none is given a sky estimated from its air, its
humidity and its cloud cover, by a named formula.

**Its solver:**

- over each stretch, at most the weather's minute, the equations are
  linearised about the stretch's start, the fourth powers of radiation
  and the nonlinear terms of transpiration and ventilation by their
  tangents, and solved exactly by the matrix exponential;
- a stretch is halved while the linearisation's error, the nonlinear
  rates against the linear ones at its end, exceeds a bound its
  parameters state;
- each loop's edge is found on that exact course by bracketing and
  halving, to a nanosecond, as decision 0058 has it;
- a general stiff solver at tight tolerances is its check, in the tests,
  not its method.

**The whole house decides.** The loops read `multi_node`'s inside air,
as they read the whole house's, and switch at their edges. Its air is
drawn the same in every cell, as the whole house's is.

**A run under it is a run like any other:**

- its identity covers the model's name, version and parameters, and the
  house's description;
- a checkpoint keeps every node's state, and the loops', at the two
  moments a whole house's checkpoint keeps, under the model's name and
  version, and a run restores only a checkpoint of the same;
- the same inputs give the same numbers, on the same platform and
  library versions, from the start and from a checkpoint.

**Its limit is the whole house.** With no screen, canopy, floor or pipe,
a cover with no heat capacity, the sky at the air's temperature and the
whole house's area and volume, it gives the whole house's air, which a
test holds.

**Its cost is budgeted.** Its own work stays under a second per simulated
day, and a window of the first comparison, end to end, under one and a
half times what the whole house takes, both measured on the comparison's
machine, a benchmark test holding the first.

**Each component is accepted on its reference first:** its fluxes against
GreenLight's at the same states, and a GreenLight run with it and
without; TiGwerLib's where the component is its own. Then the first
comparison runs again, stated before the run, its windows, bar and matched
inputs unchanged.

**Nothing in the packages needs Modelica.** No package imports, runs or
depends on Modelica, OpenModelica, GreenLight or TiGwerLib; they stay
references under `research/`.

## Consequences

- **The packaged scenarios do not move:** no run id, checkpoint or replay
  digest changes, since none names `multi_node` and today's models keep
  their versions.
- **The weather and the protocol change,** by optional quantities and new
  outside observation types; a recorded weather's file may give them.
- **Checkpoints gain a format** for the new model's state, the others read
  as they are.
- **The grid beside it is left:** a grid run started from its air, with
  its surfaces' temperatures as the cells' boundaries, is a model of its
  own, when one is asked for.
- **Lamps** are not among its nodes until the light targets need them.
- **Worth revisiting:**
  - if the linearised stretches miss the budget or the bound on a house
    the tests did not try, such as one under a strong sun with every
    screen open;
  - if a component's reference cannot be run on the same inputs;
  - if another platform's numbers differ enough to move a replay digest.

## Open questions

1. **The solver:** stretches linearised and solved exactly (proposed), or
   a general stiff solver with event location, as GreenLight solves.
2. **The budget's numbers:** a second per simulated day, and one and a
   half times the whole house's window (proposed).
3. **Its name:** `multi_node` (proposed), or one that names its source,
   such as `vanthoor`, which would read as Vanthoor's model unchanged.
