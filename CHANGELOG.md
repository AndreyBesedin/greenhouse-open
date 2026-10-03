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
