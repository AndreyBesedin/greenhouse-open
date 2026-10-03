# 0007: World coordinates are metres, right-handed, z up

**Status:** Accepted
**Date:** 2026-10-03

## Context

The scene snapshot (P-1.6) is the first place the simulator states where
things are. From here on, greenhouse geometry (P01), fixtures and planting
positions (P02), plant organs (P03), airflow fields (P04), sensors (P06) and
sun position (P08) all exchange positions, so the convention has to be fixed
once, before anything depends on a different one.

The engines the roadmap expects to use are z-up: MuJoCo for robot physics,
Blender and BlenderProc for synthetic camera data, OpenFOAM cases, and the
robotics convention of x forward, y left, z up. The browser renderer
(Three.js) is y-up, but the viewer is an adapter around the simulator, not
part of it.

## Decision

- Positions and sizes are in metres, angles in radians: SI units throughout.
- World axes are right-handed with z up. The ground is the plane z = 0.
- Orientation is a unit quaternion with named components (`w`, `x`, `y`,
  `z`), so no consumer guesses their order.
- A shape is described in its own frame, and a `Transform` (position and
  rotation) places it in the world. Each shape states where its own origin
  is, for example an upright cylinder's base centre.
- A consumer whose axes differ, such as a y-up renderer, converts once at the
  root of its scene. Renderer concepts never enter the simulator's types.

These conventions live in `greenhouse_sim/world/geometry.py`. P01 adds the
greenhouse's own origin, axes and bounds within them.

## Consequences

- Physics, rendering and CFD backends can be connected without per-backend
  axis juggling inside the simulator.
- The browser viewer applies one fixed rotation, from z-up to its y-up, at
  its scene root.
- Changing the convention later would touch every producer and consumer of
  geometry. That cost is why it is fixed now.
