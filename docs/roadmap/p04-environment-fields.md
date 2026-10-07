# P04: Environmental fields and airflow foundation

**Status:** done. Part of the [simulator roadmap](README.md).

## Goal

A pluggable 3D representation of the greenhouse's air, the environment field,
and airflow made visible in the browser, before committing to one fidelity of
computational fluid dynamics (CFD).

## Dependencies

P00 (the viewer) and P01 (the greenhouse's envelope). P02's fixtures make
obstacles realistic, but the first steps don't need them.

## Direction

- **One exchange format:** an environment field, sampled by position (and
  later time), carries what the air holds. Velocity comes first, then
  temperature, humidity, CO₂, and pressure where needed. Whatever computes
  the air writes this format, and whatever uses it reads it: the viewer
  now, plants and sensors later.
- **Diagnostics independent of the solver:** the viewer draws a field's
  arrows, streamlines and slices from the field alone, whatever produced
  it.
- **CFD out of process:** high-fidelity airflow comes from an external
  solver, OpenFOAM first, through an adapter that runs it out of process
  and samples its result onto the canonical field. Developing the viewer or
  running the simulator never requires OpenFOAM.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P04.1 | `feat(fields): define regular 3D vector/scalar field format` | Done |
| P04.2 | `feat(viewer): add airflow arrows, streamlines and scalar slices` | Done |
| P04.3 | `feat(airflow): add lightweight prescribed airflow backend` | Done |
| P04.4 | `feat(cfd): export greenhouse envelope and obstacles as CFD case geometry` | Done |
| P04.5 | `feat(cfd): run a minimal OpenFOAM adapter and import its velocity field` | Done |
| P04.6 | `feat(cfd): add an obstacle and wake QA case` | Done |
| P04.7 | `test(airflow): add a field probe and comparison panel` | Done |

### P04.1: Regular 3D vector and scalar field format

Bounds, grid spacing, vector channels, scalar channels, interpolation and
serialization. Visible result: a synthetic vector field appears as arrows in
the greenhouse. Tests: an analytic field sampled at known coordinates matches
its expected values.

As implemented (see [decision 0026](../decisions/0026-environment-fields-are-cell-centred-grids-of-packed-floats.md)):

- **The air's quantities** are domain vocabulary: `domain.air.AirQuantity`
  (velocity, temperature, humidity, CO₂, pressure), with their units and
  which are vectors.
- **`fields.field`:**
  - **The grid:** `FieldGrid` is a box from its lowest corner, its cells'
    sizes and their counts along x, y and z. `FieldGrid.over` divides a box
    into cells no wider than asked.
  - **The field:** `EnvironmentField` holds a channel per quantity at the
    cells' centres. It refuses channels of the wrong shape or with values
    that are not finite.
  - **Sampling:** trilinear between centres; the outermost centres' values
    out to the box's faces; nothing outside.
  - **Publishing:** a `FieldDocument`, each channel as little-endian 32-bit
    floats in base64 with its unit and range, versioned, and described by
    `fields/field.schema.json`.
- **A synthetic shear** (`fields.synthetic`), made to check the format: air
  along the house, faster with height, and warming with height and along the
  length. Its values are linear in position, so it is known exactly
  anywhere.
- **API:** a scenario's fields cover the air under its gutters, in cells of
  at most 0.5 m: gh_001's is 16 × 20 × 7 cells. The services answer
  `GET /api/scenarios/{id}/fields` with their names, and
  `GET /api/scenarios/{id}/fields/{name}` with one.
- **Viewer:**
  - **Codegen:** `npm run generate` now writes the viewer's side of both
    contracts, the scene and the field.
  - **Reading:** `src/fields/field.ts` checks a field against its schema,
    decodes it, and samples it as the simulator does.
  - **Drawing:** "Air field" chooses a scenario's field (`&field=shear`),
    whose velocity is drawn as an arrow at every cell, in one draw call. Each
    arrow is centred on its cell, as long as its speed is (90% of a cell for
    the fastest), and coloured by speed.
- Tests:
  - Python:
    - grids divide their boxes;
    - the analytic shear sampled at four points has its exact values;
    - edges and outside, and a one-cell field;
    - bad channels and grids refused;
    - the value order, units and ranges;
    - a published field read back to single precision;
    - the published schema up to date;
    - the scenario's fields and their 404s.
  - Viewer:
    - the field checked, decoded and refused;
    - sampled exactly as the simulator samples;
    - loaded and its failures;
    - arrows placed, pointed and sized by speed.
  - Browser: gh_001's shear is chosen, described and unchosen.

### P04.2: Airflow arrows, streamlines and scalar slices

A vector-arrow layer, streamline seeding, horizontal and vertical scalar
slices, and a legend with minimum and maximum controls. Visible result: the
user switches among arrows, streamlines and a temperature heat-map slice.
Tests: a known synthetic vortex or laminar field is recognisable.

As implemented:

- **Drawn as:** "Air field" adds a choice of how the field is drawn, kept in
  the address (`&fieldView=arrows|streamlines|slice`).
- **Streamlines** (`src/fields/streamlines.ts`):
  - **Seeds:** at every third cell's centre along each axis.
  - **Tracing:** both ways from each seed, by fourth-order Runge-Kutta steps
    of half a cell along the flow's direction. A streamline stops where the
    air leaves the field or stands still, after 400 steps, or when it
    returns to its seed, closing a loop, which is then traced only once.
  - **Drawing:** as screen-space lines 2.5 pixels wide, coloured by speed, in
    one draw call.
- **A slice** (`src/fields/slice.ts`):
  - **Placement:** a plane square to x, y or z, anywhere along it within the
    field, kept in the address (`&slice=temperature:z:1.75`).
  - **Colouring:** by any of the field's scalars or by the air's speed,
    sampled at the corners of the cells across it, and blended between
    them. It is grey where the field says nothing.
  - **Default:** the field's first scalar, across its middle height.
- **A legend** names the quantity the colours show and its unit: air speed
  for arrows and streamlines, the slice's quantity for a slice. Its lowest
  and highest colours can be typed in, and given back to the field's own
  range.
- Tests:
  - Viewer:
    - **a vortex's streamlines are closed circles, level and round to within
      2%;**
    - **a breeze's streamlines run straight from one face of the field to the
      other at its speed;**
    - a linear field's slice holds its exact values;
    - slices span the right axes and lie within the field;
    - the default slice and the quantities' scales;
    - slices are kept in the address.
  - Browser: switching between arrows, streamlines and a slice; the default
    slice and moving it; changing its quantity; and moving the legend's
    colours and giving them back.

### P04.3: Lightweight prescribed airflow backend

A uniform field, a vertical buoyancy-like gradient, and a simple vortex, chosen
in a scenario's configuration. Visible result: a dropdown switches between
the known patterns at once. Tests: every backend satisfies the same field
contract.

As implemented:

- **The interface:** `greenhouse_sim.airflow.contract.AirflowModel` is
  anything that produces the air over a grid at a moment, as an environment
  field.
- **`airflow.prescribed`:** three patterns, each set by a few numbers:
  - `UniformAirflow`: one breeze, at one temperature;
  - `BuoyancyAirflow`: convection, two rolls side by side, rising up the
    middle and sinking along the side walls, over air warming with height
    and towards the middle;
  - `VortexAirflow`: one roll across the house, turning about its length.

  The rolls follow stream functions in the y-z plane, so they are
  divergence-free and never flow through the walls, floor or roof.
- **Scenarios:** each names its airflow in its configuration
  (`ScenarioConfig.airflow`): gh_001 a vortex, gh_demo convection, gh_002 a
  uniform breeze. A scenario offers every pattern: its own, as configured,
  first, and the others with their typical numbers. `GET
  /api/scenarios/{id}/fields` says which is its own.
- **Viewer:** "Air field" marks the scenario's own airflow, and switches
  between the patterns at once. Streamlines' and slices' colours are now
  converted to the linear colours the renderer works in, as the arrows'
  are, so they match the legend.
- Tests:
  - Python:
    - **every pattern satisfies the field contract:** it covers the grid
      asked for, at the time asked for, with velocity and temperature,
      finite, repeatable, and published and read back;
    - both roll patterns are divergence-free, run along the walls, floor
      and roof, peak at their configured speed and have no flow along the
      house;
    - convection rises up the middle and sinks by the walls, warmer high and
      in the middle;
    - the vortex turns one way;
    - the breeze is the same everywhere;
    - each scenario's own airflow, offered first.
  - Viewer: the fields listed with the scenario's own.
  - Browser: the options in order, and switching between the three
    patterns.

### P04.4: CFD case geometry from the envelope and obstacles

A geometry export boundary that maps walls, floor, roof, openings and
obstacles to CFD boundaries, and writes a CFD case folder independent of the
browser. Visible result: a debug mode colours exactly the surfaces that
become CFD boundaries. Tests: the exported surfaces' count and categories
match the simulator's semantics.

As implemented (see [decision 0027](../decisions/0027-cfd-runs-out-of-process-on-the-fields-grid.md)):

- **The domain** (`greenhouse_sim.cfd.geometry`) is a scenario's field box,
  the air under its gutters, on the field's own grid, so a solver's cells
  are the field's cells. `cfd_geometry` describes its boundaries as they
  will be meshed, each snapped to the grid:
  - **faces:** the floor, four walls, and the ceiling at the eaves, standing
    for the roof;
  - **openings:** each open door or vent, however far open, on the face it
    opens in; a roof vent projected onto the ceiling. It takes the mesh
    faces whose centres its frame covers, or the one nearest its centre. A
    face is one opening's at most; an opening left with none is listed as
    `unplaced`;
  - **obstacles:** each fixture that obstructs airflow removes the cells
    whose centres it holds. One too small to hold any is listed as
    `too_small`: in gh_001, the irrigation unit removes 6 cells, and the
    crop's 24 slabs, supports and legs are too narrow for half-metre cells.
- **The OpenFOAM case** (`cfd.openfoam`, for v2412): `blockMesh` fills the
  box with the grid's cells, its faces walls; `topoSet` and `createPatch`
  move each opening's faces into a patch named for it; `topoSet` and
  `subsetMesh` remove the obstacles' cells, whose exposed faces become the
  `obstacles` wall. Each selection is the snapped box, padded or shrunk by a
  quarter of a cell, so it chooses exactly the faces and cells the
  geometry does. The case's `Allmesh` script runs only the steps it needs,
  and the dictionaries for a laminar `simpleFoam` run are written beside
  it, for P04.5.
- **Running OpenFOAM** (`cfd.runner`) out of process: natively if it is
  installed, or else in its container (`opencfd/openfoam-default:2412`, or
  `GREENHOUSE_OPENFOAM_IMAGE`) through Docker. Nothing else needs it.
- **Command line:** `python -m greenhouse_sim.cfd gh_001 cases/gh_001` writes
  a scenario's case, changed as its scene can be (`--layout`, `--envelope`,
  `--open door_1:1`); `--mesh` meshes it and says what OpenFOAM made.
