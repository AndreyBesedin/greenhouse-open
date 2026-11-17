# P24: A house's components, and a climate that carries them

**Status:** proposed, not started: the steps below, with decisions
[0078](../decisions/0078-a-multi-node-climate-is-a-model-of-the-houses-air-chosen-by-the-manifest.md),
[0079](../decisions/0079-a-crop-and-the-houses-air-exchange-heat-water-and-co2-by-what-each-declares.md)
and
[0080](../decisions/0080-a-houses-components-and-materials-are-described-in-its-installation.md),
proposed. It follows item 6 of the [research priorities](research-validation-priorities.md),
the Modelica comparison. Part of the [simulator roadmap](README.md).

## Goal

The simulator carries the equipment, materials and practices that growers use and
that greenhouse climate models in Modelica and elsewhere describe: thermal, shading
and blackout screens, glazing of several kinds, floors and the soil under them, pipe
heating, walls that face a corridor or another house, and a crop that transpires
into the air it grows in. A house's setup is described once, in its installation,
in terms a modeller can write to and read from TiGwerLib's or GreenLight's
parameters. On matched inputs, the simulator closes the gaps the first comparison
with TiGwerLib found, or the comparison says which remain and why.

## Where it starts

- **The first comparison** ([`research/modelica`](../../research/modelica/README.md#comparing-the-simulator-with-tigwerlib)):
  the simulator's whole-house air temperature against TiGwerLib's (Sourisseau et al.
  2026), reproduced in OpenModelica, on matched weather, geometry, roof windows and
  heating, over 11 days of January and 11 of July 2015. The bar, stated before the
  runs, is a day's RMSE of the difference of at most 1.6 K. No day of either window
  meets it. In January the simulator runs 4.2 K colder on average and 5.7 K colder
  at night, an RMSE of 5.20 K over the window; in July it runs 3.7 K warmer by day,
  an RMSE of 3.57 K over the window, while July's nights agree to 0.66 K.
  - **The blockers it recorded:** thermal and shading screens; the crop's exchanges
    with the air (transpiration, convection, radiation); the heat stored in the
    floor, soil, structure and crop; the roof's longwave exchange with the sky; and
    walls that face corridors at their measured temperatures, or nothing, where the
    simulator's four walls are glass to the outside (937 m² of glass where
    TiGwerLib's one outside wall has 177 m²). The relative humidity was not
    compared, since the simulator's air takes no water from a crop.
  - **The known differences** (inputs matched, models different): De Jong's
    ventilation function against the simulator's orifice flows; the leakage laws;
    how direct and diffuse light are split and transmitted; where the heaters'
    heat goes; the air's volume; and the roof's glazed area taken as its projection.
- **Apportioning the gap among the blockers** is research of its own under item 6:
  TiGwerLib run with each blocker taken out in turn. Its ranking orders this
  project's components (P24.1). P24 does not wait for it: its order below is
  provisional, by the impact each component is expected to have.
- **The simulator's climate today** (`greenhouse_sim/climate/`):
  - the house's air as one well-mixed volume (`house.py`, the house air part's
    `whole_house` model), solved exactly between moments, each loop of the
    controller switched at the moment its edge is reached (decision
    [0058](../decisions/0058-a-climate-controller-switches-each-loop-at-its-edge.md));
  - the air cell by cell beside it (`run.py`, `transport.py`, the `grid` model,
    the default), started from the whole house's air and following its decisions;
  - glass with no heat capacity, its U set by the wind (`glazing.py`); doors and
    vents passing air by the wind and the stack (`openings.py`, `vents.py`); a
    house that leaks at a rate (`settings.py`); equipment as source terms
    (`sources.py`); moist air (`psychrometrics.py`);
  - the sun and the sky's light, split by Erbs's correlation and traced through
    the glass and what shades it (`greenhouse_sim/solar/`); the weather, recorded
    or synthetic (`greenhouse_sim/weather/`), with no sky temperature and no
    measured diffuse light.
- **Its parameters are the model's, not the house's.** Glazing U and infiltration
  are the house air model's (`climate` section of a manifest). The installation
  (decision
  [0050](../decisions/0050-an-installation-is-the-house-part-of-a-scenario.md))
  holds the envelope, the layout and the rows' crops: a fixture names a material
  (steel, aluminium, plastic, concrete, substrate) for what it obstructs, not for its
  heat or light.
- **A reference for each component.** GreenLight 2.0.7 runs its own greenhouse in
  the research environment
  ([`research/integrations/driver_profiles`](../../research/integrations/driver_profiles/README.md),
  [`research/reproductions/vanthoor_katzin`](../../research/reproductions/vanthoor_katzin/README.md)).
  Vanthoor's (2011) climate model, as Katzin (2021) extends it, has a thermal and a
  blackout screen with the compartment above them, a cover, a floor over soil
  layers, pipe rails and grow pipes, a transpiring canopy and the sky as a boundary.
  TiGwerLib runs in OpenModelica beside it ([`research/modelica`](../../research/modelica/README.md)),
  with its corridors and De Jong's ventilation.
- **The crop reads the air, one way.** Decision
  [0062](../decisions/0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md)
  lets a crop model declare fluxes it gives the air, and leaves the house's taking
  them to a climate decision of its own. The first driver profile, `house_hours`,
  gives Vanthoor's model the air's temperature for its canopy's.

## When

After the first comparison, as item 6's next work, beside
[P20](p20-crop-parameter-assets.md) and [P23](p23-experiments.md). It touches the
house air part, the installation's format, the weather's quantities and the crop's
ports; not P20's parameter sets or P23's runner. P24.2 and P24.3, the description
and the model's frame, come first whatever the apportioning finds; the components
after them follow P24.1's order.

## What stays stable

- **Today's models:** `grid` and `whole_house` keep their equations, versions and
  numbers, and `grid` stays the default. A packaged scenario's run id, seed,
  checkpoints and replay digests do not move: a component left undescribed writes
  nothing into a manifest.
- **The one-way crop:** a crop model that declares no exchange with the air, and
  every run whose manifest chooses none, runs as it does today, under `house_hours`.
- **The controller:** its loops read the house's air and switch at their edges, as
  decision 0058 has them, whichever house air model runs.
- **The first comparison's record:** its statement and its two reports stay as
  committed. Each later comparison is stated anew, before its run, and keeps the
  first's windows, bar and matched inputs.
- **No Modelica in the packages.** Nothing in `greenhouse_sim`,
  `greenhouse_protocol` or `greenhouse_adapters` imports, runs or needs Modelica,
  OpenModelica, GreenLight or TiGwerLib. They run as references under `research/`,
  apart, as they do today.

## Design

### A house's components, described (decision 0080)

The installation describes what a house is made of and what it has, as a grower or
a modeller would list it; a climate model reads that description. Its parameters
keep only how the model computes.

- **The cover:** each surface's material (the roof's, each wall's), from a
  catalogue of named materials (single glass, diffuse glass, double glass, twin-wall
  polycarbonate, polyethylene film), or given by its properties: shortwave
  transmittance, beam and diffuse; longwave emissivity and transmittance; its
  thickness, conductivity and heat capacity. Each property has its unit, source and
  range in the schema, as P20's parameters do. A described cover gives `grid` and
  `whole_house` their U and transmittance too; a manifest that gives both a cover's
  material and `glazing_u_w_m2k` is refused, naming both.
- **Each wall's boundary:** the outside (the default), a neighbouring space at a
  temperature (a corridor, a headhouse, another house), constant or recorded, or
  nothing (no heat crosses it). A recorded temperature is a file of its own,
  digested into the run's identity as a recorded weather is.
- **The floor:** its surface (concrete, soil, a white film), its layers down to a
  depth, each with its thickness, conductivity, density and heat capacity, its
  shortwave reflectance and longwave emissivity, and the deep soil's temperature.
- **Screens:** each thermal, shading or blackout screen, its material
  (transmittances, emissivity, air permeability, heat capacity), its height and
  extent, and its drive: a device with a level from 0 (open) to 1 (closed), which
  commands and a screen loop run.
- **Heating:** a pipe network (rail pipes, grow pipes, perimeter pipes) as a kind
  of equipment: its pipes' length, diameter, height and emissivity, and how its heat
  leaves, by convection to the air and by radiation to what it sees. A unit heater
  stays a heater that warms the air.
- **Refused, not ignored:** a model that cannot model a described component refuses
  the house, naming it, as a run refuses rows of crops it cannot grow.
- **In the builder:** each component is placed and edited in the builder from the
  installation's published schema, as its envelope and items are.

A named material's values never change once published, as a published parameter set's
do not (decision 0077): a correction is a new name.

### A multi-node climate (decision 0078)

A third model of the house air part, `vanthoor`, version 1, beside `grid` and
`whole_house`, chosen by the manifest
([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)).
It is named after its source, Vanthoor's (2011) model, and documents where it
departs from it: its default ventilation law, TiGwerLib's walls, and the house's own
description.

- **Its nodes** follow the house's description: the inside air (its temperature,
  water and CO₂); the air above a drawn screen; the cover, which holds the
  structure's heat with its own; each screen; the canopy
  (decision 0079); the floor and its soil layers, down to the deep soil; each pipe
  network. The outside air, the sky, the deep soil and each neighbouring space are
  its boundaries. A house without screens has no screen node.
