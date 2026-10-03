# P00: Browser renderer and visual QA foundation

**Status:** in progress. Part of the [simulator roadmap](README.md).

## Goal

Build the permanent visualization shell in the browser, so that every later
simulator feature can be inspected there without one-off plotting code.

## Direction

- React, TypeScript and Three.js through React Three Fiber, on WebGL first.
  Renderer-specific code stays isolated, so WebGPU can be adopted later
  without changing the simulation contracts.
- The browser shows the simulation and lets people interact with it. The
  simulation's truth stays in the Python process.
- Scenes are deterministic, selected by scenario and seed.
- SI units and the world axes of
  [decision 0007](../decisions/0007-world-coordinates-metres-right-handed-z-up.md).
  The viewer converts to Three.js's axes once, at the root of its scene.
- Debug overlays are first-class features.
- Visual regression tests are in place before scene complexity grows.

## Starting point

P-1 already provides the scene snapshot types (P-1.6), the local API with the
scenario list and each scenario's initial scene (P-1.8), and the viewer
package with its CI and browser smoke test (P-1.7, P-1.9). P00 builds the
renderer on them.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P00.1 | `chore(web): scaffold the browser simulation viewer` | Done ([#19](https://github.com/AndreyBesedin/greenhouse-open/pull/19)) |
| P00.2 | `feat(viewer): add orbit camera, presets and scene HUD` | Planned |
| P00.3 | `feat(scene): render typed scene entities from JSON` | Planned |
| P00.4 | `feat(sim-bridge): stream scene snapshots from the local Python process` | Planned |
| P00.5 | `feat(time): add play, pause, step, speed and reset controls` | Planned |
| P00.6 | `feat(debug): add selection, an inspector and overlay primitives` | Planned |
| P00.7 | `test(visual): add a deterministic screenshot regression harness` | Planned |
| P00.8 | `perf(viewer): add an instancing stress scene and diagnostics` | Planned |

### P00.1: Scaffold the 3D viewer

A full-window 3D view showing a ground grid, the world axes and a 1 m
reference cube, with the development command documented. Tests: the viewer
boots from a clean install, logs no console errors, and resizes with the
window.

As implemented:

- React Three Fiber 9 on Three.js 0.186. The canvas fills the window, and the
  build and scenario information floats over it as a panel.
- The reference scene is a 20 m ground grid with 1 m cells, 2 m world axes,
  and a 1 m cube standing on the grid cell from (1, 1) to (2, 2) m, clear of
  the axes.
- `src/world.ts` is the single conversion from the world's z-up axes to
  Three.js's y-up axes. Its tests pin that world up becomes screen up and
  that the axes stay right-handed.
- The browser smoke tests check that the scenarios are listed, that the 3D
  view fills the window and follows it when resized, and that nothing logs an
  error. WebGL works in headless Chromium.
- Three.js makes the bundle about 1 MB, which is acceptable for a local
  development tool.

### P00.2: Orbit camera, presets and HUD

Orbit, pan and zoom; top, front, side and isometric camera presets; a
world-coordinate readout; and a HUD with camera position, frame rate and
object count. Visible result: the reference scene can be inspected
predictably from predefined viewpoints. Tests: each preset moves the camera
to its expected pose, and a refresh restores the default view.

### P00.3: Render typed scene entities

Render the scene snapshot from P-1.6 through a registry keyed by entity
kind, publish the snapshot's JSON Schema as a file the viewer's types are
generated from, and add a deterministic example scene. Visible result: a JSON
scene of differently sized and placed objects renders without scene-specific
code. Tests: schema validation, an unknown kind fails visibly, and entity
transforms match the fixture.

### P00.4: Stream scene snapshots from Python

A streaming channel from the local API (WebSocket or equivalent). This is
the point where, per
[decision 0009](../decisions/0009-a-standard-library-local-api-until-streaming-is-needed.md),
a web framework replaces the standard-library server, as an optional
dependency of the API. The viewer shows the simulation timestamp, and one test
entity moves because Python advances it. Tests: stopping the API shows a
disconnected state, restarting it reconnects, and the known timestamp appears
in the HUD.

### P00.5: Time controls

Play, pause, single step, speed and reset, with deterministic restart.
Visible result: the moving entity can be paused, stepped, sped up and reset.
Tests: a reset with the same seed returns to an identical state, and a single
step advances exactly one tick.

### P00.6: Selection, inspector and overlays

Click to select, highlight the selection, and inspect its properties. Debug
primitives: point, vector arrow, bounding box, line, label and scalar legend.
Visible result: selecting an entity shows its identifier and transform, and
arrows, boxes and labels can be toggled around it. Tests: selection is
stable, and toggling overlays never changes world state.

### P00.7: Screenshot regression

Playwright visual tests on a canonical route such as `/qa/renderer?seed=42`,
with a fixed viewport and camera, golden screenshots and a documented
tolerance. Tests: an intentional scene change produces a difference, and the
restored scene passes.

### P00.8: Instancing and diagnostics

An instanced rendering path, a stress scene with thousands of repeated
objects, and frame-time, draw-call and memory diagnostics where available.
Visible result: a dense, greenhouse-like grid stays navigable. Tests: a
baseline performance measurement, kept as a non-blocking benchmark.

## Final QA: `renderer-smoke`

On one deterministic route, check camera presets, selection, live movement
driven by Python, pause, step and reset, overlay arrows and bounding boxes,
deterministic replay, the screenshot baseline, and stress-scene
interactivity.

## Acceptance criteria

- [ ] The renderer runs entirely in the browser.
- [ ] Python drives scene state without any rendering responsibility.
- [ ] A deterministic scene is visually regression-tested.
- [ ] Debug overlays are reusable by airflow, radiation, sensors and plants.
- [ ] Later projects do not need another visualization stack.
