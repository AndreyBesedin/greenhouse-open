# P05: Climate actuators: fans, heaters, dehumidification and vents

**Status:** done: P05.0 to P05.7 and the final QA. Part of the [simulator roadmap](README.md).

## Goal

Make greenhouse equipment change the simulated air in visible, testable ways,
while keeping each device's model independent of the airflow backend.

## Dependencies

P01 (the envelope and its openings) and P04 (environment fields and
airflow). P02's fixtures make obstacles and placement realistic.

## Direction

- **Equipment is represented twice:** as a semantic, visual entity in the
  world (where it stands, what it is, what it is commanded to do), and as
  the source terms it supplies to whatever computes the air.
- **Useful approximations over equipment CFD:** a fan is a jet, a heater a
  heat source, a dehumidifier a moisture sink. No device needs a particular
  solver.
- **Commands are explicit and replayable:** what a device is told to do,
  and when, is data. The same commands always give the same air.

## Design

Today the air is a steady snapshot. A field is either a prescribed pattern
or a kept CFD solution, with no time in it beyond a label. The crop's
climate is one greenhouse-wide temperature and humidity, a day at a time
(`environment.simple`). Equipment acts in seconds to minutes, and its
effects build up and spread. So P05 needs air that evolves. Each choice
below gives what it was weighed against. The review's decisions are at the
end.

### 1. A climate model that steps the air on the field's grid

A new backend, `climate.transport`, holds the air's state on a scenario's
field grid (decision 0026): temperature, humidity and velocity in every
cell. It advances that state through time. This is the "spatial
approximation" rung of the fidelity ladder, between the prescribed patterns
and CFD.

- **Velocity** is the scenario's base airflow plus each running fan's jet
  (section 3). The base airflow is its prescribed pattern or its kept CFD
  solution, whichever the run names.
- **Temperature and humidity** are carried by that velocity and mixed by an
  effective diffusivity: advection–diffusion, by finite volumes on the
  grid. Heaters add heat, dehumidifiers remove moisture, open vents
  exchange air with the outside, and the envelope exchanges heat with it
  through its glass.
- **Humidity is transported as absolute humidity** (grams of water per
  kilogram of air), which mixing conserves. Relative humidity is derived
  from it and the temperature when published.
- **Numerics:**
  - first-order upwind advection, which keeps values within their range;
  - explicit diffusion;
  - a time step held within both stability limits (the air crossing at
    most half a cell per step, and the diffusion limit);
  - obstacles' cells (P04.4) blocked;
  - no flux through walls, the floor and the ceiling, except heat exchange
    and open vents.
- **Conservation:** the base airflow plus fans is not exactly mass
  conserving. Advection is written so that uniform air stays uniform
  wherever the flow converges or diverges. With exchange and vents off, the
  energy and moisture budgets close exactly, which the tests check. The
  approximation is tracked under "Known approximations".
- **Cost:** a greenhouse of a few thousand cells steps in well under a
  millisecond with NumPy. Ten simulated minutes near a fast fan take a few
  thousand steps, about a second.

*Alternatives:*
- **A single well-mixed volume per zone** (a zonal energy and moisture
  balance): cheap, but it can't show a heater warming its corner or a
  fan's plume, which this project's visible results are about.
- **Running OpenFOAM in time** (`buoyantPimpleFoam`): faithful, but it
  makes every actuator change wait on an external solver, and contradicts
  "no actuator requires a specific CFD engine".
- **Projecting the velocity to be divergence-free** (a pressure solve on
  the grid each time the fans change): left for later. It's cheap at this
  size, but adds a solver to own before its benefit is visible.

### 2. A clock for the air, separate from the crop's days

The air runs on its own clock, in seconds, for a **climate run**. A run is
a scenario's air from a starting state, over minutes to hours, under a
command schedule. The engine's day step is unchanged. Plants keep reading
their daily climate as now. Feeding them the air where they stand (a daily
summary of the local air) is P07/P09's, once weather drives the outside.

- **The starting state:** the scenario's base airflow, and uniform
  temperature and humidity from its configuration.
- **The outside:** a fixed temperature and humidity in the scenario's
  configuration, until P07 brings weather.
- **Serving a run:** the service recomputes it from its start for the time
  asked, and keeps recent runs in a small in-memory cache. A run is cheap
  and deterministic, so there is nothing to persist.

*Alternatives:*
- **A full multi-rate orchestrator now**, advancing crop days and air
  seconds together: the plan's eventual design, but it would turn P05 into
  P09.
