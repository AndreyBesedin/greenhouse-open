# 0013: Describe debug overlays as data, in world coordinates

**Status:** Accepted
**Date:** 2026-10-04

## Context

P00 makes debug overlays a first-class part of the viewer, and later
projects (airflow, radiation, sensors and plants) need to show their own:
arrows for a flow, boxes around a sensor's volume, labels and scalar
colours. If each of them draws with Three.js directly, every project
learns the viewer's axes conversion and lifetime rules again, and nothing
outside the viewer can describe an overlay.

React Three Fiber's companion library, drei, offers ready-made helpers such
as text and page-element labels. It is a large dependency, pulling in its own
dependencies, for the five primitives P00 needs, and the viewer has so far
added only what it uses.

## Decision

- An overlay is data: a list of `OverlayPrimitive` values (point, arrow, box,
  line and label) in world coordinates, metres with z up, each with an
  identifier unique in its list. One component, `Overlays`, draws any such
  list inside the world's z-up group.
- Code that explains something produces primitives from what it reads and
  never changes it. The selection's overlays come from `selectionOverlays`,
  which reads the selected entity. A later project adds its own function,
  not its own drawing code.
- Overlays are drawn outside the part of the scene that takes clicks, so
  they never decide what a click selects.
- Labels are page elements placed over the view at their projected point,
  so they stay crisp and can be found by their text in browser tests.
- A scalar is shown by shading entities with a fixed colour scale
  (viridis), with a legend that names the property and its range.
- The viewer draws these itself with Three.js; drei is not added.

## Consequences

- A project's overlay is a pure function from its data to primitives,
  tested without a browser.
- Since primitives are plain data, the simulator could send overlays with a
  scene later, without new drawing code.
- New kinds of primitive, such as a vector field drawn as many arrows, are
  added to the type and to `Overlays` once, for every project.
- If the viewer comes to need much of what drei offers, such as text in the
  3D scene or instanced helpers, adding it is worth reconsidering.
