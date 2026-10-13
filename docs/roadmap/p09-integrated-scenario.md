# P09: Integrated greenhouse scenario, replay and release QA

**Status:** in progress. Part of the [simulator roadmap](README.md).

## Goal

Join the projects into one coherent visual simulator release, and show
that its parts exchange state through their contracts rather than through
hidden shortcuts: one modest reference greenhouse in which a crop grows in
the air the equipment, the weather and the sun make, watched by sensors and
a camera, on one clock, that can be saved, branched and replayed.

## Dependencies

P00–P08, all done. The organ-level crop (P03), the climate and its
equipment (P04, P05), the sensors and cameras (P06), the weather (P07) and
the sun (P08) each work on their own; P09 runs them together.

## Direction

- **One clock.** A run's moments are seconds from its start, its start
  date's midnight at its site (P07.1). The crop's days are that clock's
  days. Every process, the air's stretches, the plants' days, the sensors'
  samples, the cameras' frames and the commands, happens at a moment of it.
- **State crosses through the contracts.** Plants take their days through
  the `Environment` contract (decision 0024); sensors report through the
  observation path; truth leaves only by its own (`ground_truth`,
  `evaluation`). No process reads another's internals.
- **The fidelity ladder stays.** The house's air as one well-mixed volume
  through the whole run, and the air cell by cell drawn when a moment's
  field is asked for, as P07.3 does through a day.
- **Reproducible by construction.** Every draw is seeded by the scenario's
  seed, the process, the subject and the index, as sensors' are
  (`sensors/air.py`), so a moment reads the same whether it is reached
  directly, after another, after a restore or in a branch.
- **A modest world, as data.** The reference scenario is a file, not code,
  small enough to run on a laptop and complete enough to exercise every
  subsystem.

## Design

### Where things stand

- **Scenarios are code.** Each is a `ScenarioConfig` in a Python module,
  registered in `scenarios/__init__.py`; its layouts are JSON files
  (decision 0020), its weathers presets by name.
- **Two clocks.** The engine and the live run advance a scenario's crop a
  day at a time with the simple daily tomato model, drawn as stems. The
  climate, sensors, cameras, weather and sunlight run on seconds from the
  start, for at most a day (`LONGEST_RUN_S`). `services/sensors.py` and
  `solar/plants.py` both leave joining the two to P09.
- **The organ-level crop grows only in the plant lab:** 20 plants, in a
  preset or in sunlight, with pruning, harvesting and lowering scheduled
  by day. No scenario has it.
- **Each plant's light** (P08.6) is computed with crowns as tall as the
  first day's plants.
- **Checkpoints keep only the latest world** per greenhouse
  (`InMemoryWorldCheckpoints`), which leaves rewinding and branching "until
  something needs it". A climate run already carries on from another's air
  up to the first command they differ in (`carry_on_from`).
- **Truth leaves by its own path,** and the sensor lab compares readings
  with it. Cameras' frames, RGB, depth and an instance pass, are drawn on
  demand.
- **The climate box is most of a reference world already:** a fan, a
  heater, a dehumidifier, air, CO₂ and PAR sensors, a camera and a weather
  station, and 32 plants, in one span.
- **Visual QA:** QA pages compared in CI's pinned container (decision 0014)
  for the renderer, shell, layout, airflow, plants and sun; every project
  has its final QA as a browser test. The renderer is benchmarked locally on
  a graphics card (decision 0015).
- **Starting it** takes two commands, the API and the viewer's development
  server.
- **Measured on a laptop:** the whole house's air through a day takes 0.1 s
  (climate box) to 0.6 s (solar lab, in sunshine); every plant's light
  through a day, 0.06 s for 16 plants; the plant lab's 20 organ-level
  plants to day 90, 0.9 s and 10,400 entities. In the lab's reference
  environment, a plant's first fruit starts to ripen between days 60 and
  70 and is red by day 80; by day 120 it has 17 red fruits and a stem of
  2.5 m, by day 180, 48 and 3.7 m. Growing one plant to day 180 takes
  0.08 s. Its structure as JSON is 20 KB at day 60 and 41 KB at day 120;
  32 plants at day 80 take 960 KB, 162 KB gzipped.

### 1. The reference scenario, as a manifest (P09.1)

`reference_greenhouse`, version 1, described by
`scenarios/manifests/reference_greenhouse.json` against a JSON Schema
generated from the model that reads it, as the layouts' is:

- **What it refers to:** its envelope, its layout file, its weather, its
  site, its crop (variety, model, rows and plants), its equipment and
  sensors (in the layout), its commands, and its models' choices: the
  airflow, the climate's fidelity, the plant model, the sensor model.
- **How it runs:** its seed, its start date, its duration, and
  `schema_version`, the manifest format's version, which a reader refuses
  if it does not know it.
- **The world:** a three-span Venlo-style house, 12 by 9.6 m, 4 m to the
  gutters, a roof vent along each span and a door in the front gable; four
  rows of eight plants (32) on hanging gutters, with pipe rails between
  them and a path across the front; two fans, a heater and a dehumidifier;
  air, humidity, CO₂ and PAR sensors at crop height; a weather station
  outside; one fixed RGB-D camera along a path. Synthetic weather at the
  default site from 1 March 2026 for 120 days, so that March nights need
  heat, June days need venting, and the crop bears red fruit for its last
  month or more. Seed 42.
