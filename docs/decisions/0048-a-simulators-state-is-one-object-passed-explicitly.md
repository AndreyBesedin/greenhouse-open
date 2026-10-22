# 0048: A simulator's state is one object, passed explicitly

**Status:** Accepted
**Date:** 2026-10-22

## Context

The simulator keeps its state in module globals: the scenarios, read from
their manifests as it is imported (`SCENARIO_REGISTRY`); the runs, crops,
sunlight, checkpoints and kept states its services keep, each in a `Store`
(W9); the runs it plays back, with their worker threads; the cursors it has
given consumers; and, owned by the API's server, the live runs and their
pacing threads. Tests reset the globals through fixtures (`afresh`,
`no_playbacks`) and a list of every store ever made (`forget_everything`);
the threads are stopped and not all of them joined. The repository audit
asks for one object that owns all of it, made by the server and by a test's
fixture (`AUDIT.15`).

A setup builder (P12) turns an installation into a scenario while the
simulator runs, which a registry fixed at import cannot take; and the
action plans of P13 are carried out by the runs a simulator plays.

## Decision

- **A `Simulator` owns the state:** its catalogue of scenarios, the stores,
  the runs it plays back, the consumers' cursors and the live runs. The
  server makes one, or is given one; a test's fixture makes its own.
  `close()` stops what it plays and joins its threads.
- **It is passed explicitly.** A service that keeps or plays runs takes
  `simulator: Simulator`; one that only looks a scenario up takes the
  `catalogue: Scenarios` it looks in; a pure helper takes neither. This is
  how a service already takes its `RunRequest` (W11) and a live route its
  `LiveRuns`, and mypy checks it.
- **The packaged scenarios never change.** They are read once into
  `PACKAGED` (`scenarios/catalogue.py`). A simulator's catalogue begins with
  them and registers others while it runs, by their greenhouse's identifier:
  never in place of a packaged scenario, and never a different scenario
  under an identifier already registered, since the runs it keeps know a
  scenario by its identifier alone. A changed scenario is registered under
  an identifier of its own.
- **Considered and not chosen:** the services as classes composed by the
  `Simulator`, which re-indents twenty-five modules and gives each of them
  an object for no second implementation; and a context variable holding
  the current simulator, which mypy cannot check and which threads started
  for a playback, a live run or a request do not inherit.

## Consequences

- The change comes in steps, top down from the routes: the catalogue; a
  simulator the server makes, owning the live runs; the routes answering
  from it; its playbacks and cursors; the services that read runs, then
  those that keep them, taking it; the lookups taking a catalogue; and last
  the stores made by each simulator instead of the module. Until that last
  step the simulator's stores are the module's, shared as they are today.
- Run ids, checkpoint ids, replay digests, the opening days and the golden
  views do not change in any step; the tests that hold them say so.
- `SCENARIO_REGISTRY` stays importable, the packaged scenarios as before.
- A test that only reads a packaged scenario needs no simulator; one that
  keeps or plays runs asks for one, and starts from a clean slate without a
  list of every store.