- **API:** `GET /api/scenarios/{id}/cfd/geometry` describes the boundaries,
  with the scene's changes (`?open=door_1:1`), as `CfdGeometry`, versioned
  and described by `cfd/geometry.schema.json`.
- **Viewer:** "CFD boundaries" (`&cfd=boundaries`) draws them over the
  scene, following its openings: the floor, walls and ceiling lightly
  tinted, the openings and obstacles strongly, each outlined, in colours by
  category from Okabe-Ito's palette, with a legend of how many mesh faces
  each category takes. `npm run generate` now writes the viewer's side of
  three contracts, and a test checks every one is up to date; the field's
  had not been.
- Tests:
  - Python:
    - the domain is the field box, its six faces of the right sizes and
      categories;
    - **for every scenario, every boundary is one the greenhouse has, by its
      category:** one floor, one ceiling, four walls, an opening for each
      open door or vent, and an obstacle or a too-small entry for each
      fixture in the air's way;
    - only open doors and vents are openings, on the faces they open in;
    - each opening's and obstacle's OpenFOAM selection chooses exactly the
      faces and cells the geometry describes, checked against the grid's
      own centres;
    - at a coarser grid, openings crowd each other out and obstacles become
      too small, and both are listed;
    - the case takes only the steps it needs;
    - the route and its 404 and 400, the published schema, and the command
      line;
    - with `pytest -m cfd`, skipped without OpenFOAM: **OpenFOAM meshes
      gh_001 with its door open into exactly the patches the geometry
      describes,** face for face, and its cells less the obstacle's.
  - Viewer: the geometry checked and loaded, its failures; faces drawn just
    inside the domain and openings just outside it; outlines; the legend's
    sums and the status; the address keeps the toggle.
  - Browser: gh_001's boundaries drawn and described, then its door opened
    and drawn as a third opening, then hidden.