- **Its crop work:** a harvest round once a week, from the first red fruit,
  picks every red fruit, so that ripe fruit does not pile up and each
  plant's history records its harvests; and a lowering round once a week
  keeps each plant's top under its wire, as a high-wire crop is lowered
  (review decision 9). Like the commands, the crop work is the run's, not
  the world's.
- **Every scenario becomes a manifest,** in one format. Before the
  conversion, each scenario's configuration is written out by its code, and
  a test holds the manifest's to it, field by field, so that no scenario
  changes. Their Python modules go; the registry lists the manifests.

### 2. One clock, and a timeline (P09.2)

- **A run** is a scenario, its changes and its commands. Its moments run
  from 0 to its duration, in seconds; `&t=` in the viewer's address and the
  API's routes means the same throughout, no longer capped at a day.
- **Processes and their cadences:** the house's air in stretches of at most
  a minute (P05.3); each plant's day at each midnight, from that day's air
  and light; each sensor's samples and each camera's frames at their own
  `cadence_s`; each command at its moment; each crop action (prune, harvest,
  lower) at the start of its day, as in the lab.
- **Order within a moment:** commands, then the air, then the plants, then
  the sensors, then the cameras, so that an observation at a moment sees
  what changed at it.
- **The timeline** lists every event in a window of the run, by process,
  subject and kind. It is enumerated from the cadences and commands, so it
  costs nothing to keep. The viewer shows it as a panel of lanes, one per
  process, zoomable from a day to a minute.
- **Commands through days:** a schedule may repeat daily, so that a heater
  can run every night and the vents open every afternoon.
- **Test:** over a fixed day, each plant has one day, each sensor
  `86 400 / cadence_s` samples, each camera its frames, and each command one
  event; and the same events in the same order on every run.

### 3. The crop in the climate (P09.3)

- **The reference scenario's plants are the organ-level model's,** each at
  its planting position, its traits drawn from the scenario's seed, as the
  lab's are from the lab's. The other scenarios keep the simple model, so
  their recorded numbers and baselines do not move.
- **Each plant's day** is a `LocalEnvironment` from the run: the house's
  mean air temperature and CO₂ through the day, the plant's own daily light
  integral (P08.6), and water status 1, since nothing yet models the
  irrigation.
- **The crowns grow:** each day's light is computed with the crowns as tall
  as that day's plants, so a tall row shades its neighbours more as the
  season goes on.
- **The coupling is recorded:** each plant's environment, day by day, is
  served beside its structure, and the inspector charts it.
- **Visible result:** plants in different places diverge over an
  accelerated season: the row ends, open to more sky, grow ahead of the
  middle ones; and from the first harvest round, each plant's history
  lists the fruits picked from it.

### 4. Equipment, weather and sensors through the season (P09.4)

What P05–P07 joined within a day now runs through the season: the commands
change the air, the weather and the sun change it more, and the sensors
observe it, every sample through the observation path. A test checks that
the reference scenario's observations are derived only from the run's
state, and that nothing on their path reads truth (extending
`greenhouse_sim/tests/test_sensor_observations.py`). Visible result: a
heater, fan and vent schedule changes the field overlays and the sensors'
charts, day after day.

### 5. Checkpoints, branches and replay (P09.5)

- **A checkpoint** is taken at a day's start: the run it belongs to (the
  manifest's identity and version, its changes and commands so far), the
  plants' structures, and the house's air. Nothing else needs keeping:
  sensors' and cameras' draws are seeded per sample, the weather and the
  sun are functions of the moment, and the air cell by cell is drawn again
  from the house's.
- **What one is for.** Runs are deterministic, so a checkpoint never
  holds anything its run could not compute again. It saves the time to get
  there, about 0.7 s a simulated day, and it lets a run carry on from a
  state on another machine, or after the code has changed.
- **Made while viewing, kept in the API's memory.** Saving one returns its
  identifier; the viewer lists them, restores one and branches from it;
  any can be downloaded as a JSON file and uploaded again. Restarting the
  API forgets them, and the API writes no file. The alternative, a folder
  the API manages, would keep them across restarts, but would make a local
  server write files on request, and name, clean up and confine them.
- **Kept in the repository: the reference run's opening day.** The first
  day with red fruit, expected around day 80, is kept gzipped (about
  160 KB) beside the manifest, which names it as where the viewer opens.
  The days before it are not computed again unless asked for; the later
  ones are computed as the run plays. A test replays the run from day 0 to
  that day and compares the two, and a command writes it again when the
  models change on purpose, as the visual baselines are drawn again.
- **A branch** is a checkpoint and another schedule from its moment. Two
  branches share every day before it, as climate runs already share their
  air up to their first difference.
- **Replay:** a run's state probes, each plant's organs and sizes, the
  house's air, and a sample of readings, are hashed at each day's end. A
  reference list of the first days' hashes is kept in the repository, and a
  test replays the run and compares them.
