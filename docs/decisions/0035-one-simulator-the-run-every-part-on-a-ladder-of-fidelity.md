# 0035: One simulator, the run, with every part on a ladder of fidelity

**Status:** Accepted
**Date:** 2026-10-16

## Context

The simulator has two ways of running a scenario
([repository audit](../audits/2026-10-13-repository-audit.md), `AUDIT.1`):

- **The engine's day** (`core/engine.py`): `SimulationEngine` advances a
  world a day at a time through the three contracts of decision 0006,
  `PlantModel`, `EnvironmentModel` and `SensorModel`, with simple models as
  their defaults. The examples, the live stream and the actions a policy
  requests run through it.
- **The run**, built from P05 to P09: the house's air every minute, the
  sun through the glazing, the organ-level crop living each day in that
  air and light, the sensors sampling the run, and its checkpoints,
  branches and replay. The reference scenario is a run, and the viewer
  draws one. Some of its parts are exchangeable already (`WeatherSource`,
  `AirflowModel`, `CropLight`, the plant's `Environment`), but the house's
  air (`WholeHouse`, `ClimateRun`) and the crop (`RunCrop`) are classes it
  builds directly.

So a model author implements a contract that the reference scenario never
calls, a policy can close the loop only on the simple model, and every
change to how a greenhouse behaves has two places to go.

Keeping both, each with a stated job (the engine for fast batch runs, the
run for the detailed greenhouse), was weighed and rejected: it is two
logics to maintain, and every model would be written twice or reach only
half the scenarios.

The simulator must serve extremely simple greenhouses (one box at a
constant climate, a few plants, a day at a time) and extremely complex ones
(a whole house with its air cell by cell or from CFD, the sun and its
shadows, an organ-level crop, noisy sensors), and everything between.

## Decision

- **There is one simulator: the run.** No model, scenario or feature is
  added to the engine's own day; it is fixed when broken, and goes once
  the run does what it does.
- **The run is made of parts, and each part has a ladder of
  implementations from the simplest to the richest.** The parts are at
  least the weather, the house's air, the light, the crop, the sensors and
  the devices. The house's air, for example, runs from a prescribed or
  constant climate, through one well-mixed volume (`WholeHouse`) and the
  air cell by cell (`ClimateRun`), to CFD (decision 0027); the crop from
  the simple daily model to the organ-level one. A scenario chooses a rung
  for each part. A simple rung is first-class, fast, tested and used, not
  a stub, and a part's rung sets how finely it steps: the simplest step a
  day at a time.
- **Each part has a contract,** written as decision 0006 says, a minimal
  `typing.Protocol` in its domain's `contract.py` whose docstring states
  the rules an implementation keeps, and a conformance test run over every
  implementation. The engine's three contracts move onto the run: the
  simple plant model becomes a rung of the crop beside the organ-level
  one, the simple environment the lowest rung of the house's air, and the
  sensor model a way of sampling the run.
- **The run is composed from its parts' contracts only.** It never names
  an implementation, and a part reads another only through the run: the
  crop takes its air and light from the run, not from `WholeHouse`.
- **A policy drives the run.** The actions it requests
  (`greenhouse_protocol.action`) are carried out on the run, and its
  observations come from the run's sensors. A day-by-day interface for a
  policy, `SimulationEngine`'s today, stays, built on the run.
- Left to P10, which decides them with its first model: how a scenario
  names its rungs (the manifest, a registry), where a model's parameters
  live (`AUDIT.4`), and devices described by their capabilities
  (`AUDIT.3`).

## Consequences

- P10 is the work. Its first step takes one part through all of this, end
  to end: a contract, two rungs, chosen by the scenario's manifest, kept
  in a checkpoint and drawn by the viewer. The other parts follow.
- Until then the engine's day only takes fixes. The examples, the live
  stream and actions move to the run once it carries actions out;
  `greenhouse_sim.engine` and the engine's contracts stay public until
  then, and are deprecated in the release that moves them.
- The simple models keep their numbers when they become rungs: the
  reference baseline (`greenhouse_sim/tests/test_reference_baseline.py`)
  holds them, and the move is checked against it.
- A new model is a rung of a part of the run. Until that part has its
  contract, its author starts from the part's current classes and writes
  the contract with it.
- Decision 0006's contracts are superseded in what they plug into, the
  engine's day, and not in how a contract is written.
- Worth revisiting if a simple scenario on the run cannot be made about as
  cheap as the engine's day: that would mean the ladder needs a coarser
  clock than the run's, not a second simulator.