- **Advancing the air one day at a time like the crop:** too coarse for
  equipment that acts in minutes.

### 3. Equipment: kinds, placement, commands and source terms

- **Vocabulary:** `domain.equipment.ActuatorKind`: fan, heater,
  dehumidifier. Vents stay the envelope's openings (P01), with the opening
  fraction they already have.
- **Placement:** an actuator is placed in a scenario's layout file, beside
  the fixtures. It has an identifier, a kind, a pose (position, and for a
  fan the direction it blows), a size, and its rated capacity:
  - a fan's airflow, in m³/s, and its diameter;
  - a heater's power, in W;
  - a dehumidifier's water removal, in kg/h, and the heat it gives off, in W.

  A heater or dehumidifier obstructs airflow like any fixture, so the CFD
  geometry sees it.
- **Commands:** each actuator has a level from 0 (off) to 1 (full).
  - **A schedule** is a list of `(time_s, actuator, level)` commands.
  - **Manual overrides** from the viewer are commands too, at the moment
    they are made.
  - **Logging:** the run records every command it applied, in order.
  - **In the address**, as a scene change like `?open=`:
    `?set=fan_1:1,heater_1:0.5` for levels from the start of the run, and
    `&schedule=60:fan_1:1,300:heater_1:0` for the schedule.
- **Source terms, the device contract:** an actuator at a level supplies
  its effect as backend-independent terms over the grid:
  - **velocity added**, for a fan: a jet along its axis, with its core
    speed set by flow over area, decaying and spreading with distance;
  - **heat added**, in W per cell, for a heater and a dehumidifier's waste
    heat;
  - **moisture removed**, in kg/s per cell, for a dehumidifier, never more
    than the air holds.

  The transport model consumes these terms. A later CFD adapter could map
  them to `fvOptions` sources without the devices changing.

*Alternatives:*
- **Actuators as a field of `ScenarioConfig`:** possible, but equipment is
  placed like fixtures and belongs to the layout, so another layout can
  equip the house differently.
- **Devices that write into the field directly:** simpler for one backend,
  but it ties every device to the transport model.

### 4. Vents

An open vent's aperture area (P01.5, decision 0018) sets how much air it
exchanges with the outside. Absent wind (P07), the exchange is a fixed
exchange speed times the aperture area, mixing outside air into the vent's
cells. It also adds a small draught there, so the arrows respond. Its
direction is out of the vent when the air inside is warmer, and in when it
is cooler, as the stack effect would have it. A closed vent exchanges
nothing. The CFD geometry already treats an open vent as an opening (P04.4).

### 5. Heat exchange through the envelope

Each wall, roof and floor cell face exchanges heat with the outside: in
proportion to its area and the glazing's heat transfer coefficient (about
6 W/m²K for single glass), times the outside's temperature less the
inside's. When the outside is cooler the house loses heat; when it is
warmer it gains it. This lets the house settle at a temperature rather than
heating or cooling without end. The tests switch it off to check the
heater's energy budget exactly. Sunlight through the glass is P08's.

### 6. Viewer

- **Equipment in the scene:**
  - a fan as a short cylinder with an arrow along its axis; heaters and
    dehumidifiers as boxes;
  - each coloured as off or running, selectable, and described in the
    inspector (kind, capacity, level);
  - "Equipment" lists every actuator with an on/off switch and a level
    slider, like "Openings".
- **The air as the equipment drives it:** a `climate` field among the
  scenario's fields. It is drawn like any other (arrows, streamlines,
  slices, probes), at a time on the run's clock, with a time slider and
  play (`&t=300`).
- **The schedule:** a timeline under the time slider marks each scheduled
  command (05.6).
- **Probes over time:** each probe charts temperature, relative humidity
  and air speed through the run. A second run, with all equipment off, can
  be charted beside it (05.7). The charts are plain SVG; no chart library.

### 7. Scenarios

The review decided to retire the original scenarios, gh_001, gh_demo and
gh_002, and build new ones that matter to what the simulator is now. They
come before the equipment, so that P05's equipment, QA and baselines are
built on them rather than moved later. Scenarios exist to test and QA what
each project adds and to catch regressions; demonstration scenarios will be
built through the interface once it can build them. The airflow QA case,
`airflow_box`, stays. P05's own QA scenario, `climate_box`, is one of the
new scenarios (P05.0).

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P05.0 | `feat(scenarios): replace the original reference scenarios` | Done |
| P05.1 | `feat(actuators): define climate actuator contract and controls` | Done |
| P05.2 | `feat(fans): add fan airflow source model` | Done |
| P05.3 | `feat(heating): add heater sensible-heat source` | Done |
| P05.4 | `feat(humidity): add dehumidifier moisture sink` | Done |
| P05.5 | `feat(vents): connect vent opening state to airflow boundaries` | Done |
| P05.6 | `feat(control): add actuator schedule timeline` | Done |
| P05.7 | `test(climate): add actuator comparison dashboard` | Done |

