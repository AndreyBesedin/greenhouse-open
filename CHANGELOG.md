# Changelog

All three packages share a version while the protocol settles. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [semantic versioning](https://semver.org/): a change that
breaks the conformance checks is a major version.

## Unreleased

- All three packages now require Python 3.14 or newer (previously 3.12).
- `greenhouse-sim`: the simple tomato model's own values (a plant's growth
  multiplier and water stress; a fruit's target diameter, growth-rate
  multiplier and ripening day) move from `PlantWorld` and `Fruit` to
  `GreenhouseWorld.plant_model`. Worlds serialized by earlier versions no
  longer load.
- `greenhouse-sim`: plant, environment and sensor models plug into
  `SimulationEngine` through contracts (`PlantModel`, `EnvironmentModel`,
  `SensorModel`), with the existing dynamics kept as the default simple
  models. The internal modules are regrouped by domain; the public import
  paths are unchanged and now documented.
- `greenhouse-sim`: `scene_snapshot` describes a world as a renderable scene,
  in metres with z up.
- `greenhouse-sim`: a local API for the browser viewer
  (`python -m greenhouse_sim.api`), using only the standard library.
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
- `greenhouse-sim`: virtual sensors and cameras (P06), with noise, bias,
  drift, latency and dropouts, an observation log and each sensor's
  freshness; and the sun (P08): its position, the glazing's transmission,
  shadows, and each plant's light.
- `greenhouse-sim`: the reference scenario and its season (P09): every
  scenario a versioned JSON manifest; the reference greenhouse's 32 plants
  grown organ by organ through 120 days in their run's air and their own
  light, on one clock, with a timeline; checkpoints, branches and replay
  digests; a kept opening day; a QA mode with the truth and a developer
  panel; golden views; a benchmark (`python -m greenhouse_sim.benchmark`);
  and the API's `Server-Timing` header.
- The viewer draws all of it (P00 to P09), with screenshot regression in a
  pinned container, and `python scripts/demo.py` starts the API and the
  viewer together and opens the reference greenhouse (`docs/demo.md`).
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
