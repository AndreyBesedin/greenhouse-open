# 0015: Batch repeated shapes, and benchmark the renderer on a graphics card

**Status:** Accepted
**Date:** 2026-10-05

## Context

A greenhouse repeats the same shapes by the thousand: stems now, and later
leaves, fruit, posts and sensors. Drawn one mesh per entity, a field of
10,000 plants costs 10,000 draw calls, and the browser spends its time
issuing them rather than drawing.

Measuring the renderer needs a graphics card. Playwright's default
headless browser draws in software (SwiftShader), as CI does: there a field
of 10,000 plants runs at about 4 frames per second, on any renderer design.
The full Chromium in its headless mode draws on the machine's graphics
card. CI runners have none.

## Decision

- Repeated shapes are drawn in instanced batches: every cylinder in a
  scene is one instance of one mesh, placed by a matrix built from the
  entity's transform, radius and height (`cylinderMatrices`). New repeated
  shapes join the same way.
- A batch lists its entities in instance order, so a click on an instance
  selects its entity. A selected entity leaves the batch and is drawn on
  its own, so it can glow.
- The HUD reports the frame time, draw calls, triangles, what the renderer
  holds in GPU memory, and the JavaScript heap where the browser reports it.
- The renderer's performance is measured by a local benchmark (`npm run
  bench`): the stress scene at 1,000 to 100,000 plants, while orbiting, in
  the full Chromium on the graphics card, with the frame rate not tied to
  the display. Its baseline is recorded in `benchmarks/stress.json` with
  the machine and renderer it ran on. It is a record, not a gate: it never
  fails on the numbers, and CI does not run it.
- CI checks what does not depend on the graphics card: a stress scene of
  2,000 plants takes single-figure draw calls, and its plants can be picked.

## Consequences

- Draw calls stay flat as a scene grows: four for the ground, the axes, the
  grid and every plant, at 100 or 100,000 plants.
- A regression in speed is seen when someone runs the benchmark and
  compares, not automatically. A baseline from another machine is a
  different record, not a comparison.
- Per-instance looks are limited to what the batch carries, a colour today.
  A look that cannot be batched, such as the selection's glow, takes the
  entity out of the batch.