- **Its equations** are Vanthoor's (2011), as GreenLight implements them (Katzin
  2021), each flux with its source; TiGwerLib's (Sourisseau et al. 2026) where a
  component is its own, such as walls on corridors. They are written from the
  publications, not ported from code.
- **The sky** is the weather's: a recorded sky temperature or downward longwave
  radiation where the weather has one, or else one estimated from the air, its
  humidity and the cloud cover by a named formula. The weather gains those
  quantities, and a measured diffuse radiation, as optional fields; the protocol
  gains them as outside observation types.
- **Its solver:** over each stretch, at most the weather's minute, the equations
  are linearised about the stretch's start (radiation's fourth powers,
  transpiration and the ventilation's terms by their tangents) and solved exactly,
  by the matrix exponential. A stretch is halved while the linearisation's error,
  the nonlinear rates against the linear ones at its end, exceeds a stated bound.
  On that exact course, each loop's edge is found by bracketing and halving, as
  decision 0058 has it. The same inputs give the same numbers, with no step history
  to keep: a checkpoint keeps each node's state, and the loops', at the two moments
  a whole house's checkpoint keeps today. A general stiff solver (scipy's BDF, as
  GreenLight solves) at tight tolerances is its check, in the tests, not its
  method.
- **Its geometry:** the cover's own area, its roof's slopes and not their
  projection, and the envelope's exact volume.