### P04.5: Minimal OpenFOAM adapter

An out-of-process solver runner, a tiny canonical greenhouse case, its output
sampled onto the canonical field grid, and results cached by the scenario's
hash. Visible result: the browser draws velocity vectors from an actual CFD
run rather than a synthetic field. Tests: the reference case completes and
gives finite values on the expected grid.

As implemented:

- **What drives the air** (`cfd.setup.CfdSetup`, `ScenarioConfig.cfd`): air
  blown in square to the scenario's inlets, by default its first open door
  or vent, at 0.5 m/s, and out through every other open one. A scenario
  with fewer than two open openings cannot be solved, and says so.
- **The solve:** steady, laminar `simpleFoam`, with an effective viscosity
  of 0.01 m²/s in place of the air's own. Half-metre cells cannot resolve
  turbulence, so its mixing is folded in as a constant eddy viscosity. The
  air is isothermal.
  - **Boundaries:** the inlets at a fixed normal speed; the outlets at the
    outside's pressure, letting air out and back in freely; no slip on
    every wall, the floor, the ceiling and the obstacles.
  - **`Allrun`:** meshes the case, copies the starting fields from `0.orig`
    (meshing would change them), solves, and writes the cells' centres.
- **Reading it back** (`cfd.solve`): each solver cell's velocity and
  pressure go to the grid cell its centre lies in, so nothing is
  interpolated. The pressure is in pascals, from the kinematic pressure
  times the air's density, 1.2 kg/m³. Inside an obstacle the air is still,
  and its pressure is its neighbours' mean, so the field says something
  everywhere. The reader takes OpenFOAM's lists one entry a line or, when
  short, on one line.
