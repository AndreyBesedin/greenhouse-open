# greenhouse-sim viewer

The browser viewer for the simulator. It is an adapter around the headless
simulator core: it displays what the simulator produces, and the simulator
never depends on it. It shows a full-window 3D view, with panels for the
scenario, its run and what the simulator measures, and a HUD. It opens on a
reference scene, a 1 m grid on the ground, the world axes and a 1 m cube;
the panel chooses what else it draws (see Scenes below), and
`uv run demo`, from the repository's root, opens it on the reference
greenhouse.

Drag to orbit, right-drag to pan, and scroll to zoom. The HUD's buttons jump
to the top, front, side and isometric views; a refresh always returns to the
isometric one. It also shows the camera's position and where the pointer
meets the ground, both in world metres, with the frame rate and object
count. What it draws was built project by project, as the
[simulator roadmap](../../docs/roadmap/README.md) records.

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
plants for measuring the renderer, `?scenario=climate_box` is that scenario before
day one, from the simulator's API, and `?live=climate_box` follows it live as the
API plays it one simulated day per second (`uv run api --seconds-per-day
0.2` plays faster). The HUD then shows the stream's state
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
chooses it, and the address keeps it (`?scenario=tomato_compartment&field=buoyancy`). Every
scenario offers the prescribed airflow patterns, uniform, buoyancy and vortex,
its own first, and the synthetic shear the format is checked against. The
viewer checks it against the field schema the simulator publishes
(`npm run generate` writes the viewer's side of every contract), and draws it
as arrows at every cell, as long and as warm in colour as the air there is
fast; as streamlines, traced through it from seeds every few cells; or as a
slice through it, horizontal or vertical, coloured by any of its scalars or
the air's speed (`&fieldView=slice&slice=temperature:z:1.75`). A legend says
what its colours mean, and its lowest and highest colours can be moved.
A scenario's `cfd` field is its air as OpenFOAM solved it, with the layout
shown: `?scenario=airflow_box&field=cfd&fieldView=streamlines` is the
airflow QA case, air blown past a block, and `&layout=open` the same house
without it. A scenario with equipment offers its `climate` too: its own air
with its equipment running at the levels the Equipment panel sets, reloaded
as they change (`?scenario=climate_box&field=climate&set=fan:1`, its fan's
jet blowing down the house). A fan carries an arrow the way it blows. The
climate is its air through a climate run, as many days long as its
scenario: "Climate run" moves through a day a minute at a time, and through
the run a day at a time, or plays it, a minute at a time through its first
hour and five minutes at a time after it, or at the pace chosen, an hour or
a day a step (`&t=600`, ten minutes in; `&t=18000`, five hours;
`&t=87000`, the second day, ten minutes in, `day 1, 10 min`). A day ends at
its midnight, `24 h 00 min`, and the next begins a minute after it. "House
air" charts the house's air as one volume through the moment's day
(`GET /api/scenarios/{id}/climate/house`), as the weather's and a sensor's
charts do, its
colours keeping the widest range its moments have reached, and a
temperature slice shows a heater warming its corner and the house
(`&set=heater:1&fieldView=slice&slice=temperature:z:0.75`), and a humidity
slice a dehumidifier drying the air around it
(`&set=dehumidifier:1&fieldView=slice&slice=humidity:z:0.75`). The climate
follows the Openings sliders too: an open door or vent passes what the wind
and the stack drive through it (`GET /api/scenarios/{id}/climate/openings`),
marked by an arrow in or out, and shows its draught. A run can switch its equipment on
its own (`&schedule=60:fan:1,300:heater:0`, seconds:actuator:level), or
every day at a time of day (`&daily=64800:heater:1,79200:heater:0`, the
heater on every evening from 18 h to 22 h), and
equipment switched while the run stands past its start is an override from
that moment, which a daily command at the same moment gives way to. A
scenario may have daily commands of its own, as the reference greenhouse
heats, vents and stirs its house by the clock (P09.4): a run gives them
unless its address gives its own, and `&daily=none` gives none; the address
keeps a change to them, not a copy.
"Schedule", under the time sliders, is folded at first to how many commands
it has and the next to come (`Schedule: 21 commands. Next at 23 h 00 min:
heater 80%.`), over a bar across the moment's day with its commands marked,
a daily one's square; opened, it lists them, each to go to or take out,
and a command for one moment to repeat every day (↻); the Equipment panel and the
scene show the levels at the moment drawn, and a door or vent a command
opens stands as far open. "Timeline", opened on demand,
draws a lane per process (its commands, its air, its plants, its sensors
and its cameras) with each event a tick across the window the moment lies
in, a day, an hour, ten minutes or a minute wide, and lists what each
process does at the moment, in the order they take their turns
(`GET /api/scenarios/{id}/timeline`). "Checkpoints", opened on demand,
saves the run's state at the start of the moment's day
(`POST /api/scenarios/{id}/checkpoints`), lists those the API keeps for the
scenario, restores one, its run at its moment, and downloads one as JSON or
uploads one again (`GET /api/checkpoints/{id}`, `POST /api/checkpoints`);
the API keeps them in its memory, and a restored run given other commands
from its moment on is a branch from it, sharing every day before.
"Compare" against one charts its run, carried on unchanged, beside the run
drawn: the house's air, a temperature sensor's readings and a plant's days.
A scenario whose manifest names an opening day, as the reference greenhouse
names its first day with red fruit, opens there when shown from the list,
at noon, from the checkpoint the API keeps of it. With probes placed, "Probe
charts" draws each probe's temperature, relative humidity and air speed
through the run up to the moment drawn, beside the same run with all its
equipment off, in plain SVG (`GET /api/scenarios/{id}/climate/probes`).
`/qa/airflow-box?view=vectors` and `?view=slice` draw the airflow QA case's
solution from the simulator's files (`tests/test_airflow_qa.py --update`),
for its screenshot tests; switching a scenario's layout keeps its field, probes
and comparison, so that its air can be compared with and without a fixture.
Probes read the drawn field at points in it (`&probes=3:3.2:0.75`): "Add a
probe", or check "place by clicking" and click the view to place one above
the ground there. "Compare with" reads another of the scenario's fields at
the same points, and says how the drawn one differs
(`?scenario=airflow_box&field=cfd&compare=uniform`).
"CFD boundaries" (`&cfd=boundaries`) draws what a CFD solver is given of the
scenario's air (`GET /api/scenarios/{id}/cfd/geometry`): its floor, walls
and ceiling at the eaves lightly tinted, its open doors and vents and the
fixtures in the air's way strongly, all snapped to the solver's mesh, with a
legend by category; it follows the openings' sliders.
"Weather" shows a scenario's weather outside at the moment drawn
(`GET /api/scenarios/{id}/weather?t=600`): when that is at its site, the
air's temperature, humidity and CO₂, the wind, with a compass needle along
the way it blows, the pressure, and the site. A wind is drawn as an arrow
outside the house, a metre long for each metre a second
(`?scenario=tomato_compartment`). Opened, it runs the scenario under a
synthetic day in place of its own weather
(`?scenario=climate_box&weather=cold_spring_day`), and charts that day's
temperature, humidity and wind (`GET /api/scenarios/{id}/weather/day`).
For QA, its sliders override the sky's cloud cover (`&clouds=80`) and the
wind's direction, the bearing it blows from (`&wind=90`), keeping the rest of
the weather its own; the API takes them in the weather's name
(`weather=default@80~90`).
"QA mode", in the display options (`&qa=1`, kept through every change of
view), shows what the simulator knows and a policy never sees, and only it
asks for truth (`GET /api/scenarios/{id}/climate/truth`): a selected
sensor's truth beside its readings, with a switch to read it as a clean
sensor would; every plant in a scenario labelled with its identifier, and
its day's light in a climate run; each probe's value of the quantity drawn
beside its name; and a panel of its own: "Developer", what each process
of the run holds at the moment drawn, the clock, the house's air, the
crop's last day, every level and the latest commands, each sensor's
freshness and each camera's frames (`GET /api/scenarios/{id}/climate/state`);
and "Run manifest", its version, seed, season and models
(`GET /api/scenarios/{id}/manifest`), and the simulator's and the viewer's
versions and commits, warning when both are known and differ
(`GET /api/version`). Out of it, a selected sensor shows its readings
alone.
The inspector says what the selected entity is in words, and names its
dimensions. In a climate run's view, a selected plant, or any part of one,
shows its light: its PAR at the moment drawn and its day's light integral
(`GET /api/scenarios/{id}/climate/plants`). The reference greenhouse grows
its crop organ by organ (P09.3): once a day of its run has ended, its scene
draws the crop as it stands at the moment drawn
(`GET /api/scenarios/{id}/crop`), and a selected part of a plant shows the
plant's days, the house's air and its own light on each day it lived,
charted day by day, what was picked from it, and its structure
(`GET /api/scenarios/{id}/crop/{plant}`). On a scenario's view, a slider per door and vent sets how far
it stands open: the viewer asks the simulator for the scene with it so
(`?open=roof_vent_1:0.5`), and the address bar keeps it. Its climate
equipment gets a switch and a slider each, the same way: a fan, heater or
dehumidifier runs at the level set (`?set=heater:0.5`), drawn grey while it
is off and in its kind's colour while it runs, and the panel says what that
level gives (`50%, 5 kW`). While a climate run stands past its start, both
give a command at that moment instead (`&schedule=600:roof_vent_1:1`), so
that the run stays the same house, carried on rather than worked out again
from its start. The address can
change the greenhouse itself too (`?scenario=climate_box&envelope=length:16,bays:4`:
length, width, spans, bays, eave_height, ridge_height); the simulator checks
it, and the viewer shows why when it refuses. It can also place the camera,
for a part of a big greenhouse no preset frames
(`?scenario=tomato_compartment&camera=26:6:8,23.3:6:1`, its position, then the
point it looks at).
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
time, draw calls and triangles, and memory, and how long the simulator took
to answer the latest request, as its API says in a `Server-Timing` header.

`npm run bench` measures the stress scene at 1,000 to 100,000 plants while
orbiting, in the full Chromium on this machine's graphics card, and compares
it with the baseline in `benchmarks/stress.json`; and the reference
greenhouse at the end of its season, its crop at its fullest and its climate
drawn, with how long the simulator took to give each part of it, against
`benchmarks/reference.json`, starting its own API (`PYTHON` names its
interpreter) and waiting minutes for the season's last days.
`RECORD_BENCHMARK=1 npm run bench` records new baselines. It never fails on
the numbers, and CI, which has no graphics card, does not run it
([decision 0015](../../docs/decisions/0015-batch-repeated-shapes-and-benchmark-on-a-graphics-card.md)).
`uv run setup` installs the Chromium it runs in.

## The demo

`e2e/demo.spec.ts` walks through P09's final QA on the reference greenhouse
(`docs/demo.md`), step by step, as a browser test. `uv run record-demo`,
from the repository's root (`npm run demo:record` here, with `PYTHON` naming
the simulator's interpreter), plays it on this machine's graphics card with
a caption on each step, lingering on each (`DEMO_PAUSE_MS`), and records it
as video under `test-results/demo/`.

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

`/qa/reference-greenhouse?view=…` shows P09's golden views of the reference
greenhouse, from its run's opening day, day 80, and a young crop's, day 21
(`public/scenes/qa-reference-greenhouse.json.gz`, gzipped, written by the
simulator's `tests/test_reference_qa.py --update`): `dawn`, `noon` and
`evening`, lit by the sun with its path; `fans-on` and `fans-off`, the air as
arrows; `vents-open` and `vents-closed`, a slice of temperature across the
house; `young` and `fruiting`, beside a row; `camera-rgb` and
`camera-depth`, the path camera's picture; `airflow-slice`, the air's speed
along a fan's jet; and `radiation-slice`, the light in the canopy. Each says
its moment's state probes under it. CI compares them with
`e2e/visual/__screenshots__/reference-<view>-linux.png`.

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

The viewer reads the simulator through its local API. `uv run start`, from
the repository's root, starts both; or start the API, then the viewer, in
two terminals:

```bash
uv run api      # http://127.0.0.1:8765/api
uv run viewer   # the viewer, which forwards /api there
```

Without the API, the page says so and how to start it.

## Develop

Node 24 (see `.nvmrc`) and npm. `uv run setup`, from the repository's root,
installs the packages (`npm ci`) and the browsers; `uv run viewer-checks`
runs the lint, the type check, the coverage and the build as CI does, and
`uv run browser-tests` the browser tests, with the workspace's Python. From
this directory, each step:

```bash
npm ci
npm run dev         # local development server
npm run lint        # Biome: formatting and lint (npm run format applies fixes)
npm run typecheck   # TypeScript, strict
npm test            # Vitest
npm run coverage    # Vitest, and how much of the code it runs, held to a floor
npm run build       # production build into dist/
PYTHON=../../.venv/bin/python npm run e2e  # browser tests against the real simulator API
npm run e2e:visual  # screenshot comparisons (they run in CI's container only)
npm run bench       # the renderer's benchmark, on this machine's graphics card
```

The browser tests start the simulator's API with `$PYTHON -m greenhouse_sim.api`,
so that interpreter needs greenhouse-sim installed: `uv run browser-tests`
names the workspace's. The browser tests start
their own API, on port 8766, and their own build of the viewer, so an API
kept running on 8765 for development cannot answer for them. They never test
a server already running on their ports: Playwright stops, saying the port is
in use. `REUSE_TEST_SERVERS=1` reuses such servers deliberately, to rerun a
test quickly against ones known to be this checkout's. Once every other browser
test has passed, `e2e/renderer-smoke.spec.ts` walks through the whole renderer
as a person would: live play, camera presets, pause, step and reset with a
deterministic replay, selection and overlays, and the stress scene. The
plant lab's tests, which grow thousands of entities, run on their own after
the others too, then the checks of the sun's light (`e2e/light.spec.ts`,
`e2e/solar-lab.spec.ts` and P08's final QA, `e2e/solar-day.spec.ts`), which
work climate runs out to noon, and last P07's final QA,
`e2e/weather-day.spec.ts`, which works the climate through a whole day: each
in its own Playwright project, so that none slows another into a timeout. On
CI the projects are cut into lanes that run at once, each on a machine of its
own with an API of its own (decision 0032); `BROWSER_TEST_LANE=<lane>` runs
one lane here, as CI does (`LANE_STARTS` in `playwright.config.ts`).
`uv run setup` installs the browser, Chromium.

The page shows the simulator version, read from `../pyproject.toml` at build
time, and the commit it was built from. The viewer has no version of its own:
it ships with the simulator.

Built with React, TypeScript and Vite. The 3D scene will use Three.js through
React Three Fiber, as the roadmap's technical choices describe.
