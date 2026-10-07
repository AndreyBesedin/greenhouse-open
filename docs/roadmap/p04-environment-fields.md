# P04: Environmental fields and airflow foundation

**Status:** in progress. Part of the [simulator roadmap](README.md).

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
| P04.5 | `feat(cfd): run a minimal OpenFOAM adapter and import its velocity field` | Planned |
| P04.6 | `feat(cfd): add an obstacle and wake QA case` | Planned |
| P04.7 | `test(airflow): add a field probe and comparison panel` | Planned |

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

### P04.6: Obstacle and wake QA case

One simple block or row obstacle inside, with an inlet and an outlet, and its
imported solution. Visible result: streamlines visibly deflect around the
obstacle and show a wake. Tests: qualitative field checks, and numeric probes
stored at fixed positions.

### P04.7: Field probe and comparison panel

Clicking in the 3D view inspects the field's vector and scalar values there,
and the prescribed backend and the CFD result can be compared at selected
points.

## Final QA: `airflow-box`

- toggle the field's arrows and streamlines;
- inspect several probe points;
- switch between a prescribed field and the CFD result;
- enable and disable one obstacle, and check the expected deflection;
- take screenshots of the vector and slice views.

## Acceptance criteria

- [ ] The browser shows airflow independently of the solver.
- [ ] The environment field is the stable exchange format.
- [ ] At least one real CFD case round-trips through an external engine.
- [ ] OpenFOAM is optional for normal viewer development.
- [ ] A solver's output can later feed plants and sensors without
  solver-specific code.