- **Kept by what was solved** (`cfd.results`): a result is keyed by a hash
  of every file written for OpenFOAM. Any change to the greenhouse, its
  openings, its obstacles, the setup or the OpenFOAM version is a new key.
  Each scenario's result is kept in `cfd/results/<id>.json` and offered as
  its `cfd` field only while its key is the scenario's current one.
  `CfdAirflow` serves it as an airflow model: steady at any time, on its own
  grid, or sampled onto another.
- **Command line:** `python -m greenhouse_sim.cfd gh_001 cases/gh_001 --solve`
  solves the scenario and keeps the result. A changed scenario's solve is
  written to `field.json` in its case only.
- **CI:** a CFD workflow runs OpenFOAM's container on changes that can
  change what it is given. It runs `pytest -m cfd`, solves the reference
  case, and keeps the results and the solver's logs as the `cfd-results`
  artifact. gh_001's kept result came from it, solved on Linux.
- **Viewer:** nothing new. "Air field" lists `cfd` among gh_001's fields,
  and draws it as arrows, streamlines or a slice like any other field.
- Tests:
  - Python:
    - flow roles, and the setups refused;
    - the case's boundary conditions;
    - **the key changes with everything OpenFOAM is given and nothing
      else;**
    - values read whether uniform or listed either way;
    - **a solution written in OpenFOAM's format, its cells shuffled and one
      removed, read onto the grid by its centres**, and the removed cell
      still, at its neighbours' pressure;
    - solutions that don't fit the grid refused;
    - convergence read from the log;
    - results kept while current;
    - **every airflow model, prescribed or solved, satisfies the same field
      contract;**
    - gh_001's kept solution is current and converged, and its air falls
      from the inlet vent at about its speed and rises to the outlet;
    - its solution as a field on another grid;
    - the scenario offers it;
    - with `pytest -m cfd`, **OpenFOAM solves gh_001 again, as its kept
      result says**, within 2% of each quantity's scale.
  - Browser: gh_001's `cfd` field listed, described and drawn as
    streamlines and a pressure slice.