### P05.0: New reference scenarios

Retire gh_001, gh_demo and gh_002 for new scenarios that matter to the
simulator as it is now (section 7), and move everything that rests on them.
Their design, below, was reviewed before they are built.

**What the scenarios are for.** Today, the original scenarios carry most of
the simulator's tests and examples:

| Role | Today | After P05.0 |
| --- | --- | --- |
| The reference: a full house of crop rows, with every kind of fixture and zone, a second layout, a kept CFD result; the examples, the conformance tests and the reference baseline | gh_001: 8 × 9.6 m, two spans, 40 plants, 28 days | `tomato_compartment` |
| Small and quick: the example scene, live play, the viewer's bounds and command tests, every kind of opening | gh_demo: 4 × 6.4 m, two spans, 6 plants, 15 days | `climate_box` |
| One plant, followed for a season: examples 01 and 03, the controls and renderer smoke tests, a scenario with no openings | gh_002: 4 × 3.2 m, one plant, 40 days | `climate_box` |
| The airflow QA case | `airflow_box` | unchanged |

Both new scenarios run the simple tomato model, as every scenario does now;
the organ-level model joins the engine in P09.

#### `tomato_compartment`: a production compartment

A modern glasshouse compartment for high-wire tomato, the scale and shape
the simulator's later projects (sensors, weather, sun, the integrated
scenario) are about.

- **The house:** 24 m long (six 4 m bays) and 16 m wide (four 4 m spans),
  with 6 m to the gutters and 6.8 m to the ridges: a Venlo-style
  multi-span roof. Its field grid is 48 × 32 × 12 cells.
- **Openings:** a roof vent on each span's right slope, 6 m by 1 m, standing
  20% open; a 3 by 3 m sliding door in the front gable for trolleys,
  closed.
- **The crop:** eight rows along the house, 1.6 m apart, of 40 plants each
  at 0.5 m: 320 plants, on hanging gutters under crop wires, for 28 days. A
  season takes about a second with the simple model.
- **The layout:**
  - a main path across the front, past the door, and side paths along both
    side walls;
  - a pipe rail between each pair of rows, which heats and carries
    trolleys;
  - heating pipes along both side walls;
  - a service area at the back, with an irrigation unit that obstructs the
    air and is kept clear of robots.
- **Its second layout, `propagation`:** the same house set up for raising
  young plants, on benches. It keeps today's coverage of benches, which
  gh_001's `benches` layout gives.
- **Its air:** convection as its prescribed airflow. A CFD result is kept,
  solved by the CFD workflow, with the first vent as the inlet and the
  others as outlets, as now.
- **No equipment until the end of the roadmap (P09)**, unless a test, a
  regression check or a QA scenario needs it sooner.

#### `climate_box`: a small house to equip

A single-span house, small enough to follow its air closely, where P05's
equipment is placed and its final QA is run. It also takes over gh_demo's
and gh_002's small and quick roles.

- **The house:** 12 m long and 6.4 m wide, with 4 m to the gutters and
  4.8 m to the ridge. Its field grid is 24 × 13 × 8 cells.
- **Openings:** every kind, so that their tests keep a home:
  - a roof vent, 4 m by 1 m, on the right slope;
  - a side vent, 3 m by 0.6 m, in the right side wall;
  - a door in the front gable.

  All are closed to start, so that the equipment acts on still, closed air.
- **The crop:** two rows on gutters, 1.6 m apart, of 16 plants each: 32
  plants, for 14 days.
- **Its air:** still to start: a uniform breeze of 0 m/s, so that a fan's
  jet stands out. No CFD result: closed, it has no way in or out.
- **Equipment, from P05.1 on:**
  - a fan at the front, 2.8 m up, blowing along the house;
  - a heater in a back corner;
  - a dehumidifier by the left side wall.

  The run's outside (8 °C, 90%) and starting air (16 °C, 85%) come with
  P05.3 and P05.4: a cold, damp night, when heating and drying matter.

#### What moves

- **The simulator's tests:** 29 files name an original scenario. Each moves
  to whichever new scenario serves the same role, with its expected numbers
  worked out afresh: cells, mesh faces, field ranges, plant counts.