- **Its limit:** with no screen, canopy, floor or pipes, a massless cover, the sky
  at the air's temperature, and the whole house's area and volume, it gives the
  whole house's numbers, which a test holds.
- **Its cost:** today's whole house takes about 7 minutes for an 11-day window,
  most of it outside the air's equations. The budget, measured on the
  comparison's machine: the multi-node model's own work under 1 s per simulated
  day, and an 11-day window end to end in at most 1.5 times today's, so that a
  season, and an experiment of many episodes, stays practical. P24.3 measures where
  today's 7 minutes go before it adds anything.
- **Beside the grid:** it draws its air the same in every cell, as the whole house
  does. A grid beside it, started from its air with its cover's, screens' and
  floor's temperatures as the cells' boundaries, is left for later.

### The crop and the air, both ways (decision 0079)

- **The canopy is a node of the climate**, where a model has one: its temperature,
  its transpiration (Stanghellini's, as Vanthoor's), its convection and its
  radiation with the cover, the pipes, the floor and the sky are the climate's.
- **The crop gives the canopy its leaf area,** per m² of floor, and takes the CO₂ its
  assimilation declares from the air. Each is a typed port a crop model declares,
  held through the crop's step, in its units; a model that declares neither is not
  coupled. The organ crop gives its plants' leaf area, each leaf's from its length
  and its plant's form, summed over its scope, and takes no CO₂.
- **Or the canopy is prescribed:** the house air's parameters give a leaf area, a
  constant or a recorded series, so that a comparison can match the reference's, and
  a crop that does not couple can still stand in a house that transpires. The
  manifest says which: no canopy, a prescribed one, or the crop's.
- **The crop reads its canopy back** through a driver profile of its own,
  `house_canopy`, version 1, which gives the canopy's temperature and substitutes
  nothing. `house_hours` stays.
- **In turn, at the crop's step:** the climate runs the step with the crop's leaf area
  and uptake held from the step before, then the crop steps on the climate's
  means. The split's effect is measured against GreenLight's coupled solve.
- **Conserved:** the water transpired is the water the air takes, less what
  condenses; the CO₂ the air loses is what the crop gains; tests hold both.

### Known differences: options, or deliberate