- **Viewer:** branch A and branch B from the same checkpoint charted side by
  side, the house's air, a plant's growth and a sensor's readings, as P07.8
  compares a controlled and an uncontrolled day.

### 6. QA mode (P09.6)

- **An explicit toggle,** `&qa=1` in the address and a checkbox in the
  display options, off by default. Only QA mode asks for truth; a browser
  test checks that the viewer makes no truth request without it.
- **What it shows:** the sensors' truth beside their observations, the
  plants' identifiers as labels, field probes, each plant's light, and the
  run's manifest: the scenario's version, the models chosen, the seed, and
  the simulator's and the viewer's versions and commits.
- **One developer panel** says what every subsystem holds at the moment:
  the clock, the last plant day, the latest commands, each sensor's
  freshness and each camera's last frame.

### 7. Visual regression (P09.7)

Golden views of the reference scenario on a QA page, in CI's pinned
container (decision 0014), with baselines drawn by CI: dawn, noon and
evening; a fan on and off; a vent open and closed; a young crop and a
fruiting one; the camera's RGB and depth images; an airflow slice and a
radiation slice. State probes' values are checked beside them. These tests
run in their own Playwright project, as the plant lab's and the sun's do.

### 8. Performance (P09.8)

- **The simulator's costs:** wall-clock time per simulated day (the house's
  air, the plants' light, the plants' days) and per hour of air cell by
  cell; entity and organ counts; the field grid's size; a camera frame's
  cost; the process's memory.
- **The renderer's:** frame rate and frame time with the reference scenario
  at its fullest crop, measured locally on a graphics card (decision 0015).
- **A stored report:** a benchmark command writes a JSON report, and the
  first, with the machine it ran on, is kept in the repository. The HUD
  shows the simulator's time for the latest request beside the renderer's.
- **The report names the next bottleneck,** before anything is rewritten in
  another language. Expected: about 1.5 minutes to run the season's 120
  days from the start, which the kept opening day spares the viewer.

### 9. A release (P09.9)

- **One command** starts the API and the viewer and opens the reference
  scenario in the browser; stopping it stops both.
- **A guide,** `demo.md` in the `docs` folder: the command, the reference
  scenario, the final QA's checkpoints with what each should show, the
  known approximations gathered from every project, and troubleshooting (a
  port in use, Node and Python versions).
- **A demo video:** a scripted walk through the final QA, recorded by
  Playwright from the reference scenario on a machine with a graphics
  card, so that each release can record it again. GitHub plays a video in
  the README only if GitHub hosts it: an MP4 or WebM uploaded through an
  issue or pull request, up to 10 MB on a free plan. A Google Drive file
  can only be linked. So the README plays a short cut, under 10 MB, and
  links a longer one on YouTube by its thumbnail. Uploading them is done by
  hand.
- **A version:** the release is tagged, with its changelog.

### 10. Viewer

- **The reference scenario is the viewer's first,** and its default.
- **The time controls span the season:** day and time of day, play at a
  chosen pace through it, and step a day.
- **A wind override** for QA, `&wind=90`, as `&clouds=` overrides the cloud
  cover, so that the wind's direction can be changed without another
  weather.
- **New panels:** the timeline (section 2), the plant's days in the
  inspector (section 3), branches (section 5) and QA mode (section 6).

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P09.1 | `feat(scenarios): define versioned integrated scenario manifest` | Done |
| P09.2 | `feat(sim): unify multi-rate scheduler and visible event timeline` | Done |
| P09.3 | `feat(coupling): connect radiation/weather/climate to plant environment` | Done |
| P09.4 | `feat(coupling): connect actuators weather and vents to sensor observations` | Done |
| P09.5 | `feat(replay): add checkpoint reset branch and replay` | Done |
| P09.6 | `feat(qa): add QA mode with truth overlays` | Planned |
| P09.7 | `test(e2e): add integrated visual regression suite` | Planned |
| P09.8 | `perf(sim): add representative performance benchmark` | Planned |
| P09.9 | `docs(release): document local demo and QA protocol` | Planned |

### P09.1: Scenarios as manifests

The manifest's model and schema; every scenario converted to one,
unchanged; then the reference scenario's manifest and layout. Two pull
requests: the conversion, then the new scenario. Visible result: one file
boots the complete scene in the browser. Tests: every converted scenario's
configuration equals its code's, written out before the conversion; the
manifests validate; an unknown `schema_version` is refused.

#### As implemented