- **The viewer:**
  - 19 browser specs and 10 unit test files;
  - the example scene, regenerated from `climate_box`, with the bounds test
    following its size.
- **The reference baseline:** regenerated. The original scenarios' entries
  go, the new ones' come, and `airflow_box`'s stays as it is.
- **Kept CFD results:** gh_001's goes; `tomato_compartment`'s is solved by
  the CFD workflow, with its solve list following.
- **The four examples, the conformance tests and the READMEs** move to the
  new scenarios: the examples that follow one plant, or close the loop with
  a policy, to `climate_box`; those that store, query and score a full
  house, to `tomato_compartment`.
- **Unchanged:**
  - finished projects' roadmap pages, which record what was built then;
  - the protocol package's tests, which use "gh_001" only as a sample
    identifier;
  - the screenshot QA pages, which draw their own scenes.

#### Delivery

Two stacked pull requests:

1. **Adding:** `feat(scenarios): add the tomato compartment and the climate
   box`. The new scenarios, their layouts, their tests, their baseline
   entries, and the compartment's CFD result, which CI solves (two commits,
   as before).
2. **Retiring:** `refactor(scenarios): move to the new scenarios and retire
   the original ones`. Every dependent moves, gh_001, gh_demo and gh_002
   and their layouts and results go, and the examples and READMEs follow.

#### As implemented

- **`tomato_compartment` and `climate_box`** are as designed. In numbers:
  - **the compartment:**
    - field grid: 48 × 32 × 12 cells;
    - four roof vents of 1.1 m² each at 20% open, and a 3 m door, shut;
    - eight rows of forty plants;
    - a pipe rail in each of the seven paths between rows;
    - its scene: 896 entities;
    - its kept CFD solution: solved by the CFD workflow, converged in 79
      iterations, air in through the first vent at up to 0.49 m/s and out
      through the other three.
  - **the box:** field grid 24 × 13 × 8 cells; 32 plants; its scene: 111
    entities.
- **Retired:** gh_001, gh_demo and gh_002, their layouts, and gh_001's kept
  CFD result.
- **What moved:**
  - **the simulator's tests:** 29 files, by role:
    - tests of a full house, its layouts or its CFD solution, to the
      compartment;
    - tests of a small, quick house, to the box.
  - **Re-pinned numbers:** those that follow a scenario's seed, such as
    the characterization run's heights and fruit, now follow the
    compartment's.
  - **The model contracts and the checkpoint round trip:** the model
    contracts run 28 days in the box, so that fruit ripens; the
    checkpoint round trip runs in the compartment. gh_demo's crop had been
    tuned to fruit fast.
  - **The viewer's tests:** 19 browser specs and 10 unit test files, their
    picks worked out afresh.
    - **New picks:** the compartment's heating pipes are picked from the
      front right, since its roof gutter hides them from above; its
      service area from a camera beyond its back wall.
    - **Separate live runs:** the time controls play `airflow_box`, so
      that the box's live run is left alone.
  - **The example scene** is drawn from the box.
  - **The examples, the conformance tests and the READMEs** follow.
- **Fixed on the way:** the viewer had worked out a drawn field's colour
  scale afresh on every render, so its streamlines were traced again four
  times a second. On the compartment's field, nine times gh_001's, that
  took seconds; it is now worked out once per field. Streamlines also start
  from at most 300 seeds.
- **New:** the address can place a scenario's camera
  (`&camera=26:6:8,23.3:6:1`, its position then the point it looks at).
  The presets frame only the corner of a 24 m house.

#### Review decisions (7 October 2026)

1. **The set:** `tomato_compartment` and `climate_box`, with `airflow_box`
   staying, as proposed.
2. **gh_002 is retired too.** Scenarios are for testing and QA of what each
   project adds and for catching regressions. Demonstration scenarios will
   be built through the interface later.
3. **The compartment's scale,** 24 × 16 m with 6 m to the gutters and 320
   plants: agreed.
4. **The compartment's equipment** waits for the end of the roadmap, unless
   a test, a regression check or a QA scenario needs it sooner.
5. **The names,** `tomato_compartment` and `climate_box`: agreed.

### P05.1: Climate actuator contract and controls

Actuator kinds, placement in layout files, rated capacities, levels and the
command log; the source-term contract; `climate_box`. Visible result: a
device can be selected, inspected and switched on and off in the browser.
Tests: commands are logged in order and replay deterministically, and a
device's source terms scale with its level and vanish when it is off.

#### As implemented