### P04.6: Obstacle and wake QA case

One simple block or row obstacle inside, with an inlet and an outlet, and its
imported solution. Visible result: streamlines visibly deflect around the
obstacle and show a wake. Tests: qualitative field checks, and numeric probes
stored at fixed positions.

As implemented:

- **The QA scenario, `airflow_box`** (`scenarios/airflow_box.py`):
  - **The house:** single-span, 12 m long and 6.4 m wide, with a 2 m by
    2.2 m door open at each end, face to face.
  - **The block:** on the floor halfway between the doors, 1 m along the
    house, 2 m across and 1.5 m high, a fixture that obstructs airflow. Its
    `open` layout is the same house without it.
  - **Driving the air:** blown in through the front door at 0.5 m/s, out
    through the back one. Its prescribed airflow is a uniform 0.5 m/s breeze
    along the house, to compare with (P04.7).
  - **Its one plant** stands in a back corner, out of the way.
- **Kept per layout:** a scenario's CFD results are kept for each of its
  layouts (`results/<id>@<layout>.json`). A scenario's fields are asked for
  with its layout (`?layout=open`), which only its CFD solution depends on,
  and the viewer asks with the layout it shows. The CFD workflow solves both
  of airflow_box's layouts.
- **The solutions** (24 × 13 × 6 cells; the block removes 2 × 5 × 3). Both
  converged in 81 to 86 iterations. With the block, the air:
  - rises over it in front, at 0.11 m/s against 0.03 m/s without it;
  - squeezes past beside it, at 0.19 m/s against 0.06 m/s;
  - leaves a wake behind it, which near the floor runs back towards it, at
    −0.01 m/s, where the open house's air runs on at 0.29 m/s.
- **Probes:** the velocity and pressure at six fixed points, for both
  layouts, are kept in `tests/golden/airflow_box_probes.json`, so a change
  to the solutions shows as numbers in review. `python
  tests/test_cfd_wake.py --update` writes them from the kept solutions.
- **Viewer:** a long scenario identifier now wraps in the scenarios table,
  rather than pushing its buttons out of the panel.
- Tests:
  - Python:
    - **the kept solutions turn the air around and over the block and leave
      a wake behind it, against the house without it**: it rises in front,
      is faster beside and over it, and is less than 30% as fast 1 m
      behind it, where it turns back towards the block low down;
    - the probes hold the kept solutions' values;
    - the scenario offers each layout's solution, still inside the block
      only with it;
    - with `pytest -m cfd`, **OpenFOAM's fresh solutions pass the same
      checks**, and match the probes to 0.01 m/s and 0.005 Pa.
  - Browser: airflow_box's solution with and without its block, and its
    fields listed with its own breeze first.

### P04.7: Field probe and comparison panel

Clicking in the 3D view inspects the field's vector and scalar values there,
and the prescribed backend and the CFD result can be compared at selected
points.

As implemented (all in the viewer, which reads a field as the simulator
samples it):

- **Probes** (`src/fields/probes.ts`, `FieldProbes.tsx`): up to eight
  points in the drawn field, kept in the address
  (`&probes=3:3.2:0.75,7:3.2:0.75`).
  - **Placing one:** "Add a probe" adds one in the field's middle. With
    "place by clicking" checked, a click in the view places one above the
    ground under the cursor, at the height chosen (1 m to start), and selects
    nothing. Each probe's coordinates can be typed in, and it can be
    removed.
  - **Reading it:** each probe says what the drawn field holds there: the
    air's speed and velocity, and each scalar with its unit, or that it lies
    outside the field.
  - **Marking it:** in the view, by name, on a leader up from the ground,
    with an arrow along the air there, a metre long where the air is the
    field's fastest.
- **Comparison:** "Compare with" chooses another of the scenario's fields
  (`&compare=uniform`). Each probe then says what that field holds too, and
  how the drawn one differs: how much faster, how far its air is turned, in
  degrees, and the difference in each scalar both hold.
- **Clicking:** the view's undrawn ground plane now reaches 100 m each way,
  so the pointer is found on the ground anywhere in a long greenhouse.
