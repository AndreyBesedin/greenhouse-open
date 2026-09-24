# Changelog

All three packages share a version while the protocol settles. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [semantic versioning](https://semver.org/): a change that
breaks the conformance checks is a major version.

## 0.1.0 - unreleased

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
