# 0011: The public API is the top-level modules, the model contracts and the scene

**Status:** Accepted
**Date:** 2026-10-03

## Context

Decision 0004 regrouped `greenhouse_sim` by domain and kept the import paths
callers already used (`greenhouse_sim.engine`, `.world`, `.checkpoints`,
`.executor` and others) working through re-exports. It left open which paths
form the long-term public interface, to be settled with the package
documentation in P-1.10.

The roadmap will keep reshaping the internals: an organ-level tomato model
(P03), environment fields (P04), sensors (P06). Callers should not have to
follow those moves. Model authors and viewers, meanwhile, need a few deeper
types: the model contracts, the simple models to compose with, and the
geometry and scene snapshot.

## Decision

- The short top-level modules are the stable way to run a simulation:
  `greenhouse_sim.engine`, `.scenarios`, `.world`, `.world_builder`,
  `.checkpoints`, `.executor`, `.ground_truth` and
  `.evaluation.observation_accuracy`. They are facades, not deprecated
  re-exports, and the implementation behind them may move freely.
- Writing or composing a model goes through the contracts
  (`biology.contract`, `environment.contract`, `sensors.contract`) and the
  simple models (`biology.tomato.simple.model`, `environment.simple`,
  `sensors.generation`). `greenhouse_sim.world` also exports
  `PlantModelState`.
- Looking at a simulation goes through `world.geometry` and
  `scene.snapshot`.
- The local API's command, `python -m greenhouse_sim.api`, is public. Its
  Python modules are not.
- Everything else is internal and may move without notice.
  `greenhouse_sim/tests/test_public_imports.py` lists every public name;
  removing or moving one is a breaking change.

## Consequences

- The package README documents the API by task, and the test keeps the
  documentation and the code in step.
- Internal moves in later projects need no compatibility re-exports unless
  they touch a listed path.
- The simple sensor model is public at `sensors.generation`, a name that
  describes its module rather than its role. A clearer path can be added as a
  facade later without breaking this one.
