# 0026: Environment fields are cell-centred grids, published as packed floats

**Status:** Accepted
**Date:** 2026-10-07

## Context

P04 makes the greenhouse's air visible and, later, lets plants and sensors
feel it. The air's state can come from very different sources: a prescribed
pattern, a zonal model, a learned surrogate, or a CFD solver such as
OpenFOAM, each with its own mesh. Whatever computes it, the viewer, plants
and sensors must read it the same way, and the browser must receive it
quickly: a greenhouse in half-metre cells is thousands of cells, each with a
velocity and several scalars.

## Decision

- **One format, a regular grid:** an environment field covers a box with a
  regular grid of cells, and holds each of the air's quantities
  (`domain.air.AirQuantity`) at every cell's centre. Velocity is a vector;
  temperature, humidity, CO₂ and pressure are scalars. A solver's own mesh is
  sampled onto the grid by its adapter, so nothing downstream sees it.
- **Sampling:**
  - between centres, trilinear interpolation;
  - out to the box's faces, the outermost centres' values;
  - outside the box, nothing.

  The simulator (`fields/field.py`) and the viewer (`src/fields/field.ts`)
  sample alike.
- **Order:** values run with x fastest, then y, then z, a vector's
  components fastest of all.
- **Publishing:** a `FieldDocument` writes each channel as little-endian
  32-bit floats in base64, with its unit and its range. It is versioned and
  described by `fields/field.schema.json`, from which the viewer generates
  its types, as it does for the scene.
- **Coverage, for now:** a scenario's fields cover the air under its
  gutters, from its floor up to its eaves, in cells of at most half a metre.
  The roof's spans above the eaves are left out until a solver needs them.

## Consequences

- Any source of air, at any fidelity, plugs in by producing this format,
  and the viewer, and later plants and sensors, read every source alike.
- Packed floats keep a greenhouse's field to tens of kilobytes rather than
  megabytes of JSON numbers. A field must therefore be decoded before use,
  which both sides do once, on arrival.
- A regular grid can't follow curved or fine geometry. A solver's detail
  finer than the grid's cells is averaged away when sampled. A finer grid,
  or a nested one, is a later change to the format, behind its version.
- The air under the roof's spans is not yet part of a field.
