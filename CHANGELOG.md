# Changelog

All three packages share a version while the protocol settles. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [semantic versioning](https://semver.org/): a change that
breaks the conformance checks is a major version.

## Unreleased

- `greenhouse-sim`: a playback plays its scenario's own layout or one
  rearranged (#271, decision 0041). `POST .../playback/restart?layout=`
  starts it over with that layout's run from its first day, a new run with
  its own identity and epochs, and `start` takes a layout too; its state
  says the layout it plays. A consumer finds the new run in its list of
  runs. The viewer's Move panel holds moves as a draft: equipment and
  sensors dragged stay where they are dropped, and "Start a new run with
  these moves" applies them all at once from the run's start, starting the
  run played back over with them while the view follows it.
- `greenhouse-sim`: the climate's 3D air takes steps up to 0.9 of the
  longest that keeps each new temperature a weighted mean of the old ones,
  not half of it: a late day of the reference greenhouse draws its air in
  1.3 s, not 2.2, and a day step costs about 4.3 s, not 5.2 (#198). The
  air drawn moves by 0.02 K at most. The sensors read the grid only through
  a run's first two hours, the house's air after: there, a few readings
  move by one step of their rounding (20 of the reference run's 2,341 in
  its first three hours, by 0.1), and none after. The reference QA page's
  kept views are written again.
- `greenhouse-sim`: air past water's boiling point holds any water, and
  none condenses from it. A cell the heater warmed past 100 °C used to lose
  more water than it held, as the saturation ratio's formula turns
  negative there: in the reference greenhouse's first minutes the house's
  humidity cell by cell ran to ±10⁸ %, and its hygrometers, which read the
  grid run through a run's first two hours, read 0% and then 100% for over
  an hour. They now read 43 to 89%. The reference run's day 0 replay digest
  changes with them; days 1 and 2, read from the house's air, do not.
- `greenhouse-sim`: the reference greenhouse's back temperature sensor
  drifts 0.001 °C an hour, not 0.01. Its drift grows from the run's start,
  and over the 120-day season 0.01 added 29 °C, so it read 42 to 58 °C in
  June; now it reads about 2 °C high by the opening day, still a fault a
  consumer can find. The run's identity changes with it.
- `greenhouse-protocol`: the consumer interface
  (`greenhouse_protocol.contracts.consumer`, decision 0040, P10.1): how a
  client reads a running producer, whatever it is. Routes under
  `/consumer/v1` answer a run's identity, epoch and clock, its greenhouse
  description, and its observations and events after a cursor, in delivery
  order, with nothing from after the run's clock. `check_batch` and
  `check_polls` hold a producer to the rules, and a recorded exchange
  (`tests/fixtures/consumer/exchange.json`) lets a client be built before
  any producer serves it.
- `greenhouse-sim`: a scenario's own run played back against one clock
  (decision 0041), which the viewer and a consumer follow: its point
  sensors' readings worked out ahead, day by day, at a consumer's cadence
  of 300 s, and served only as far as the clock has reached; the run's
  identity, epoch and instant said the same way to both. The API starts,
  plays, pauses, restarts and paces it (`/api/scenarios/{id}/playback`).
- `greenhouse-sim`: the consumer interface served from a played-back run
  (P10.4): `GET /consumer/v1/runs`, a run, its greenhouse, and its
  observations and events after a cursor, on the API's loopback server;
  observed records only. Besides the sensors' readings, the run's
  organ-level crop delivers a daily walk through it at noon (each plant's
  fruit and red fruit counted, their mass estimated, its height measured,
  with the scenario's observation errors) and its weekly harvests, one
  `HARVEST` event per plant picked. `uv run api --play reference_greenhouse
  [--hold]` starts the run with the API, held until told to play if asked.
- `greenhouse-sim`: a season and a thermostat (P10.3, decision 0042). A
  scenario's weather can follow the year (`"kind": "seasonal"`): each day's
  coldest and warmest temperatures go from winter's to summer's and wander
  in spells drawn from the seed, each day its own clouds. A thermostat runs
  a heater by the house's air, on below its setpoint by half its band and
  off above it by as much, a setpoint by day and one by night; a command to
  the heater takes it over. The heat a run's heaters give is counted, and
  played back hour by hour as `HEATING_ENERGY_INCREMENT_MJ_M2`, modelled
  heat input per square metre of floor, not a meter's reading. The viewer draws
  and says the thermostat's heater as the run has it
  (`GET /api/scenarios/{id}/climate/equipment`). A run's identity now covers
  everything its scenario is made of, so a changed manifest or layout is
  another run.
- `greenhouse-sim`: the reference greenhouse under a season from 1 March
  and its heater, now 30 kW, on a thermostat at 18 °C by day and 16 °C by
  night, in place of the cold spring day every day and the heater by the
  clock. Its run is another: its identity, its opening day and its numbers
  change.
- `greenhouse-protocol`: the consumer interface
  (`greenhouse_protocol.contracts.consumer`, decision 0040, P10.1): how a
  client reads a running producer, whatever it is. Routes under
  `/consumer/v1` answer a run's identity, epoch and clock, its greenhouse
  description, and its observations and events after a cursor, in delivery
  order, with nothing from after the run's clock. `check_batch` and
  `check_polls` hold a producer to the rules, and a recorded exchange
  (`tests/fixtures/consumer/exchange.json`) lets a client be built before
  any producer serves it.
- `greenhouse-sim`: the identifier of a piece of equipment
  (`actuator_id`), a sensor (`sensor_id`) or a door or vent (`opening_id`)
  holds only letters, digits, `_`, `.` and `-`, as `layout.schema.json` and
  `scenario.schema.json` now say. The API's parameters write identifiers
  between `:` and `,`, so an item named otherwise could not be set,
  scheduled or moved; a layout or scenario that names one is now refused
  as it is read. Scenario manifests are in format 2 for it
  (`schema_version`, decision 0031); a format 1 manifest is read as format
  2, and refused only if it names an item otherwise.

## 0.2.0 - 2026-10-19

The simulator's greenhouse, crop, air, sensors and sun, the reference
scenario's season, and the browser viewer that draws them (P00 to P09).
Several entries break 0.1.0's interfaces: the Python floor, records'
timestamps, a description's tuples, and worlds serialized by 0.1.0.

- All three packages now require Python 3.14 or newer (previously 3.12).
- `greenhouse-protocol`: every record's timestamps are timezone-aware, checked
  as a record is built (`greenhouse_protocol.instant.Instant`): an
  observation, event, frame or greenhouse description with a naive time is
  refused, as a capture already was. An observation's quality is written in
  order, so its bytes do not depend on the process. `check_media` refuses a
  capture that names no greenhouse.
- `greenhouse-protocol`: a greenhouse description, an action and an outcome
  check every edit as they were checked when built, and a refused edit
  leaves them as they were. A description's plants, compartments and layout
  are frozen, and its `plants`, `compartments` and `all_plants`, and a
  compartment's `plants`, are tuples: a plant or compartment is added or
  changed by assigning the description's field, which checks its identity.
- `greenhouse-sim`: the simple tomato model's own values (a plant's growth
  multiplier and water stress; a fruit's target diameter, growth-rate
  multiplier and ripening day) move from `PlantWorld` and `Fruit` to
  `GreenhouseWorld.plant_model`. Worlds serialized by earlier versions no
  longer load.
- `greenhouse-sim`: `ScenarioConfig` refuses values no run can have:
  `rows`, `columns`, `duration_days`, `truss_interval_days`,
  `fruit_growth_days_to_target` and `water_capacity_ml` are positive, and
  `random_seed` and `max_trusses` are not negative. Such values used to be
  accepted, and some then failed deep in a run.
- `greenhouse-sim`: plant, environment and sensor models plug into
  `SimulationEngine` through contracts (`PlantModel`, `EnvironmentModel`,
  `SensorModel`), with the existing dynamics kept as the default simple
  models. The internal modules are regrouped by domain; the public import
  paths are unchanged and now documented.
- `greenhouse-sim`: `scene_snapshot` describes a world as a renderable scene,
  in metres with z up.
- `greenhouse-sim`: a local API for the browser viewer
  (`python -m greenhouse_sim.api`), using only the standard library. It
  refuses a body over 64 MB, one that does not arrive in full, or one
  holding `NaN` or `Infinity`, and answers `PUT`, `PATCH` and `DELETE`
  with 405.
- A browser viewer for the simulator in `greenhouse_sim/web`, outside the
  Python package.
- `greenhouse-sim`: a greenhouse as data (P01, P02): its envelope, spans and
  bays, glazing, doors and vents, and its layout of rows, gutters, rails,
  benches, equipment and sensors, read from JSON files and checked.
- `greenhouse-sim`: an organ-level tomato model (P03): stochastic
  development, procedural plant geometry, crop work (pruning, harvesting,
  lowering) and a plant lab.
- `greenhouse-sim`: the greenhouse's air (P04, P05, P07): environment fields
  on a grid, prescribed airflow and OpenFOAM's out of process, and a climate
  driven by fans, a heater, a dehumidifier and vents, under recorded,
  synthetic or constant weather, with the house's air as one volume through
  a run.
- `greenhouse-sim`: virtual sensors and cameras (P06), sampling at most
  once a second, with noise, bias, drift, latency and dropouts, an
  observation log and each sensor's freshness; and the sun (P08): its
  position, the glazing's transmission, shadows, and each plant's light.
- `greenhouse-sim`: the reference scenario and its season (P09): every
  scenario a versioned JSON manifest; the reference greenhouse's 32 plants
  grown organ by organ through 120 days in their run's air and their own
  light, on one clock, with a timeline; checkpoints, of which an upload
  is refused unless a run could reach it, branches and replay digests; a
  kept opening day; a QA mode with the truth and a developer panel; golden
  views; a benchmark (`python -m greenhouse_sim.benchmark`); and the
  API's `Server-Timing` header.
- The viewer draws all of it (P00 to P09), with screenshot regression in a
  pinned container, and `uv run demo` starts the API and the viewer
  together and opens the reference greenhouse (`docs/demo.md`).
- The viewer zooms towards the point under the pointer and stops at the
  camera's closest approach, hides the overlays over the scene apart from
  the run, folds a run's daily schedule to a summary, and gives up the
  requests it no longer needs.
- A clone is a uv workspace: `uv run <command>` installs Python 3.14 and
  the packages and runs a task, `uv run setup` installs the viewer's
  packages, Chromium and the git hooks, and `uv run help` lists the rest
  (`demo`, `start`, `api`, `viewer`, `check`, `viewer-checks`,
  `browser-tests`, `record-demo`; decision 0039).
- `greenhouse-adapters`: a verified artifact is hashed again once its size,
  inode or modification time changes, and after every fetch; a fetched
  file that fails its checksum is moved aside, so the next run fetches it
  again. A download the publisher answers with 429 or 5xx, or that the
  connection cuts short, is resumed up to four times, waiting longer each
  time, and its bytes are kept; a resume no longer empties the partial
  file on an error, and a short or long body never reaches the final path.
- `greenhouse-adapters`: `greenhouse-data` ends a checksum mismatch, a
  network error or an archive that is not one in a line and exit code 1,
  instead of a traceback.
- `greenhouse-adapters`: a canonical build writes only records that pass
  the protocol's checks, and otherwise raises `RefusedBuild`, naming the
  first violations. It dates a greenhouse by its first reading rather than
  by when the build ran, and refuses a source with no readings.
- `greenhouse-adapters`: `excel_serial_to_utc` refuses a local time that
  the clocks skip or repeat, as `matlab_datenum_to_utc` already did.
- `greenhouse-adapters`: an artifact's name is a plain file name, with no
  folder, `..` or `:`; manifests and the canonical tier are read and
  written as UTF-8; and `greenhouse-data inventory --write` refuses to
  overwrite an installed package's manifests.
- All three packages now require pydantic 2.12.2 or newer (previously 2.9):
  `Observation` leaves its unset fields out with `exclude_if`, which
  pydantic 2.11 ignores, and 2.12.0 fails on Python 3.14. CI installs the
  protocol and the adapters at their lowest dependencies and tests them.

## 0.1.0 - 2026-09-24

First public release.

- `greenhouse-protocol`: canonical records, record store and query
  contracts with an inclusive `up_to` boundary, the action-execution
  contract, conformance checks, and an in-memory reference store.
- `greenhouse-sim`: deterministic simulator with a hidden world, noisy
  sensors, semantic actions through a pluggable executor, three scenarios,
  and ground truth behind an evaluation-only interface.
- `greenhouse-adapters`: dataset manifests, checksummed and resumable
  artifact resolution with download caps per profile, the deterministic
  canonical tier, adapters for the WUR Autonomous Greenhouse Challenge 2023
  pre-trial and 2024 challenge datasets, and the `greenhouse-data` command.