- **Equipment in a layout** (`world.equipment`), listed in a layout file
  beside its fixtures, by kind:
  - **a fan:** the centre of its rotor, its heading (the way it blows), its
    diameter and its flow; drawn as a 0.3 m deep housing along its heading;
  - **a heater or a dehumidifier:** a box on a base, turned by its heading,
    its depth along it, with its power, or its water removal and waste
    heat.
- **In the way:** a unit's body is in the way of air and of robots, as an
  obstacle is. So it is kept off walkways and inside the house, and the CFD
  mesh cuts it out. A fan is in the way of nothing. Identifiers are unique
  across fixtures, zones and equipment. Every layout file lists its
  equipment, if only as none.
- **The climate box's equipment,** all off until commanded:
  - a fan of 1 m³/s and 0.5 m across, 2.8 m up over the front path,
    blowing down the house;
  - a 10 kW heater, 0.6 × 0.8 × 1.2 m, in the back right corner, facing
    into the house;
  - a dehumidifier of 5 kg/h giving 4.5 kW, 0.6 × 1.0 × 1.4 m, halfway
    along the left wall, facing across; re-rated in P05.4 to 1 kg/h and
    1.2 kW.

  The CFD mesh loses 2 cells to the heater and 12 to the dehumidifier. The
  box's scene: 114 entities.
- **Commands** (`climate.commands`): a command sets an actuator to a level
  at a moment of a run. A schedule holds them in time order, keeping the
  given order at a moment, so the later one wins. Everything starts off.
  What a run applied up to a moment is its log, and a schedule replays the
  same from its record. The run that keeps that log comes with the air's
  clock (P05.3).
- **Source terms** (`climate.sources`): velocity added, heat added and
  water removed, cell by cell, each the rating times the level.
  - **Where:** a unit gives its heat to, and takes its water from, the air
    cells within a cell of its body, beside it or above it, shared evenly.
    It never uses the cells its body fills, as the CFD mesh removes them
    (`CfdGeometry.solid`). A unit hemmed in by other solids uses the
    nearest air cell.
  - **Not yet:** a fan adds nothing until its jet (P05.2), and water
    removal is capped by what the air holds once the air holds water
    (P05.4).
- **The scene** (schema 14): each piece is an entity of its kind, `FAN`,
  `HEATER` or `DEHUMIDIFIER`, with its actuator, level and rated capacity.
  It is grey while off and in its kind's colour while it runs: blue, red
  and cyan from Paul Tol's bright scheme, which the categories view uses
  too, in a legend of their own.
- **Levels in the address:** a scene request takes `?set=heater:0.5`.
  Equipment the scenario lacks, or a level outside 0 to 1, is refused with
  the reason. The CFD geometry ignores levels.
- **The viewer's Equipment panel:** a switch and a slider per piece, in
  steps of 5%. Switched on, a piece runs at full power. The panel reads
  what the scene's level gives: off, or `50%, 5 kW`.
- **Fixed on the way:** CI on Linux drew one of the example scene's plants
  a last bit taller than macOS had. The example scene is now compared to
  a relative 1e-12, as rounding it would also round its rotations.

### P05.2: Fan airflow source model

The fan's jet: core speed from flow and diameter, decay and spread with
distance, superposed on the base airflow in the `climate` field. Visible
result: turning a fan on visibly changes the arrows and streamlines near
it. Tests: velocity probes downstream speed up along the fan's axis, the
jet's flow through a plane across it matches the fan's flow near the fan,
and nothing changes behind it or with it off.

#### As implemented

- **The jet** (`climate.jets`): a round free jet along the fan's heading,
  its speed a Gaussian of the distance from its axis.
  - **Its core:** for six rotor diameters it keeps the rotor's radius and
    the fan's core speed, its flow over its swept area: 5.1 m/s over 3 m
    for the climate box's 1 m³/s through 0.5 m.
  - **Beyond:** it widens linearly and slows as it widens, keeping its
    momentum: its speed on the axis falls as 6 U₀ D / x, the classic decay
    of a round jet, and the air it carries grows as it draws in the air
    around it.
  - **Where it adds nothing:** behind the rotor, in the cells obstacles
    fill, and beyond three widths from its axis, where it is under a
    ten-thousandth of its speed on the axis.
  - At a level, it blows that share of its flow.
- **The `climate` field:** a scenario whose layout places equipment offers
  it, between its CFD solution and the shear. It is the scenario's own
  airflow plus every running piece's source terms (`climate.field`), for
  now the fans' jets; its temperature is its own airflow's until P05.3
  carries it. `GET .../fields/climate?set=fan:1` serves it with the fan on.
  Every field request's levels are checked as a scene's are.
