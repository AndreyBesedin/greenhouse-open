# greenhouse-sim viewer

The browser viewer for the simulator. It is an adapter around the headless
simulator core: it displays what the simulator produces, and the simulator
never depends on it. It shows a full-window 3D view (for now a reference
scene: a 1 m grid on the ground, the world axes and a 1 m cube) with a panel
listing its build and the simulator's scenarios, and a HUD.

Drag to orbit, right-drag to pan, and scroll to zoom. The HUD's buttons jump
to the top, front, side and isometric views; a refresh always returns to the
isometric one. It also shows the camera's position and where the pointer
meets the ground, both in world metres, with the frame rate and object
count. The browser renderer is
being built out in P00 of the [simulator roadmap](../../docs/roadmap/README.md).

The view uses the simulator's world axes: metres, right-handed, z up. Three.js
is y up, so `src/world.ts` converts once, at the root of the scene; nothing
else in the viewer deals with the difference.

## Scenes

The panel chooses what is drawn, and the address bar keeps the choice:
`?scene=example` is a deterministic example scene from
`public/scenes/example.json`, `?plants=lab` is the plant lab, a row of tomato plants from the
organ-level model, with the selected plant's structure as a debug tree, a
slider for the day of its run, the seed its row is drawn from, and the
environment its plants live in, with another beside it for every second plant
(`?plants=lab&day=30&seed=7&environment=cool_dim&versus=warm_bright`), and
actions on the selected organ's plant, pruning, harvesting and lowering, kept
in the address (`&act=30:p01:remove_leaf:p01_n02_leaf`) and in the plant's
history; it plays its run at a chosen speed, names its plants, and says
whether every plant keeps the structure's rules, `?scene=fixtures` is a gallery of the layout's
fixture primitives (`public/scenes/qa-fixtures.json`), one of each, drawn in
its material, `?scene=stress&plants=10000` is a dense field of
plants for measuring the renderer, `?scenario=gh_demo` is that scenario before
day one, from the simulator's API, and `?live=gh_demo` follows it live as the
API plays it one simulated day per second (`python -m greenhouse_sim.api
--seconds-per-day 0.2` plays faster). The HUD then shows the stream's state
and the simulated day; if the API goes away the viewer says so and reconnects
when it is back. Its controls play, pause, step, reset and speed up the run,
which every viewer of that scenario shares. The viewer checks every scene
against the schema the simulator publishes, and says why when it refuses one.

Click an entity to select it: it glows, the inspector shows its identifier,
transform, shape, material and properties, and debug overlays (its bounding box, its
origin and axes, and its label) can be switched on and off around it. A
selection stays on its entity as a live scenario moves on; clicking the sky
clears it. "Colour by" shades entities by a numeric property, with a legend,
"Dimensions and axis labels" measures the greenhouse and names the world's
axes, drawing its bounds as an outline, and "Categories" colours each part of
the greenhouse (floor, wall, roof, vent, door, gutter, frame) and of its
layout (planting positions, gutters, benches, slabs, walkways, service zones,
keep-out volumes, rails, pipes, obstacles) by what it is, with a legend for
each. Plants stand on their planting positions, each marked by an orange disc
around the plant's foot. The greenhouse's walls and
roof are see-through glass: a click picks the nearest solid thing along it,
such as a plant or the floor, and picks the glass only where nothing solid
lies behind. A scenario with several layouts offers them in the scenarios table: choosing
one shows the scenario with it, and the address keeps it (`&layout=benches`).