- **Every scenario is a manifest** (#123, decision 0031),
  `scenarios/manifests/<id>.json`: its configuration as Pydantic writes it,
  only the fields its module set, its layout by name, `schema_version: 1`,
  and `notes` in place of its module's comments, keyed by what each is
  about. `scenarios/manifest_files.py` reads them and refuses a format it
  does not read, a manifest of another scenario, a note on what the
  scenario does not have, and a field the configuration does not have at
  any depth, which some nested models would otherwise ignore. Its schema,
  `scenario.schema.json`, is generated and kept current by a test. Every
  converted scenario was held, field by field, to the configuration its
  code built. The registry lists the reference greenhouse first, then the
  others by identifier.
- **The reference greenhouse** (`reference_greenhouse`): three 3.2 m spans
  and three 4 m bays, 12 by 9.6 m, 4 m to the gutters and 4.7 m to the
  ridges; a roof vent 4 m by 0.8 m near each ridge and a 1.6 by 2.2 m door
  in the front gable, all shut. Four rows of eight plants, 0.75 m apart in
  rows 1.6 m apart, on hanging gutters with a pipe rail along each and crop
  wires 3.6 m up; a path across the front. Two 1 m³/s fans over the path, a
  15 kW heater in the back right corner and a 1.5 kg/h dehumidifier on the
  left wall, all off. Temperature and humidity at crop height in either
  half, the back pair imperfect; an anemometer in the right fan's jet; CO₂
  in the middle; PAR in the canopy and under the roof; a camera at the
  front looking down the middle path; a weather station 3 m in front. The
  cold spring day every day, half clouded; 14 °C and 80% inside to start;
  from 1 March 2026 for 120 days; seed 42. Its scene has 178 entities.
- **What joins it later,** with the step that uses it: the plant model's
  choice and the crop work (P09.3), commands (P09.2, P09.4) and the kept
  opening day (P09.5). Until P09.3 it grows with the simple daily model, as
  every scenario does, and its reference baseline is recorded.
- **Visible result:** `e2e/reference-greenhouse.spec.ts` finds it first in
  the scenario list, and its scene drawn whole, its equipment off, its
  vents shut, and its sensors and camera.

### P09.2: One clock and the timeline

Runs through the scenario's duration, the processes' order, daily
schedules, the timeline's route and panel. Visible result: the timeline
shows events at their different frequencies. Tests: the event counts and
order of section 2.

#### As implemented

- **One clock** (#125), `core/clock.py`, and the viewer's copy of it: a
  run's moments are seconds from its start, and a moment belongs to the
  day it lies in or, at a midnight, the day it ends, so a run of `d` days
  has days 0 to `d − 1`. A run lasts its scenario's days
  (`ScenarioConfig.run_length_s`), and every service refuses a moment past
  its end, naming them. The house's air, the observation log, the sensors'
  truth and the camera frames are a day's by default, from the start of
  the moment's day; `&from=` asks for more. The weather's day is the
  moment's, and a plant's light integral its moment's day's. A sensor's
  freshness is worked out from its dropout draws, without the readings
  before it.
- **The time controls span the run** (#126): a slider over the moment's
  time of day and one over the run's days, a day's step either way, and
  play at five minutes, an hour or a day a step. A later day's moments
  are written with their day (`day 3, 5 h 05 min`). The house's air, the
  weather's day, a sensor's chart and the schedule's bar are drawn across
  the moment's day.
- **Daily commands** (#127): `&daily=64800:heater:1` sets a piece of
  equipment, or a door or vent, at a time of day on every day of the run,
  before any other command at the same moment, so that one given for the
  moment overrides it. "Schedule" lists them apart, and repeats any
  command every day (↻).
- **The timeline** (`core/timeline.py`, `GET
  /api/scenarios/{id}/timeline`): every event of a run in a window of a
  day at most, by process, subject and kind, enumerated from the cadences
  and the commands, in the order of section 2. The house's air is listed
  where the run works a climate, at each minute's end and each command's
  moment, as the whole house works it. Its document is written column by
  column: a day of the reference greenhouse is 21 633 events, 407 KB, in
  14 ms. The viewer's "Timeline", opened on demand, draws a lane per
  process across the window the moment lies in, from a day to a minute,
  and lists what each process does at the moment, in turn.
- **Tests:** over the reference greenhouse's second day, each plant has
  one day, each sensor `86 400 / cadence_s` samples, each camera its
  frames, each command one event, and the air a step a minute; the same
  run gives the same events in the same order; at a midnight the
  processes take their turns in order (`tests/test_timeline.py`). Browser
  tests: `season.spec.ts`, `daily-schedule.spec.ts` and
  `timeline.spec.ts`; the first two, which work a climate run on each day
  they visit, run on their own after the others.
- **Found on the way:** the reference greenhouse's air takes about a
  second a simulated day to work out, mostly the sun's heat through its
  three spans, so a late day's first moment takes about a minute and a
  half to reach. The kept opening day (P09.5) and P09.8 address it.

### P09.3: The crop in the climate

The organ-level crop in the reference scenario, each plant's day from the
house's air and its own light, growing crowns, the recorded coupling.
Visible result: plants in different places diverge over an accelerated
season. Tests: a plant in more light grows more; a warmer house develops
the crop faster; the same seed grows the same crop.

#### As implemented

- **The plant model is the manifest's choice** (`crop_model`): the
  reference greenhouse's is `organ`, with a harvest round every seventh
  day (`crop_work`); every other scenario keeps `simple`, and the engine,
  the live run and the reference baseline still grow the simple model for
  all of them. The scenario list says which each grows.
- **A run's crop** (`core/crop.py`) starts from the plant lab's
  transplants, now drawn in one place for both
  (`biology/tomato/organ/transplants.py`), each from the scenario's seed,
  at its planting position. Each plant lives each day in a
  `LocalEnvironment` from the run, through the plant model's
  `Environment` contract: the house's mean air temperature and CO₂
  through the day, by the trapezoid rule over its minutes
  (`WholeHouse.mean_between`), the same for every plant; its own daily
  light integral, read at its crown's top with every crown as tall as
  its plant's standing stem that day; and water status 1. At a midnight
  the plants live the day that ends, then a harvest round, on its day,
  picks every red fruit, each a harvest of its own in the plant's
  history; the timeline lists each round after the plants' day. At a
  moment, the crop has lived the days ended by then (`days_ended`): one
  at the end of the first day.
- **Kept, not recomputed:** what each plant experienced on each day is
  kept, so that its plants on any day are lived again from it, without
  the air or the light; a crop keeps its plants on its first day, its
  latest, and the last two asked for. A run's crop takes over another's
  days up to the first on which their air differs, and the whole house
  now takes over another's air the same way, as its grid run did, so a
  command added late in a season works out only the days after it.
- **The API:** `GET /api/scenarios/{id}/crop` draws the crop organ by
  organ on the moment's day, and `.../crop/{plant}` gives a plant's
  structure, history and each day's environment; both are asked for as
  a climate field is. A scenario that grows the simple model has no crop
  to draw. The plants' light (`.../climate/plants`) takes the run's parts
  too, its crowns as the crop stands on the moment's day. Before its
  first day, the reference scene draws its transplants organ by organ:
  3,104 entities in place of 178.
- **The viewer** draws the crop on the moment's day once a day has
  ended, asking for it at the start of the crop's day so that a day's
  moments share it, and says the crop's day in the scene's status. A
  selected part of a plant shows its light, and its days: the house's
  air and its own light on each day it lived, charted day by day, what
  was picked from it, and its structure.
- **Tests:** in steady air and light, a plant in less light grows less
  at the same thermal time, a warmer house develops the crop faster, the
  same seed grows the same crop and another another, each day's light is
  read with the crowns as tall as the plants stand, a harvest round picks
  every red fruit, each day is worked out once, and a crop takes over
  another's shared days (`tests/test_run_crop.py`); in the reference
  greenhouse's own air and sunlight, its plants share the house's mean
  air, each in its own light, and a heater from the start warms their
  days and their development. Browser test: `crop.spec.ts`, with the
  season's.

##### What the season shows

- **Plants diverge mostly by their own traits.** By day 30 of the
  unheated run, their stems stand 0.28 to 0.52 m tall.
- **Place matters by row, not by row end.** At the spring's noon sun, the
  house's long gutters, 4 m up, cast their shadow about 4 m north of
  themselves: on rows 2 and 4. Over the first month those rows take about
  20 mol/m²/d against about 23 for rows 1 and 3, and a row end barely
  more than its row. Read at the crowns' tops, a plant is shaded only by
  the structure and by crowns taller than its own, and the diffuse sky
  reaches every crown alike. Above 25 mol/m²/d light no longer holds
  growth back, so by day 30 the gutters' shade costs a plant about a
  centimetre of stem; by June every row is above it most days.
- **Unheated, the crop ripens only in its last fortnight.** The shut
  house averages 13.6 °C a day in March and 19.7 °C in June: the plants
  reach 1,115 °Cd by day 120, the round of day 105 picks the first 5 red
  fruits, and 147 are picked by day 119; the first day with red fruit, the
  kept opening day (P09.5), is then about day 105, not 80. Working the whole
  season out takes 192 s. With a heater on every night,
  18 h to 8 h (`&daily=64800:heater:1,28800:heater:0`), it averages 22.2 °C,
  the plants bear 38 to 61 fruits by day 100, and the tallest stems reach
  the crop wires 3.6 m up, unless lowered.
- **Costs:** a crop's day costs the house's air through it, 1.1 to 1.5 s,
  and its light, 0.18 s for 32 crowns; living the 32 plants through 120
  days again from their kept days, 1.4 s. Its scene is 12,000 entities
  and 10 MB of JSON by day 60, and 20,000 and 17 MB by day 120, 1.8 MB
  gzipped; the API does not compress its answers (P09.8).

##### Lowering, as a high-wire crop is

Added after P09.3's first pull request, in review (decision 9): the design
had assumed the stems would stay under the wires through 120 days, an
estimate, not a constraint, and a heated run proves it wrong.

- **How a real crop is lowered:** each plant hangs by its twine from a hook
  on the crop wire; once a week or so, as its top nears the wire, a grower
  unwinds some twine, slides the hook along the wire, and the plant's bare
  lower stem, its leaves stripped and its trusses harvested, lies down
  along the gutter beside its neighbours'. In a double row the plants are
  trained to two wires by turns, and at a row's end a plant passes round
  to the other side, so that the stems travel round the gutter as a
  carousel.
- **A high-wire double row** (`CropWires.offset`): two wires above each run
  of a row's positions, one either side, `row_<r>_wire_<n>_left` and
  `_right`; the reference greenhouse's hang 0.3 m either side of its rows,
  and its scene has 3,108 entities. Its plants are trained to them by
  turns, its first to the left wire, and each stem leans out to its own,
  about 6° from the vertical (`world/training.py`).
- **The lane:** a plant's laid stem lies in a loop round its gutter, along
  its edges, 0.15 m either side of the row: a left-wire plant's forward
  along the left edge, a right-wire plant's back along the right, and each
  round the gutter's end to the other edge when it gets there. Where the
  laid stem ends, the stem rises, leaning out to the wire above that edge,
  or, round an end, to one as far out. The plant's geometry follows its
  path (`StemPath`): each laid internode from one point of the lane to the
  next, the rest along the way it rises. The plant lab keeps its straight
  path along its row.
- **The lowering round** (`lowering_round`), every seventh day after the
  harvest round: a plant whose top stands more than `head_room_m` (0.3 m)
  under its wire lays down as few of its lowest standing internodes as
  bring it low enough, stripping their leaves first, each an event in its
  history; never one whose truss still bears, so a plant whose lowest
  truss is still green waits for its harvest. Its crown, for its light,
  stands where its stem rises. The timeline lists the round after the
  harvest round.
- **Tests** (`tests/test_crop_training.py`): the pair of wires, plants
  trained by turns, a stem reaching its wire, the lane round the gutter
  and back to its start, laid stems forward on the left, back on the right
  and round the end, the geometry along the path, a round that lays down
  no more than it must and never a bearing truss, and in steady air a
  weekly round keeping every top under its wire through a season.
- **What it shows:** at a steady 22 °C the first plants are lowered in
  the run's last weeks, by up to 0.56 m by day 120; none is lowered far
  enough to turn a row's end before day 120, which a longer run does.

### P09.4: Equipment, weather and sensors through the season

Schedules, weather and sun through the season, observed by the sensors.
Visible result: a heater, fan and vent schedule shows in the overlays and
the sensors' charts. Tests: observations come only through the observation
path; a heater's night setback shows in the readings.

#### As implemented

- **A scenario's own daily commands** (`ScenarioConfig.daily`, its
  manifest's `daily`): its runs give them unless a run gives daily commands
  of its own, and `&daily=none` gives none, at every route that takes a
  run. A scenario refuses daily commands to equipment or openings it does
  not have, and the scenario list gives them, and its doors' and vents'
  identifiers. The comparison with everything off has none.
- **The reference run's climate by the clock,** every day: the heater full
  from 17 h, set back to 80% at 23 h, full again from 5 h before dawn, half
  at 7 h and off at 9 h; the roof vents half open at 9 h, fully from 11 h,
  half from 18 h and shut at 20 h; both fans from 8 h to 20 h. 21 commands.
  The dehumidifier stays off: with no crop transpiring into the air, a
  heated house is dry enough, and a night of drying took it to a mean of
  23% relative humidity.
- **What it makes of the season,** chosen among six schedules measured
  through all 120 days (about 4 minutes each): the house averages 17 °C a
  day in March and 21.5 °C in June; evenings stand near 19 °C, the night
  set back to 12 to 14 °C, March mornings dip to 10 °C once the heat steps
  down, and the day's peak rises from 22 °C in early March to 28 °C by May
  and 31 °C in June, the relative humidity at 33 to 41% on average. A fixed schedule
  cannot follow the season: from May the morning's heat and an early sun
  meet before the vents open fully, and the day's peak comes at 9 h. A
  climate computer's setpoints would follow it.
- **The viewer** draws a scenario with its own daily commands where its
  address gives none, lists them under "Schedule", and keeps in the address
  only what differs from them; taking one out writes the rest, and taking
  them all out, `&daily=none`. A door or vent a command opens now stands
  that far open in the scene at the moment drawn: a command to it was
  counted as equipment's before, which the scene refused.
- **Tests** (`tests/test_reference_schedule.py`): the reference run heats,
  vents and stirs its house every day and no other scenario's does; a run
  gives its scenario's daily commands, its own in their place, or none;
  the API reads `daily=none` as none; a daily command to what a scenario
  does not have is refused; the heater's night setback shows in the front
  temperature sensor's readings, 3 h into the third day colder than 22 h
  into the second and far warmer than unheated; and a clean sensor's
  observations late in the run are the run's own air where it stands.
  Browser test: `reference-schedule.spec.ts`, with the season's.
- **A wind override for QA** (section 10, the final QA's sixth step):
  `&wind=90` turns the wind to blow from that bearing at its own speed, the
  rest of the weather its own, as `&clouds=` overrides the cloud cover; the
  API takes it in the weather's name, `default~90` or
  `cold_spring_day@80~90`, and refuses a bearing outside 0 to 360°. The
  weather panel has a slider for it, in steps of 15°. Only openings in the
  house's walls turn with it: at noon its own westerly blows 11.6 m³/s in
  through the open front door, and a northerly draws 2.4 m³/s out; the
  roof vents' exchange depends on the wind's speed alone (P07.4).

### P09.5: Checkpoints, branches and replay

Checkpoints at day starts, saved and restored as JSON, branches, state
probes' hashes, and the branch comparison. Visible result: branch A and B
charts from the same state. Tests: a restored run continues as the original
does; a branch shares every day before its own; the replay's hashes match
the reference; the kept opening day matches the run's.

#### As implemented

In four pull requests: the checkpoints and the viewer's panel, the branch
comparison, the replay's digests, and the kept opening day.

- **A checkpoint** (`services/checkpoints.py`) is a run's state at the start
  of a day: its run, its scenario and the digest of the scenario's manifest
  it was made with (`manifest_digest`, of its content, however the file is
  laid out), its layout and weather, its levels and openings from the
  start, the commands it gave before that day and its daily commands, or
  none given, for its scenario's; its house's air then; and, where it
  grows its crop organ by organ, its plants then and what each experienced
  on each day before. Named by a digest of its content, so that the same
  state uploaded twice is one checkpoint. The reference run's on its second
  day is 178 KB of JSON.
- **Kept states** (`services/kept_states.py`): a run of the same house,
  weather and openings whose schedule agrees with a checkpoint's up to its
  moment takes its state over, the house its air (`WholeHouse.seed`) and
  the crop its plants and days (`RunCrop.seed`), as kept runs already carry
  on from one another. Restoring a checkpoint is asking for its run again;
  a branch is the same run with other commands from its moment on. A
  checkpoint saved or uploaded seeds the runs already kept too.
- **The API keeps them in memory,** the last 16: `POST
  /api/scenarios/{id}/checkpoints` saves one at the start of the day `&t=`
  lies in, its run asked for as a climate field is; `GET /api/checkpoints`
  lists them; `GET /api/checkpoints/{id}` downloads one as JSON; `POST
  /api/checkpoints` uploads one as its JSON body, checked: in a format this
  simulator reads, made with the scenario's manifest as it is, its day
  within the run, its commands the scenario's to run, its plants the
  scenario's, each having lived every day before. Restarting the API
  forgets them, and it writes no file. The API's server now reads a POST
  request's body.
- **The viewer's "Checkpoints"**, under the timeline in the climate view,
  opened on demand: it saves the start of the moment's day, lists those
  kept for the scenario, restores one, its run at its moment with the view
  as it was, and downloads one as JSON or uploads one again, saying why one
  is refused. A restored run given other commands from its moment on is a
  branch from it. Browser test: `checkpoints.spec.ts`, with the season's.
- **Branches compared** (`BranchComparison`): "Compare" against a kept
  checkpoint charts branch A, the checkpoint's run carried on unchanged,
  beside branch B, the run drawn, at the moment drawn: the house's air
  through its day, its first temperature sensor's readings through it,
  and, where it grows its crop organ by organ, its first plant's days since
  the checkpoint, with how far each has developed. A solid, B dashed; a
  moment before the checkpoint says so. In the climate box, a branch whose
  heater goes off two hours into its second day is more than 2 °C cooler
  than its checkpoint's run two hours later (`checkpoints.spec.ts`).
- **Replay** (`services/replay.py`): at each day's end a run's state is
  probed, each plant's structure, organs, sizes and history, the house's
  air, and what each point sensor observed on each hour of the day, noise,
  dropouts and all; written as JSON with its numbers rounded to six
  decimals, so that two machines' maths libraries' last bits do not tell
  two replays apart, and digested. The digests of the reference run's first
  three days are kept in `tests/fixtures/reference_replay.json`, with the
  manifest they were made with and readable values beside them, and
  rewritten by `python tests/test_replay.py --update`; a test replays the
  run against them (`tests/test_replay.py`). A branch keeps the digests of
  the days before its change. Three days probe in 11 s from the start,
  2.6 s again.
- **The kept opening day:** the reference run's first day with red fruit is
  day 80, under its own schedule, as the design expected. Its manifest
  names it (`opening_day`), and a checkpoint at its start is kept beside
  it, `scenarios/openings/reference_greenhouse.json.gz`, 188 KB gzipped
  (1.3 MB of JSON), written the same way every time; and beside that, the
  same run's with everything off (`.all-off.json.gz`, 144 KB), which the
  house's air is charted beside: without it, opening on day 80 had the
  simulator work out 80 days of air all off, two minutes in which every
  request for that run waited. The API keeps both as
  it starts (`load_openings`), saying why if it does not fit the run; the
  scenario list gives the day, and showing the reference greenhouse from
  the list opens its climate at noon on it, in a few seconds where working
  it out from the run's start takes three minutes. The address without a
  moment still opens it at its start. `python tests/test_opening_day.py
  --update` finds the day and writes both again, in about four minutes,
  and a slow test replays the run from its start to that day and holds it
  to the one kept (`tests/test_opening_day.py`). Unheated, as P09.3 measured, the first red
  fruit would come about day 105.
- **Found on the way:** a whole day's observation log of the reference
  run, 18,600 observations, takes about 40 s, each minute's sample drawing
  the house's whole field with its sunlight; the probes sample each hour on
  its own instead. For P09.8.
- **Measured:** after a restart, the reference run's third day, from a
  checkpoint at its second, comes back in 1.4 s, the same as before; from
  its start it takes about 3.5 s.
- **Tests** (`tests/test_run_checkpoints.py`): a checkpoint keeps a run's
  state at its day's start, and the commands given before it; a restored
  run carries on as the original does, working out no moment before the
  checkpoint; a branch shares every day before its own and differs on it,
  and a run that differs before the checkpoint takes nothing over; a
  checkpoint downloads and uploads as it was; and what does not fit its run
  is refused, with the reason.

### P09.6: QA mode

The toggle, truth beside observations, labels, probes, the run's manifest
and the developer panel. Visible result: one panel explains what every
subsystem holds. Tests: no truth request without QA mode; the manifest
shows the versions served.

### P09.7: Integrated visual regression

The golden views of section 7, and their probes. Visible result: the
views' screenshots. Tests: the screenshots, and the probes' values.

### P09.8: Performance

The benchmark command, its stored report, and the simulator's time in the
HUD. Visible result: the HUD and the report. Tests: the report has every
measure; the benchmark runs on the reference scenario.

### P09.9: The release

The one command, the guide, the demo video's script, and the tagged
release. Visible result: a new checkout reaches the reference scenario by
following the guide, and the README plays the demo. Tests: the command
starts both and stops both; the video's script runs as a browser test.

## Final QA: `reference-greenhouse-v1`

A reviewer should be able to:

1. Start the simulator with one command and open the reference scenario,
   seed 42.
2. Inspect the house's dimensions and the crop's layout.
3. Scrub from morning to noon and watch the sun, the shadows and the
   radiation.
4. Inspect the airflow's vectors and the temperature and humidity slices.
5. Turn the fans, the heater and the dehumidifier on, and see the fields
   respond.
6. Open a roof vent and change the outside wind's direction.
7. Compare the sensors' readings with QA mode's truth.
8. Look through the fixed camera: RGB, depth and instance views.
9. Accelerate the crop, and see its seeded variation and its fruit ripen.
10. Harvest one fruit, and find it in the plant's history afterwards.
11. Save a checkpoint, branch the run, and compare two control schedules.
12. Reset to seed 42, and match the reference screenshots and state probes.

## Acceptance criteria

- [ ] One command starts the simulator and the viewer locally.
- [ ] The reference scenario is data-driven and versioned.
- [ ] The same seed and configuration reproduce the QA results within
  stated numerical and rendering tolerances.
- [ ] The viewer gives enough diagnostics to understand a failure.
- [ ] Every major subsystem has its own QA scenario, and the integrated one
  exercises them together.
- [ ] No external service is needed to run the reference simulation.
- [ ] Performance measurements identify the next real bottleneck before any
  rewrite in another language.

## Known approximations

- **The crop's air is the house's:** its temperature and CO₂ are the
  well-mixed house's, the same for every plant; only light differs from
  plant to plant.
- **The crop does not change the air:** its transpiration and CO₂ uptake
  are not modelled, and its water status is always 1.
- **The house sees the crop as it stands before its first day:** the
  sun's heat in the house's air (P08.8) and the PAR sensors' light are
  shaded by the transplants' crowns; only the plants' own light follows
  the crowns as they grow.
- **A plant's light is read at its crown's top:** a crown shades another
  only if it stands taller, and the diffuse sky reaches every crown alike.
- **A lowered crop's stems lie on its gutter's edges:** the stems on one
  edge lie along one line rather than side by side, and the twine and the
  hooks are not drawn.
- **The live run grows the simple model:** the stream a viewer can play
  live steps the engine, which grows every scenario's crop with the simple
  daily model, the reference greenhouse's too.
- **Coupling at day boundaries:** a plant's day is computed from that day's
  air and light, and its crown's height changes the light the next day.
- **Checkpoints at a day's start** only; a moment within a day is reached by
  running from its start.
- **The air cell by cell** is drawn for a moment when asked, from an hour
  of air started from the house's (P07.3), not kept through the season.

## Review decisions (12 October 2026)

1. **The organ-level crop in the reference scenario only.** The other
   scenarios keep the simple daily model, so that their numbers and
   baselines hold. Agreed.
2. **House-wide air for every plant, its own light each.** Local
   temperature from the air cell by cell would need about 24 hours of it per
   simulated day, 36 to 170 s: one to four hours for the season. It can
   come later as a higher rung of the ladder. Agreed.
3. **Every scenario becomes a manifest** in P09.1, one format for all,
   rather than only the new one (section 1). Changed in review.
4. **Checkpoints made while viewing live in the API's memory,** downloadable
   as JSON, rather than in a folder the API manages; the reference run's
   opening day is a file in the repository (section 5). Explained further
   after review, then agreed.
5. **One command launches both processes,** the API and the viewer's
   development server, rather than the API serving a built viewer, which
   would spare a release its Node dependency but add a build to every
   start. Agreed.
6. **The season:** 120 days from 1 March rather than 90, with a weekly
   harvest round, opening on the first day with red fruit, kept in the
   repository (sections 1 and 5). Changed after review, which asked for a
   longer run or a saved later start, then agreed.
7. **`&t=` becomes seconds through the whole run** for every scenario,
   rather than a separate day parameter beside seconds within a day.
   Agreed.
8. **A demo video** in the README, as GitHub can host it, with a longer one
   linked (section 9). Added in review.
9. **Lowering:** the reference run lowers its crop every week, as a
   high-wire double row is lowered, its stems passing round each gutter's
   ends to the other side, rather than no lowering in 120 days, which was
   an estimate. Asked for in P09.3's review, with the turn at the row's
   end rather than stems running on past it.