- **In the climate box,** with the fan on, the air along its axis moves at
  4.4 m/s 2 m from the fan, 1.8 m/s 8 m from it, and is still behind it.
  The field's fastest cell: 4.89 m/s.
- **The viewer** loads the climate again whenever the Equipment panel
  changes a level; other fields are not reloaded. A fan is drawn on its
  own rather than in a batch of cylinders, with an arrow out of its
  housing the way it blows.

### P05.3: Heater sensible-heat source

The transport model's first scalar: temperature, carried and mixed over the
run's clock, with heat exchange through the envelope; the heater's heat source;
the `climate` field's time slider. Visible result: a temperature slice warms
around a running heater and spreads with time. Tests: with exchange off,
the energy the air gains matches the heater's power times the time, to
within 1%. With exchange on, the house settles where the heater's power
balances what the envelope loses, and with the outside warmer and the
heater off, the house warms towards it.

#### As implemented

- **A scenario's climate settings** (`climate.settings`): the outside's
  temperature, the air's at the start, the glazing's U-value, and the air's
  effective mixing. The climate box: 8 °C outside, 16 °C to start, single
  glass at 6 W/m²K.
- **The flow is projected after all** (`climate.projection`), though the
  design had left it for later.
  - **Why:** carried by the unprojected jet, the climate box kept only 29%
    of a heater's energy with the fan on. The jet appears at its rotor and
    dead-ends at the far wall, right where the heater stands, so a running
    fan would have cooled a heated house.
  - **How:** a potential over the air cells, solved by Jacobi-preconditioned
    conjugate gradients in NumPy (4.5 ms for the box, no new dependency),
    takes the flow's divergence out of every face, to 1e-10 of it.
  - **What it shows:** the fan now draws the air it blows from behind it,
    0.75 m/s at its back, and the house returns it along the floor. Its
    core keeps most of its speed: 4.34 m/s 2 m from the fan, where the
    unprojected jet had 4.42.
- **The transport** (`climate.transport`), by finite volumes:
  - upwind advection in the conserving flow;
  - mixing at κ = 0.1 m²/s. At 0.01, a heater's corner reached 150 °C; at
    0.1 it holds about 40 °C, as a heater's own convection would keep it;
  - the heaters' source terms;
  - exchange through the walls and roof, both ways. The floor isn't glass,
    and passes nothing.

  Every step keeps each new temperature a weighted mean of the old ones,
  at most half taken away. Shut, the air gains exactly the heater's energy,
  still or with the fan on (to 1e-8).
- **The climate run** (`climate.run`): from the starting air, with the
  schedule's commands applied at their moments. A run keeps every moment
  asked of it, so a later moment carries on from there, and the service
  keeps eight recent runs. An hour with the fan on takes about 3 s.
  `GET .../fields/climate?set=heater:1&t=600` serves the air ten minutes
  in. Obstacle cells show the mean of the air beside them.
- **In the climate box:**
  - **unheated,** the house cools from 16 °C towards the 8 °C outside, to
    9 °C in ten minutes;
  - **heated,** its corner is at 32 °C and its middle at 15 °C ten minutes
    in, and it settles where the 10 kW balance what its 224 m² of glass
    loses, about 15.4 °C.
- **The viewer:** with the climate drawn, "Climate run" moves through the
  hour a minute at a time, or plays it, once each moment has arrived
  (`&t=600`).

### P05.4: Dehumidifier moisture sink

Absolute humidity transported beside temperature; relative humidity derived
from both and published; the dehumidifier's moisture sink and waste heat.
Visible result: a humidity slice dries around a running dehumidifier.
Tests: the water the air loses matches the commanded removal rate, never
more than the air holds. The relative humidity is right against
psychrometric tables.

#### As implemented

- **Psychrometrics** (`climate.psychrometrics`): Buck's saturation pressure
  over water, within 0.1% of the ASHRAE tables, and the humidity ratio
  and relative humidity from one another, at standard pressure.
- **The air's water** is carried beside its temperature, as its humidity
  ratio (g/kg), in one array, one pass over the faces per step.
  - **The dehumidifier** dries its cells by its rating times its level.
    It never takes more than their air then holds, and its waste heat
    warms them.
  - **Condensation:** air holds no more than saturates it. Beyond that,
    the water condenses, on the cold glass, and is counted. This is
    checked every 10 simulated seconds rather than every step.
  - **Glass passes no water.**