- Tests:
  - Viewer:
    - probes kept in the address, and refused when malformed;
    - read as the simulator samples, and nothing outside the field;
    - **two fields compared: the difference in speed, the turn between
      directions, and the scalars both hold;**
    - written out with their units, and marked in the view.
  - Browser:
    - **airflow_box's CFD solution against its uniform breeze, at two
      probes:** upstream, 0.07 m/s slower and turned 8° upwards; in the
      wake, nearly still and turned back 130°;
    - comparing with nothing;
    - a probe added, placed by a click that selects nothing, moved and
      removed.

## Final QA: `airflow-box`

- toggle the field's arrows and streamlines;
- inspect several probe points;
- switch between a prescribed field and the CFD result;
- enable and disable one obstacle, and check the expected deflection;
- take screenshots of the vector and slice views.

As implemented, on the airflow QA case, `airflow_box` (P04.6): air blown
from door to door past a block, solved with OpenFOAM, with the block and
without it (`&layout=open`).

| QA step | Where |
| --- | --- |
| Arrows and streamlines | "Air field" → `cfd`, drawn as arrows or streamlines |
| Probe points | "Add a probe", or a click in the view while placing them (P04.7) |
| Prescribed against CFD | "Air field" switches between `uniform` and `cfd`; "Compare with" reads both at every probe |
| One obstacle, on and off | the scenario's layout, `default` with the block or `open` without it, which keeps the field, its probes and its comparison |
| Screenshots | `/qa/airflow-box?view=vectors` and `?view=slice`, drawn from the simulator's files (`tests/test_airflow_qa.py --update`) and compared with CI's baselines |

The walkthrough, on 7 October 2026 (`e2e/airflow-box.spec.ts`):

1. **Arrows and streamlines.** The CFD solution, 24 × 13 × 6 cells with air
   from still to 0.60 m/s, is drawn as arrows and then as streamlines.
   Streamlines run in at the front door, pass around and over the block,
   and gather at the back door. Slow eddies turn beside the inlet's jet, in
   the front corners. The air turning back in the block's lee is too slow
   and small to show as streamlines; the probes and the slice show it.
2. **Probes,** upstream of the block, beside it and 1 m behind it, at half
   its height:
   - upstream, the air runs at 0.43 m/s, rising a little towards the block;
   - beside it, at 0.21 m/s, turned 25° outwards;
   - behind it, at 0.02 m/s, turned back towards the block.
3. **Prescribed against CFD.** Against the uniform 0.5 m/s breeze, the
   solution is 0.07 m/s slower upstream and turned 8° upwards. Behind the
   block it is 0.48 m/s slower and turned back about 130°: a breeze has no
   wake.
4. **The block, off and on.** With the `open` layout, the probes stay where
   they are:
   - beside where the block stood, the air slows to 0.07 m/s, no longer
     squeezed past it;
   - behind it, the air runs on at 0.29 m/s.

   Put back, the wake returns: 0.02 m/s.
5. **Screenshots.** The vectors view, from beside and above the house,
   shows the jet from the front door spreading and lifting over the block.
   The slice view, from above, of the air's speed through the block at
   0.75 m high, shows:
   - the inlet's jet splitting around the block;
   - a still wake behind it, twice the block's length;
   - the air gathering again towards the back door.

   CI draws and compares both (`e2e/visual/airflow.spec.ts`).

## Acceptance criteria

- [x] **The browser shows airflow independently of the solver.** Arrows,
  streamlines, slices and probes read any field alike, whether prescribed,
  synthetic or solved.
- [x] **The environment field is the stable exchange format.** Every
  airflow model, prescribed or solved, satisfies the same field contract
  (decision 0026).
- [x] **At least one real CFD case round-trips through an external engine.**
  gh_001 and both layouts of airflow_box are meshed and solved by OpenFOAM
  and read back as fields. CI solves them again and compares (decision
  0027).
- [x] **OpenFOAM is optional for normal viewer development.** Solved results
  are kept in the repository, keyed by what was solved. Only `pytest -m cfd`,
  `--mesh` and `--solve` need OpenFOAM, natively or in Docker.
- [x] **A solver's output can later feed plants and sensors without
  solver-specific code.** A solution is an `AirflowModel` producing an
  `EnvironmentField`, sampled by position like any other.
