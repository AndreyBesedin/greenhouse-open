# 0019: Fixtures say what they are made of, and what they obstruct

**Status:** Accepted
**Date:** 2026-10-06

## Context

P02 fills the greenhouse with fixed objects: crop gutters and benches,
walkways, rails, pipes, wires and other obstacles. Robots (navigation),
airflow (P04) and radiation (P08) will each treat some of them as obstacles,
and not the same ones: a pipe rail stops a trolley crossing it but barely
slows the air; a walkway obstructs nothing, but light lands on it. The
viewer, meanwhile, has to draw each in a way that says what it is.

## Decision

- The greenhouse's layout is a description in the greenhouse's frame
  (`greenhouse_sim.world.layout`), like its envelope (decision 0016), and
  its fixtures are generated from it (`greenhouse_sim.world.fixtures`). A
  scenario holds it, and refuses a layout that reaches outside its
  greenhouse.
- A fixture is one solid with a stable identifier, a kind (what it is), a
  material, and the set of things it obstructs: movement, airflow and light.
  Each kind brings a default material and set of obstructions; a
  description can choose its own.
- Consumers select obstacles by what they obstruct, not by kind, so a new
  kind of fixture needs no change to them.
- Fixtures are built from a small set of primitives: a box, an upright
  cylinder, a pipe between two points, a rail of two tubes, an open tray
  along a line, and a walkway on the floor. Each is drawn with the world's
  existing shapes, so repeated cylinders (pipes, rails) join the instanced
  batches of decision 0015.
- The scene shows each fixture as an entity of its kind's scene kind, in its
  material's colour, with what it obstructs as properties. Scene entities
  gain an optional material, which the viewer uses to draw metal as metal;
  the envelope's frames and gutters state theirs too.

## Consequences

- P04 and P08 build their obstacle sets from the layout's fixtures and their
  obstructions, without a list of kinds to keep in step.
- The envelope's glazing has no material yet. P08 gives glazing its optical
  properties, and can add glazing materials then.
- A tray is drawn as a box, its open top not modelled. A shape with walls can
  come later, behind the same primitive, if a consumer needs it.