| Difference | Proposed | Why |
| --- | --- | --- |
| Ventilation: De Jong's function against the orifice flows | An option of `vanthoor`'s: `orifice` (today's, its default), `boulard_baille` (after Boulard and Baille, as Vanthoor and GreenLight) or `de_jong` (as TiGwerLib) | Each is a published law with its own range of validity; a comparison chooses its reference's |
| Leakage: power laws against a rate | An option: `rate` (today's, its default) or `power_law`, by the pressure across the cover | TiGwerLib's corridors leak by the pressure, which a rate cannot say |
| Light: measured diffuse against Erbs's split | A weather that records diffuse radiation is read as measured; Erbs's split stays for one that does not | A matched input, not a model's choice |
| Light: transmission | Deliberate: the simulator's ray tracing through the cover's material stays; the material gives the transmittances a reference uses | The geometry is the simulator's own strength; the numbers are matched through the material |
| Where the heaters' heat goes | A component: a pipe network gives its heat by convection and radiation; a unit heater warms the air | Not a difference of law, but of equipment |
| The air's volume | `vanthoor` takes the envelope's exact volume; the grid's cells stay the grid's, documented | The grid's volume is its resolution's |
| The roof's glazed area taken as its projection | `vanthoor` takes the slopes' own area; `whole_house` keeps its projection, documented | Changing it would move every whole-house run |

### Setups in step with TiGwerLib and GreenLight

An installation is written to, and read from, TiGwerLib's and GreenLight's
parameters, by a mapping that names each field's counterpart, its conversion of
units, and the fields with none on either side, which it reports rather than
drops. It lives under `research/`, where the references run, until a package needs
it. The comparison's harness then builds its house through it, so that both sides
are given one description.

### How a component is accepted

Each component is held, first, to its reference on the same inputs: its fluxes
against GreenLight's at the same states, as Vanthoor's crop was, and a run of
GreenLight's greenhouse with the component and without; TiGwerLib's where the
component is its own. Then the first comparison runs again, in a pull request of
its own: the same windows, the same 1.6 K bar and the same matched inputs, with the
inputs the new component needs (a screen's closure, a corridor's temperature, the
canopy's leaf area) read from TiGwerLib's records and stated before the run. No
parameter is set to meet the bar. Its report is committed as written, and a table
in [`research/modelica`](../../research/modelica/README.md) records the progress: the
days within the bar, the RMSE by day and by night, for each window, at each step.
Once the canopy transpires, the air's relative humidity is reported beside its
temperature, with no bar. P24 sets no number of days within the bar as its target:
it is done when its steps are, and the table says how far they took the comparison.

### Licences

TiGwerLib is MIT; GreenLight is BSD 3-Clause Clear, with no patent grant; the
Greenhouses library is BSD 3-Clause. Each permits porting with its notice kept.
P24 writes its components from the publications' equations, and runs the
references apart, as the research does; anything ported beyond an equation keeps
its source's notice, and is named where it is used. The data the comparisons read
stay fetched, never committed (decision
[0063](../decisions/0063-a-data-file-is-generated-committed-or-fetched-by-one-rule.md)).

### What it leaves

- **Lamps**, and the CO₂ and light targets that would run them (future work).
- **A grid beside the multi-node model.**
- **Energy, CO₂ and crop yield compared with TiGwerLib:** the first comparison's
  scope stays the air's temperature, and its relative humidity once the canopy
  transpires.
- **Calibration:** nothing here fits a parameter to a window. A calibrated house is
  a research result, as decision 0076's crop sets are.
- **A replacement for Modelica,** an FMI or FMU link, or Modelica in any package.

## Steps

Each step is a pull request, or two where it says so. From P24.3 on, a component's
step is followed by a pull request of the research's that runs the first comparison
again, and the step is done when that run is recorded. The order of P24.4 to P24.9
is provisional, by the impact expected: stored heat, the thermal screen and the
walls for January's nights, the canopy and the shading for July's days.

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P24.1 | **Ordered by the apportioning:** once the research's apportioning of the first comparison's gap lands, P24.4 to P24.9 are put in the order of the share each blocker carries, in this document | Each step's place cites the share its blocker carries, and the document says what moved | Proposed |
| P24.2 | **Components described** (decision 0080), in two pull requests: the installation's schema gains the cover's materials, each wall's boundary, the floor and its layers, screens and pipe networks, with the catalogue of named materials; then the weather's sky temperature, longwave and diffuse radiation, as optional fields and outside observation types. `grid` and `whole_house` refuse what they cannot model, naming it | An installation with every component reads back the same; a value outside its range is refused by field; a house with a screen run under `whole_house` is refused, naming the screen; no packaged run id, checkpoint or replay digest moves | Proposed |
| P24.3 | **The multi-node model's frame** (decision 0078), in two pull requests: `vanthoor` registered with the inside air, the cover and the sky, the cover's own area and the envelope's volume, its solver, its edges, its checkpoint and its replay, and today's 7 minutes measured; then the floor and its soil layers | Its fluxes agree with GreenLight's at the same states; its course agrees with scipy's BDF at tight tolerances within a stated bound; at its limit it gives the whole house's numbers; a run is the same when repeated and resumed; its cost is within budget; the comparison is run again and recorded | Proposed |
| P24.4 | **The thermal screen,** with the air above it, its material, its drive and a screen loop | Its fluxes agree with GreenLight's; a screen closed at night keeps the air warmer than none, as GreenLight's does; the comparison is run again, the screen closed as TiGwerLib's records close it, and recorded | Proposed |
| P24.5 | **Walls' boundaries:** a wall on a neighbouring space or on nothing | A wall on nothing passes no heat; one on a space at the air's temperature passes none either; agreement with TiGwerLib's corridors on the same temperatures; the comparison is run again, the corridors at their measured temperatures, and recorded | Proposed |
| P24.6 | **The canopy, both ways** (decision 0079), in two pull requests: the canopy as a node, prescribed, with its transpiration and condensation on the cover and screens; then the crop's ports, Vanthoor's model, Reduced-State TOMGRO and the organ crop giving their leaf area and Vanthoor's its uptake, read back through `house_canopy` | Its fluxes agree with GreenLight's; water and CO₂ are conserved; a crop that does not couple runs as before; the comparison is run again with TiGwerLib's leaf area prescribed, its relative humidity reported beside its temperature, and recorded | Proposed |
| P24.7 | **The shading and blackout screens,** each with its material and its drive | Their light and heat agree with GreenLight's (blackout) and TiGwerLib's (shading); the comparison is run again, the shading drawn as TiGwerLib's records draw it, and recorded | Proposed |
| P24.8 | **Pipe networks:** pipes as nodes, their heat by convection and radiation, given the heat a record gives or the water's temperature | Their split agrees with GreenLight's pipe rail's and grow pipe's; the heat given over a window matches the record's as the first comparison's does; the comparison is run again and recorded | Proposed |
| P24.9 | **Known differences as options:** the ventilation laws (`boulard_baille`, `de_jong`), power-law leakage, and measured diffuse light read | Each law agrees with its reference on the same openings and weather; the defaults change no run; the comparison is run again with TiGwerLib's choices, and recorded | Proposed |
| P24.10 | **Setups in step:** an installation written to TiGwerLib's and GreenLight's parameters and read back, the fields with no counterpart reported; the comparison's harness builds its house through it | An installation written and read back is the same in every field mapped; the comparison's house built through the mapping gives the numbers it gave | Proposed |
| P24.11 | **In the builder:** every component placed and edited from the published schema, the materials chosen from the catalogue, a house without a component's model refused in words | A browser test describes a screen, a wall on a corridor and a floor, and runs the house under `vanthoor` | Proposed |
| P24.12 | The QA scenario below, run and recorded | Each step passes as it says | Proposed |

## QA scenario (proposed)

In the builder: describe TiGwerLib's house, its cover's glass, a wall on each
corridor, a concrete floor over soil, a thermal and a shading screen, two pipe
networks and a crop, and run it under `vanthoor` for a winter week. The screens
close as their loop says, the floor holds the day's heat into the night, and the
crop's transpiration shows in the air's humidity. Run the same house under
`whole_house`: refused, naming what it cannot model. Write the house to GreenLight's
parameters and read it back: the same house, the fields with no counterpart listed.
Run the first comparison once more, from its statement, and read the progress
table: each step's days within the bar and its RMSE, by day and by night.

## Open questions

None: the questions it was proposed with are answered in its design and in
decisions 0078 to 0080. The solver linearises stretches and solves them exactly; the
budget is under 1 s per simulated day and 1.5 times today's window; the model is
named after its source, `vanthoor`; its default ventilation law is the simulator's
orifice flows; the canopy's balance is the climate's, coupled at the crop's own step,
the organ crop by its plants' leaf area; 0080 stands apart; a described cover gives
every model its glass; a neighbour's record is a file of its own; the mapping lives
under `research/`; the relative humidity is reported with no bar; and P24 records
its progress with no target number of days.