- **The climate field** publishes the relative humidity (`humidity`, %).
- **The climate box:** its settings gain a damp night, 90% outside and 85%
  inside to start.
- **The dehumidifier re-rated:** at 5 kg/h, it dried the box's 368 kg of
  air, holding 3.5 kg of water, to nothing within the hour. It now takes
  1 kg/h and gives 1.2 kW: the latent heat of the water it condenses,
  0.7 kW, plus its compressor's.
- **In the climate box,** ten minutes in:
  - unheated, the house cools to 9 °C and saturates;
  - beside the running dehumidifier the air is at 87%, at 73% with the
    heater on too, against 96% in the far corner.

  An hour with the fan, heater and dehumidifier on takes about 4.5 s.

### P05.5: Vents and the airflow boundaries

An open vent's exchange with the outside, from its aperture area, and its
draught, by the stack effect's direction. Visible result: moving a roof
vent's slider changes the air at the vent, in the arrows and in the slices.
Tests: a closed vent exchanges nothing, and the exchange grows with the
aperture area the geometry gives. With the outside cooler, an open vent
cools the house towards it.

#### As implemented

- **A vent's cells:** those against the face of the grid the CFD geometry
  puts it on (`CfdGeometry.opening_cells`), with which way is out. A roof
  vent's are under the ceiling at the eaves.
- **The exchange** (`climate.vents`): 0.3 m/s through its aperture, as much
  in as out. It mixes the outside's temperature and water into those
  cells, shared evenly. Closed, it exchanges nothing; part open, its
  aperture's share.
- **The draught** shows in the climate's velocity, so the arrows respond.
  It goes through the cells' faces at the speed that carries the exchange:
  out when the air against it is warmer than the outside's, in when it is
  cooler. It is drawn, not carried: the exchange already mixes the air.
- **Field requests** take the openings as scene requests do
  (`fields/climate?open=roof_vent:1`). The viewer asks for the climate
  with the Openings sliders' values.
- **In the climate box,** heated, ten minutes in: opening the roof vent
  cools the house's mean from 15.5 to 13.6 °C, and 0.29 m/s goes out
  through it. Unheated, it lets the outside's drier air in.

### P05.6: Actuator schedule timeline

Scheduled commands and manual overrides in one log; a timeline of markers
under the time slider. Visible result: a short run where the fan, heater and
dehumidifier switch on their own, and the field maps respond. Tests: a
schedule replays to the same air, and an override takes effect from its
moment on.

#### As implemented

- **The schedule in a request:** `fields/climate?set=heater:1&schedule=300:heater:0`
  carries commands at their moments after the levels set from the start,
  the later winning at a moment.
  - **Refused, with the reason:** equipment the scenario lacks, a level
    outside 0 to 1, a moment outside the run's hour, or a command not
    written seconds:actuator:level.
  - **Kept runs** are found by their schedule too.
- **Overrides are commands:** in the viewer, equipment switched while the
  run stands past its start becomes a command at that moment. It replaces
  any command to the same equipment then. At the start, switching sets the
  levels from the start.
- **The moment drawn:** the Equipment panel and the scene show the levels
  then.
- **"Schedule"** lists the commands under the time slider, marked on a bar
  over the run and filled once applied, each to go to or take out. The
  log is the schedule: what a run has applied by a moment is its commands
  up to then.

### P05.7: Actuator comparison dashboard

Fixed probes, time-series charts of temperature, relative humidity and air
speed, and the same run with all equipment off, side by side. Visible
result: the controlled and uncontrolled runs diverge where the equipment
acts. Tests: the charts' values are the probes' values at each time.

#### As implemented

- **The readings** (`climate.probes`):
  `GET /api/scenarios/{id}/climate/probes?probes=10.5:1:0.75,…&set=heater:1&t=600`.
  - **What:** each probe's temperature, relative humidity and air speed,
    every minute up to the moment asked, as the run's published field
    samples them, so a chart reads exactly what a probe does.
  - **Against what:** the same run with all its equipment off, its doors
    and vents as asked.
  - **Asked and refused** as the climate field is. A probe outside the
    house's air is refused too.
- **The charts:** "Probe charts", plain SVG, three a probe:
  - this run's line solid, the all-off run's dashed, across the run's hour;
  - a faint line at the moment drawn, and what both read then.
- **A run keeps its air every minute** on the way to any moment, so the
  charts, and moving back along the time slider, find each minute kept:
  reading two probes for twenty minutes with the fan on takes 0.4 s after
  the field. Where water condenses is checked at each minute's end too.
