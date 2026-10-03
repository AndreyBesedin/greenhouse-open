# 0004: Organize `greenhouse_sim` by simulation domain

**Status:** Accepted
**Date:** 2026-10-03

## Context

`greenhouse_sim` was a flat set of modules plus a `dynamics/` folder. The
roadmap adds plant models, environment fields, sensors, geometry, an API and
a viewer, each of which needs a clear home that does not grow one module or
blur the boundary between simulator core and adapters. Examples, the package
README and downstream applications already import from some of the existing
module paths, listed in `greenhouse_sim/tests/test_public_imports.py`.

## Decision

- Code is grouped by simulation domain: `core/` (engine, checkpoints, seeded
  randomness), `world/` (hidden world state), `biology/tomato/` (the tomato
  dynamics), `environment/` (environment models), `sensors/` (observation
  generation) and `actions/` (validation, effects of accepted actions,
  executors).
- Modules that belong to no single domain stay at the package root for now:
  `records` (record identifiers), `world_builder` (until P-1.3 makes the
  current dynamics an explicit backend), `ground_truth` (whose evaluation-only
  import path a test enforces), `scenarios` and `evaluation`.
- Code inside the package imports from the module that defines a name.
  Package `__init__` files hold only a docstring, except where a package
  replaces a module that was a public import path.
- Every public import path keeps working. `greenhouse_sim.engine`,
  `greenhouse_sim.checkpoints` and `greenhouse_sim.executor` become
  re-export modules, and `greenhouse_sim.world` re-exports the state types
  from its `__init__`. They are not deprecated. Which import paths form the
  long-term public interface is settled when the package documentation is
  rewritten in P-1.10.
- Repository checks that name file paths move with the files. A test fails if
  a sensitive path in the risk gate no longer exists.

## Consequences

- New models and backends have an obvious home, and a module's location says
  which domain owns it.
- The re-export modules are a small, deliberate duplication of paths until
  P-1.10 decides what to keep.
- Moving a file now means updating its importers explicitly. That is visible
  in review rather than hidden behind a re-export.
