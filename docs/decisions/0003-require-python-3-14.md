# 0003: Require Python 3.14

**Status:** Accepted
**Date:** 2026-10-03

## Context

The packages required Python 3.12 or newer, and CI and the type checker
targeted 3.12. That was the floor the project started with, not a deliberate
choice. 3.12 has long been in security-fix-only maintenance. The packages are
not yet published to PyPI, so no external installation depends on the floor.

Before deciding, the full repository check was run unchanged on Python 3.14:
linting, strict type checking and every test passed, including the
simulator's reference baseline, so the simulator behaves identically. The
compiled libraries the roadmap expects to use (NumPy, Pydantic, JAX, MuJoCo)
publish 3.14 wheels.

The alternatives were to keep the 3.12 floor and test on several versions,
or to raise the floor to 3.13.

## Decision

All three packages require Python 3.14 or newer. Ruff, mypy and CI target
3.14. Implemented in
[#5](https://github.com/AndreyBesedin/greenhouse-open/pull/5).

## Consequences

- The restructured simulator can be written for 3.14 directly: deferred
  evaluation of annotations for models that refer to each other, and later
  the free-threaded build and subinterpreters for parallel batch rollouts.
- CI tests one Python version.
- Consumers on 3.12 or 3.13 cannot install new releases and must upgrade.
- Code that has to run inside an interpreter we do not control, such as a
  renderer's embedded Python, stays behind a process boundary so that it does
  not constrain the core.
- Revisit when Python 3.15 is released and the compiled dependencies ship
  wheels for it.
