# 0016: The greenhouse has its own frame, described by its envelope

**Status:** Accepted
**Date:** 2026-10-05

## Context

Decision 0007 fixed the world's axes. P01 builds the greenhouse inside the
world: floor, walls, roof, bays and openings, and later projects place
fixtures, plants, sensors and airflow within it. Each of them is easiest to
describe from the greenhouse's own point of view ("the third bay", "two
metres along the ridge"), and a greenhouse need not stand at the world's
origin or along its axes, for example when a site holds several.

A greenhouse could also be described as meshes, but meshes cannot be
resized, say nothing about which surface is glazing and which a vent, and
cannot become an airflow boundary. The greenhouse is expected to be set up
from scenarios now, and possibly from an editor in the viewer later.

## Decision

- A greenhouse has a frame of its own: its origin is a corner of the floor,
  x runs along its length, y across its width, and z up, so the greenhouse
  fills the positive octant of its frame. Units and handedness are the
  world's (decision 0007).
- An `Envelope` describes the greenhouse: the `Transform` that places its
  frame in the world (by default the world's origin, unrotated), and its
  length, width and height. Everything the envelope describes is given in
  the greenhouse's frame; `Envelope.to_world` places it in the world.
- Every scenario declares its envelope. The envelope is the one validated
  description of the greenhouse: whoever edits it, a scenario now or an
  editor later, the geometry is generated from it, never modelled as
  meshes.
- The scene shows the space the envelope encloses as a `GREENHOUSE_BOUNDS`
  entity, a box. Its faces never take a click, so it never hides what it
  encloses from a pick.

## Consequences

- Floor, walls, roof, bays and openings (P01.2 to P01.5) are added to the
  envelope as fields, in the greenhouse's frame, and placed in the world in
  one place.
- Planting positions, fixtures and sensors (P02, P06) can be given in the
  greenhouse's frame as well.
- An editor in the viewer would change the envelope through the local API;
  the geometry needs no change for it.
- Today every scenario's greenhouse stands at the world's origin, so the
  greenhouse's frame and the world's coincide. A test places one elsewhere
  to keep the difference honest.
