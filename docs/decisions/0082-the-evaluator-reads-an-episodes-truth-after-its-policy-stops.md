# 0082: The evaluator reads an episode's truth after its policy stops

**Status:** Proposed, with [P25](../roadmap/p25-measures-and-baselines.md)'s plan
**Date:** 2026-11-16

## Context

- **Truth leaves a run by a path of its own** (decision 0059):
  `greenhouse_sim.ground_truth`, which only `greenhouse_sim.evaluation`
  imports, and which the policy port's modules may not import
  (`tests/test_dependencies.py`). It gives what each point sensor truly
  sampled at its sample moments, and what the crop's walk truly found.
- **Decision 0061 asks for evaluator-only instrumentation** where a
  measure needs it: the true air through time, and the controller's
  switches.
- **The run has both, and no evaluator reads them:** the house's air as
  one volume every minute, with the heat its heaters have given
  (`climate.house.HouseAir`, `services.climate_readings`); the grid's air
  at a moment (`climate.house.grid_mean`); the levels the controller runs
  its devices at (`WholeHouse.controlled_at`), the commands applied, and
  which a command has taken over (`ClimateRun.controls`). People read
  some of them through the local API (decision 0036).
- **A steered run's truth is the steered run's:** the scenario's run with
  the plan the policy's revisions left, which the playback holds and the
  experiment's runner does not hand on. `ground_truth` scores a steered
  run's readings when given that run.
- **A record is scored later too:** a new measure, or a new version of
  one, is scored on records already written. P23's `check` runs a record's
  episode again and compares its digest.
- **The options weighed:** the truth through the policy's port, behind a
  flag (no: decision 0061's allowlist forbids it); the run as carried out
  written into the record, so that a record is scored without being run
  again (a change of the record's format, and a second account of what the
  outcomes already say); or the run as carried out handed to the evaluator
  in the process, and a record scored later run again first.

## Decision

- **Only `greenhouse_sim.evaluation` reads an episode's truth,** and only
  once its policy has stopped. The runner hands the evaluator the run as
  carried out, a `RunRequest` of the scenario's run on the episode's
  condition with the plan its revisions left, after `stop`.
- **The evaluator's instruments,** in `greenhouse_sim.evaluation`:
  - the house's air through time: the air the run draws, averaged over
    the house's air cells, every minute, its temperature, relative
    humidity and CO₂;
  - the heat given: the heaters' heat to the air, from the house's own
    count, over any window;
  - the equipment's states through time: each device's level, and each
    switch with its moment, its level, and whether a loop or a command set
    it;
  - the crop's harvest: the run's harvest events, read for a harvest
    reported as the crop model's prediction (decision 0081), never
    compared.
- **None reaches a policy:** not the port, the consumer interface or the
  capability context. The dependency test holds the port's modules, and
  the baselines' (decision 0081), to importing none of them.
- **A record scored later is run again first,** by `check`, and scored only
  if its digest is the record's. A record that does not replay is not
  scored, and says so; a policy whose episodes cannot be run again, such
  as a remote one, is scored as it runs.
- **The local API is unchanged:** people read the truth there, as decision
  0036 has it.

## Consequences

- **A measure of the house can be scored on any episode,** steered or
  not, without the policy having been able to see what it is scored on.
- **The episode's record does not change,** and no digest moves.
- **Scoring a record later costs a run of its episode.** Scores written as
  an experiment runs cost nothing more than reading the run.
- **The run as carried out becomes readable** outside the playback, for
  the evaluator; it stays out of the policy's reach.
- **Worth revisiting:** if a policy in a process of its own, or a remote
  one, needs scoring from its record alone, which would ask for the run as
  carried out in the record; or if a measure needs the air at each place in
  the house rather than its mean.