A scenario's air field, one of the environment fields the simulator publishes
for it (`greenhouse_sim/fields/`), can be drawn over its scene: "Air field"
chooses it, and the address keeps it (`?scenario=gh_001&field=vortex`). Every
scenario offers the prescribed airflow patterns, uniform, buoyancy and vortex,
its own first, and the synthetic shear the format is checked against. The
viewer checks it against the field schema the simulator publishes
(`npm run generate` writes the viewer's side of every contract), and draws it
as arrows at every cell, as long and as warm in colour as the air there is
fast; as streamlines, traced through it from seeds every few cells; or as a
slice through it, horizontal or vertical, coloured by any of its scalars or
the air's speed (`&fieldView=slice&slice=temperature:z:1.75`). A legend says
what its colours mean, and its lowest and highest colours can be moved.
"CFD boundaries" (`&cfd=boundaries`) draws what a CFD solver is given of the
scenario's air (`GET /api/scenarios/{id}/cfd/geometry`): its floor, walls
and ceiling at the eaves lightly tinted, its open doors and vents and the
fixtures in the air's way strongly, all snapped to the solver's mesh, with a
legend by category; it follows the openings' sliders.
The inspector says what the selected entity is in words, and names its
dimensions. On a scenario's view, a slider per door and vent sets how far
it stands open: the viewer asks the simulator for the scene with it so
(`?open=roof_vent_1:0.5`), and the address bar keeps it. The address can
change the greenhouse itself too (`?scenario=gh_demo&envelope=length:12,spans:3`:
length, width, spans, bays, eave_height, ridge_height); the simulator checks
it, and the viewer shows why when it refuses.
Overlays are data in world coordinates, drawn by `src/debug`
([decision 0013](../../docs/decisions/0013-describe-debug-overlays-as-data-in-world-coordinates.md)),
and they only ever read the scene.

The scene contract has one source, the simulator's types. After changing
them, regenerate both sides:

```bash
python greenhouse_sim/tests/test_scene_schema.py --update  # schema and example scene
cd greenhouse_sim/web && npm run generate                  # the viewer's types
```

Tests on both sides fail while either is stale.

## Performance

Repeated shapes are drawn in instanced batches, one per kind of entity,
shape (cylinder, sphere or ellipsoid) and finish: a field of 100,000 plants
takes four draw calls, and the plant lab's plant, organ by organ, eight. The HUD reports the frame rate and
time, draw calls and triangles, and memory.

`npm run bench` measures the stress scene at 1,000 to 100,000 plants while
orbiting, in the full Chromium on this machine's graphics card, and compares
it with the baseline in `benchmarks/stress.json`; `RECORD_BENCHMARK=1 npm run
bench` records a new one. It never fails on the numbers, and CI, which has no
graphics card, does not run it
([decision 0015](../../docs/decisions/0015-batch-repeated-shapes-and-benchmark-on-a-graphics-card.md)).
Run `npx playwright install chromium` once for it.

## Screenshots

`/qa/greenhouse?view=outside|aisle|top|section` shows the canonical QA
greenhouse (`public/scenes/qa-greenhouse.json`, written by the simulator's
`tests/test_scene_schema.py --update`) from four fixed views, which CI compares
with `e2e/visual/__screenshots__/greenhouse-<view>-linux.png` in the same way.

`/qa/plants` shows the plant lab's first plant on days 0, 30, 60 and 90, side
by side (`public/scenes/qa-plants.json`, written by the same test), which CI
compares with `e2e/visual/__screenshots__/plants-time-lapse-linux.png`: a
change to how plants develop or are drawn shows as a change of pixels.

`/qa/layout?view=top|between-rows|occluded` shows the canonical layout
(`public/scenes/qa-layout.json`, written by the same test) in the QA
greenhouse: from above, coloured by category and cut just below the eaves so
that the roof does not hide it; from a trolley riding a rail between the rows;
and from low down, looking across a row through the fixtures in the way. CI
compares them with `e2e/visual/__screenshots__/layout-<view>-linux.png`.

`/qa/renderer?seed=42` is the renderer's canonical page: a QA scene the viewer
builds from the seed, with a plant selected, every overlay drawn and the
plants coloured by height. CI's "visual checks" job compares its screenshot
with `e2e/visual/__screenshots__/renderer-seed-42-linux.png`, in a pinned
Playwright container that draws the same pixels on every run
([decision 0014](../../docs/decisions/0014-compare-screenshots-in-a-pinned-container-in-ci.md)).
Elsewhere `npm run e2e:visual` skips the comparison.

When a change to what the renderer draws is intended, the job fails and keeps
what it drew in its `visual-results` artifact. Review the baseline test's
screenshot there, then make it the baseline:

```bash
gh run download <run id> --name visual-results --dir /tmp/visual-results
cp /tmp/visual-results/renderer-the-renderer-s-QA-scene-matches-its-baseline-chromium/renderer-seed-42-actual.png \
  e2e/visual/__screenshots__/renderer-seed-42-linux.png
```

## Run it with the simulator

The viewer reads the simulator through its local API. Start the API, then the
viewer, in two terminals:

```bash
python -m greenhouse_sim.api          # http://127.0.0.1:8765/api
cd greenhouse_sim/web && npm run dev  # the viewer, which forwards /api there
```

Without the API, the page says so and how to start it.

## Develop

Node 24 (see `.nvmrc`) and npm.

```bash
cd greenhouse_sim/web
npm ci
npm run dev         # local development server
npm run lint        # Biome: formatting and lint (npm run format applies fixes)
npm run typecheck   # TypeScript, strict
npm test            # Vitest
npm run build       # production build into dist/
PYTHON=python npm run e2e  # Playwright smoke test against the real simulator API
npm run e2e:visual  # screenshot comparisons (they run in CI's container only)
npm run bench       # the renderer's benchmark, on this machine's graphics card
```

The smoke test starts the simulator's API with `$PYTHON -m greenhouse_sim.api`,
so that interpreter needs greenhouse-sim installed. Once every other browser
test has passed, `e2e/renderer-smoke.spec.ts` walks through the whole renderer
as a person would: live play, camera presets, pause, step and reset with a
deterministic replay, selection and overlays, and the stress scene. Run
`npx playwright install chromium` once to get the browser.

The page shows the simulator version, read from `../pyproject.toml` at build
time, and the commit it was built from. The viewer has no version of its own:
it ships with the simulator.

Built with React, TypeScript and Vite. The 3D scene will use Three.js through
React Three Fiber, as the roadmap's technical choices describe.
