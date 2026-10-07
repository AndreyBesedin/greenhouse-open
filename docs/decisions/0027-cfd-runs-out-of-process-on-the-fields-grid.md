# 0027: CFD runs out of process, on the environment field's own grid

**Status:** Accepted
**Date:** 2026-10-07

## Context

P04 brings high-fidelity airflow from a CFD solver, OpenFOAM first, into the
environment field format ([0026](0026-environment-fields-are-cell-centred-grids-of-packed-floats.md)).
OpenFOAM is a large native toolchain, with no Python API, that most people
working on the simulator or its viewer will never install. Its result must
still come back as a field, and what it was given must be visible: a CFD
result is only as good as the boundaries it was solved with.

## Decision

- **The domain is the field's box, on the field's grid:** the air under the
  gutters, in cells of at most half a metre, so a solver's cells are the
  field's cells and its result maps onto a field without interpolation.
  The roof's spans above the eaves are left out, as they are from fields;
  a ceiling at the eaves stands for the roof.
- **The simulator owns the geometry it hands a solver**
  (`greenhouse_sim.cfd.geometry`): which faces bound the air, which open
  doors and vents let it through, and which fixtures stand in its way, each
  snapped to the grid as it will be meshed. What a viewer draws of it is
  exactly what the solver sees, and anything the grid is too coarse for is
  listed rather than silently dropped.
- **OpenFOAM is an adapter, run out of process:** the simulator writes a
  case and runs its scripts, natively if OpenFOAM is installed or in its
  official container through Docker otherwise. Nothing else in the
  simulator imports or needs it.
- **Its tests are opt-in:** tests that run OpenFOAM are marked `cfd`, run
  only with `pytest -m cfd`, and are skipped where it cannot run. Everything
  that can be checked without it, such as which faces and cells each
  selection chooses, is checked against the grid itself in the ordinary
  tests.

## Consequences

- Developing the simulator or the viewer never needs OpenFOAM or Docker.
  A CFD result reaches them only as a field, which they already read.
- The mesh is as coarse as the field: a fixture narrower than a cell, such
  as a crop's slabs and supports at half a metre, is not an obstacle. A
  finer or body-fitted mesh, sampled back onto the field's grid, is a later
  change to the adapter, not to the format.
- A roof vent is an opening in the flat ceiling at the eaves, not in the
  sloping roof above it. Air in the roof's spans waits for a domain that
  includes them.
- The container image is about 2 GB, pulled the first time a `cfd` test or
  `--mesh` runs without OpenFOAM installed.