- **In the climate box,** heated, ten minutes in: 31.88 °C beside the
  heater against 9.01 °C all off, and 14.96 against 9.13 across the house.

## Final QA: `climate-actuators`

At runtime:

- toggle the fan;
- vary the heater's power;
- toggle the dehumidifier;
- open and close the roof vent;
- watch the vector field, and the temperature and humidity slices;
- inspect fixed probes and their time-series charts.

Expected:

- the fan changes the air's direction and speed near it;
- the heater warms the air;
- the dehumidifier dries it;
- the vent changes the air at its boundary;
- replaying the same schedule reproduces the run exactly.

### As run

The browser test `e2e/climate-actuators.spec.ts` runs it in the climate box
(8 °C outside, 16 °C to start), with probes in the fan's core, beside the
heater, beside the dehumidifier and under the roof vent. Every expectation
holds:

- **The fan:** switched on, the air moves at up to 4.81 m/s, 4.34 m/s along
  the fan's axis in its core; switched off, it is still again.
- **The heater:** ten minutes in, beside it the air is at 31.88 °C at full
  power, cooler at half, and below 10 °C unheated.
- **The dehumidifier:** switched on too, it dries the air beside it by more
  than 5 points of relative humidity in ten minutes.
- **The roof vent:** opened, a draught of over 0.2 m/s goes out through it
  and the air under it cools; closed again, the air is as it was.
- **The views:** the arrows, then the temperature and humidity slices, each
  with its legend.
- **Probes and charts:** four probes, three charts each, a line for the run
  and one for the run all off; the charts read what the probes read.
- **Replay:** reloading the same address gives every probe's reading again,
  digit for digit.

## Acceptance criteria

- [x] **Device state is visible and inspectable:**
  - each piece of equipment is drawn grey when off and in its kind's colour
    when running;
  - it is selectable, and the inspector shows its level and rating;
  - the Equipment panel and the schedule show every level at the moment
    drawn.
- [x] **Device effects reach the air only through the source-term
  contract:** a climate run's flow, heat and water come from
  `climate.sources` and nothing else (`tests/test_climate_field.py`).
- [x] **No actuator requires a specific CFD engine:** the climate run is
  NumPy on the field's grid. The CFD geometry only says where obstacles and
  vents lie.
- [x] **Visual and numerical probes agree on the direction of change:** the
  charts read what the probes read, at every minute
  (`tests/test_climate_probes.py`, `e2e/probe-charts.spec.ts`).

## Known approximations

What P05 simplifies on purpose, kept here until a later step removes it:

- **The flow is the nearest conserving one, not a solved one:** the base
  airflow plus the fans' jets, with their divergence projected out
  (P05.3). It has no momentum of its own, so the air does not accelerate
  or decay in time, and a fan's jet takes effect at once.
- **No buoyancy:** warm air does not rise. The run's effective mixing,
  0.1 m²/s, folds in the convection it does not carry.
- **The floor passes no heat:** it is not glass, and the ground's heat is
  P08's.
- **Condensation's latent heat is not counted,** and the glass passes no
  water. Condensed water is counted and gone.
- **A dehumidifier takes its rating whatever the air:** only the water
  there caps it, where a real one takes less as the air dries and cools.
- **A fan's jet is a free jet:** it does not turn at walls or flow around
  obstacles. It stops at the grid's faces and adds nothing inside an
  obstacle's cells, but nothing in its wake is shadowed.
- **The outside is fixed**: one temperature and humidity for a run, until
  P07 brings weather.
- **Vents exchange air at a constant speed through their aperture**, its
  direction by the stack effect only, until P07 brings wind. The exchange
  is as much in as out, so the flow inside is not driven by it; the draught
  is drawn, not carried.
- **Plants don't feel the air yet:** they keep their daily, greenhouse-wide
  climate until P07/P09 feed them the air where they stand.

## Review decisions (7 October 2026)

1. **The air's own clock:** agreed. The crop keeps its daily climate in
   P05, and feeding it the local air is deferred to P07/P09.
2. **Fan jets by superposition:** acceptable for v1, and tracked under
   "Known approximations" until a projection replaces it.
3. **Scenarios:** retire the original scenarios and build new, more
   relevant ones, `climate_box` among them (section 7). Their design comes
   first, for review (P05.0, reviewed).
4. **Equipment in layout files:** agreed.
5. **A fixed outside and a constant vent exchange speed until P07:**
   agreed.
6. **The envelope exchanges heat both ways** (section 5): it loses heat
   when the outside is cooler, and gains it when the outside is warmer.
