# P00: Browser renderer and visual QA foundation

**Status:** done. Part of the [simulator roadmap](README.md).

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
| P00.2 | `feat(viewer): add orbit camera, presets and scene HUD` | Done ([#20](https://github.com/AndreyBesedin/greenhouse-open/pull/20)) |
| P00.3 | `feat(scene): render typed scene entities from JSON` | Done ([#21](https://github.com/AndreyBesedin/greenhouse-open/pull/21)) |
| P00.4 | `feat(sim-bridge): stream scene snapshots from the local Python process` | Done ([#22](https://github.com/AndreyBesedin/greenhouse-open/pull/22)) |
| P00.5 | `feat(time): add play, pause, step, speed and reset controls` | Done ([#23](https://github.com/AndreyBesedin/greenhouse-open/pull/23)) |
| P00.6 | `feat(debug): add selection, an inspector and overlay primitives` | Done ([#24](https://github.com/AndreyBesedin/greenhouse-open/pull/24)) |
| P00.7 | `test(visual): add a deterministic screenshot regression harness` | Done ([#25](https://github.com/AndreyBesedin/greenhouse-open/pull/25)) |
| P00.8 | `perf(viewer): add an instancing stress scene and diagnostics` | Done ([#26](https://github.com/AndreyBesedin/greenhouse-open/pull/26)) |

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

As implemented:

- Orbit, pan and zoom use the orbit controls that ship with Three.js, so no
  dependency is added.
- The presets look at the world origin from 9 m. They are plain data in
  world coordinates (`src/camera.ts`), shared by the viewer and its tests.
  The isometric view is the default, and the top view leans a millimetre
  towards -y so world +y stays up the screen.
- The HUD shows the camera position in world coordinates, where the pointer
  meets the ground, the frame rate and the scene's object count. A probe in
  the canvas samples them four times a second, so the page does not
  re-render on every frame.
- Browser tests check that each preset puts the camera at its pose, that
  dragging orbits and a refresh restores the default view, and that the HUD
  reports its readouts. Screenshots confirmed the top view shows +x to the
  right and +y up the screen.

### P00.3: Render typed scene entities

Render the scene snapshot from P-1.6 through a registry keyed by entity
kind, publish the snapshot's JSON Schema as a file the viewer's types are
generated from, and add a deterministic example scene. Visible result: a JSON
scene of differently sized and placed objects renders without scene-specific
code. Tests: schema validation, an unknown kind fails visibly, and entity
transforms match the fixture.

As implemented:

- The simulator publishes `greenhouse_sim/scene/snapshot.schema.json`. It is
  plain JSON Schema 2020-12, without Pydantic's OpenAPI `discriminator`
  keyword, and it describes snapshots as the simulator sends them, so every
  field it always writes is required. It sits next to a deterministic example
  scene, gh_demo on day 9, in `web/public/scenes/`. Python tests fail if
  either drifts from the types.
- `npm run generate` turns the schema into the viewer's TypeScript types and
  a schema module, and a Vitest test fails if those are stale. The viewer
  checks every scene with Ajv in strict mode before drawing it, and lists the
  problems with their paths when it refuses one.
- A registry typed by the published kinds draws each entity, inside the
  world's z-up group. A new kind does not compile until it has a renderer.
- `?scene=example` or `?scenario=<id>` chooses the scene, and a refresh keeps
  it. Browser tests draw the example and gh_001's 40 plants from the API, and
  show an entity of an unknown kind being refused visibly.

### P00.4: Stream scene snapshots from Python

A streaming channel from the local API (WebSocket or equivalent). This is
the point where, per
[decision 0009](../decisions/0009-a-standard-library-local-api-until-streaming-is-needed.md),
a web framework replaces the standard-library server, as an optional
dependency of the API. The viewer shows the simulation timestamp, and one test
entity moves because Python advances it. Tests: stopping the API shows a
disconnected state, restarting it reconnects, and the known timestamp appears
in the HUD.

As implemented (see [decision 0012](../decisions/0012-stream-to-the-viewer-with-server-sent-events.md),
which replaces the framework plan above):

- `GET /api/scenarios/{id}/live` streams Server-Sent Events from the existing
  standard-library server, so the API still adds no dependency. A shared
  `LiveRun` steps the scenario through the engine one simulated day per
  second (`--seconds-per-day`), and each `frame` event carries a sequence
  number, the simulated day and instant, and the scene. After the last day the
  run starts over, and a given day always looks the same.
- Rather than a test cube, a real scenario moves: the crop grows as Python
  advances it.
- `?live=<id>`, or a scenario's Live button, follows the stream. Each frame is
  checked like any other scene, and the HUD shows the stream's state and the
  simulated day and instant. A lost stream shows "disconnected,
  reconnecting…" with the last frame kept on screen, and the viewer
  reconnects by itself, also after the error response a proxy gives while
  the API is down.
- Browser tests watch the day advance and the stream recover after its
  requests are blocked. Stopping and restarting the real API was checked by
  hand: the viewer showed the disconnection, then went live again without a
  reload.

### P00.5: Time controls

Play, pause, single step, speed and reset, with deterministic restart.
Visible result: the moving entity can be paused, stepped, sped up and reset.
Tests: a reset with the same seed returns to an identical state, and a single
step advances exactly one tick.

As implemented, the controls act on a scenario's live run from P00.4, and a
tick is one simulated day:

- As [decision 0012](../decisions/0012-stream-to-the-viewer-with-server-sent-events.md)
  planned, commands are POST requests:
  `/api/scenarios/{id}/live/{play,pause,step,reset}` and
  `/api/scenarios/{id}/live/speed?multiplier=2`. Speeds run from a quarter
  of the server's pace to eight times it (`SPEEDS` in `api/live.py`). An
  unknown scenario or command is refused with a 404, and a speed outside
  that list with a 400.
- A run is shared, so a command changes it for every viewer. Each command
  publishes a new frame, which now also says whether the run is playing and
  at what speed, and the viewer's controls follow those frames.
- Step works whether the run is playing or paused; the viewer offers it
  while paused. Reset rebuilds the world from the scenario's seed, back to
  before day one, and keeps the run playing or paused as it was.
- The HUD has Play or Pause, Step, Reset and a speed selector. They are
  disabled until a frame arrives and while the stream is lost. When the
  simulator refuses a command, the HUD says why.
- Tests:
  - Python: a reset matches a fresh run, and the days after it repeat
    exactly. A step advances exactly one day. A paused run publishes nothing.
    A faster run moves on sooner. Each command answers over HTTP.
  - Browser: one test pauses `gh_002`, resets it, holds day 0, steps to
    days 1 and 2, then plays on. Another checks that the simulator accepts
    every speed the viewer offers.

### P00.6: Selection, inspector and overlays

Click to select, highlight the selection, and inspect its properties. Debug
primitives: point, vector arrow, bounding box, line, label and scalar legend.
Visible result: selecting an entity shows its identifier and transform, and
arrows, boxes and labels can be toggled around it. Tests: selection is
stable, and toggling overlays never changes world state.

As implemented (see [decision 0013](../decisions/0013-describe-debug-overlays-as-data-in-world-coordinates.md)):

- A click selects the nearest entity under the pointer. A drag orbits the
  camera and selects nothing, and clicking the sky clears the selection.
  The selection is kept by the entity's identifier, so it follows the entity
  from one live frame to the next.
- The selected entity glows in the selection colour. The inspector shows its
  identifier, kind, label, position, rotation, shape and properties.
- The debug primitives are point, arrow, box, line and label. They are data
  in world coordinates, drawn by one component. Around the selection they
  show its bounding box, its origin and its own axes (turned as the entity
  is), and its label on a leader line. Each of the three can be switched off.
- The scalar legend comes with "Colour by", which shades entities by any
  numeric property on a viridis scale. The legend names the property and its
  range in the scene.
- Tests:
  - Unit: picking takes the nearest entity hit. A selection follows its
    entity into the next scene. Bounding boxes follow rotation. Each overlay
    appears only when switched on. Colours run from the scale's ends and
    blend in between. The scene, deep-frozen, comes out unchanged after
    every combination of overlays and every colouring.
  - Browser: clicking a plant shows its identifier and transform, a drag
    keeps the selection, the ground and the sky select as expected. A
    selection stays on a live plant while its age changes. On a paused run,
    switching every overlay and colouring sends no request to the simulator
    and leaves the day and the scene unchanged.

### P00.7: Screenshot regression

Playwright visual tests on a canonical route such as `/qa/renderer?seed=42`,
with a fixed viewport and camera, golden screenshots and a documented
tolerance. Tests: an intentional scene change produces a difference, and the
restored scene passes.

As implemented (see [decision 0014](../decisions/0014-compare-screenshots-in-a-pinned-container-in-ci.md)):

- `/qa/renderer?seed=42` shows a QA scene the viewer builds from the seed:
  the ground, the axes and fifteen leaning plants of seeded heights. It is
  drawn from the default camera in a 1280 by 720 view, with one plant
  selected, every overlay drawn and the plants coloured by height. The
  simulator plays no part, so the screenshot changes only when the renderer
  does.
- CI's "visual checks" job compares it in a pinned Playwright container,
  which draws the same pixels on every run. A pixel differs when its colour
  moves by more than 0.2, and the screenshot fails when more than 100
  pixels differ. Moving one stem by its own width changes about 200 pixels.
- Comparisons never overwrite the baseline. A failed comparison keeps what
  it drew as an artifact, from which an intended change, or the first
  baseline, takes its new baseline.
- Tests: the QA scene matches its baseline. Seed 43 fails against it, and
  seed 42 then passes again. Unit tests check that the scene passes the
  scene check and is the same for a seed. A browser test checks the page
  everywhere, while the screenshot comparisons run only in the container.

### P00.8: Instancing and diagnostics

An instanced rendering path, a stress scene with thousands of repeated
objects, and frame-time, draw-call and memory diagnostics where available.
Visible result: a dense, greenhouse-like grid stays navigable. Tests: a
baseline performance measurement, kept as a non-blocking benchmark.

As implemented (see [decision 0015](../decisions/0015-batch-repeated-shapes-and-benchmark-on-a-graphics-card.md)):

- Every cylinder is drawn as one instance of a single mesh, placed by a
  matrix from its transform, radius and height, and coloured per instance.
  A click on an instance selects its entity; a selected plant is drawn on
  its own so it can glow.
- `?scene=stress&plants=10000` (the panel's Stress scene button) is a field
  of double rows of plants, built in the viewer, of up to 100,000 plants.
- The HUD reports the frame time (mean and worst), draw calls and
  triangles, what the renderer holds in GPU memory, and the JavaScript heap
  where the browser reports it.
- `npm run bench` measures the field at 1,000 to 100,000 plants while
  orbiting, on the graphics card, and compares with the baseline in
  `greenhouse_sim/web/benchmarks/stress.json`. It never fails on the numbers,
  and CI, which has no graphics card, does not run it. On the development
  machine (Apple M2, Chromium 153), the frame rate not tied to the display:

  | Plants | Frame rate | Frame time | Draw calls | Triangles |
  | ---: | ---: | ---: | ---: | ---: |
  | 1,000 | 572 fps | 1.7 ms | 4 | 96,002 |
  | 10,000 | 570 fps | 1.8 ms | 4 | 960,002 |
  | 50,000 | 302 fps | 3.3 ms | 4 | 4,800,002 |
  | 100,000 | 153 fps | 6.5 ms | 4 | 9,600,002 |

- Tests: unit tests place, turn and scale instances, pick an instance's
  entity, and check the stress scene's layout and address. A browser test,
  in CI's software renderer, draws 2,000 plants in single-figure draw
  calls and picks one of them.

## Final QA: `renderer-smoke`

On one deterministic route, check camera presets, selection, live movement
driven by Python, pause, step and reset, overlay arrows and bounding boxes,
deterministic replay, the screenshot baseline, and stress-scene
interactivity.

As implemented ([#27](https://github.com/AndreyBesedin/greenhouse-open/pull/27)),
`e2e/renderer-smoke.spec.ts` walks through the renderer as a person would,
starting from `/?live=gh_002`:

1. The live scenario moves on, day by day, as Python advances it.
2. Each camera preset moves the camera to its pose.
3. Pause holds the day, reset returns to day 0, and step moves one day.
4. A plant is selected, and the inspector shows its position.
5. Its bounding box and its origin and axes are drawn: switching each off
   removes objects from the scene, and switching them back restores the
   count. Its label is shown.
6. A reset, followed by the same steps, shows the plant's properties exactly
   as before: the replay is deterministic.
7. Playing again, Python moves it on.
8. The screenshot baseline's page, `/qa/renderer?seed=42`, draws its seeded
   scene. Its screenshot is compared in CI's visual checks job (P00.7).
9. The stress scene of 10,000 plants keeps single-figure draw calls, orbits
   when dragged, and lets a plant be picked.

It runs with the other browser tests in CI, as a Playwright project of its
own that starts once they have passed, since it drives a shared live run.
A reset that keeps the grown world, planted on purpose, fails it at step 6.
Frame rates on a graphics card are recorded by the benchmark (P00.8).

## Acceptance criteria

- [x] The renderer runs entirely in the browser: React, Three.js and React
  Three Fiber in `greenhouse_sim/web` (P00.1, decision
  [0008](../decisions/0008-build-the-viewer-with-npm-node-24-and-vite.md)).
- [x] Python drives scene state without any rendering responsibility: the
  simulator sends scene snapshots, which are data with no renderer in them,
  and streams them live (P00.3, P00.4, decision
  [0012](../decisions/0012-stream-to-the-viewer-with-server-sent-events.md)).
- [x] A deterministic scene is visually regression-tested: the seeded QA
  page, in CI's pinned container (P00.7, decision
  [0014](../decisions/0014-compare-screenshots-in-a-pinned-container-in-ci.md)).
- [x] Debug overlays are reusable by airflow, radiation, sensors and plants:
  they are data in world coordinates, which any project can produce (P00.6,
  decision
  [0013](../decisions/0013-describe-debug-overlays-as-data-in-world-coordinates.md)).
- [x] Later projects do not need another visualization stack: a new kind of
  entity is a schema change and a renderer entry, repeated shapes are
  batched (decision
  [0015](../decisions/0015-batch-repeated-shapes-and-benchmark-on-a-graphics-card.md)),
  and overlays, selection, time controls and screenshots come with the
  viewer. P01 onwards build on it.
