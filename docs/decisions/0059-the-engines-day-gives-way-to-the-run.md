# 0059: The engine's day gives way to the run

**Status:** Accepted, for P14.6's last step
([P14](../roadmap/p14-models-by-manifest.md)).
**Date:** 2026-10-28

## Context

Decision 0035 made the run the one simulator, and said what becomes of the
engine's day (`SimulationEngine`):

- its three contracts move onto the run: the simple plant model a rung of
  the crop, the simple environment the lowest rung of the house's air, and
  the sensor model a way of sampling the run;
- a day-by-day interface for a policy stays, built on the run.

Most of that is done:

- **The simple plant model** is a rung of the run's crop (P14.3): the run
  grows the simple crop by the model's daily rules
  (`biology/tomato/simple/daily.py`), from the run's air, each plant with
  its own root zone.
- **The house's air** has a model that is the whole house alone
  (`whole_house`, P14.6), and the sensors are a part with its model
  (`sampled`, P14.6).
- **A policy acts on the run,** through its gateway, in a loop that observes,
  plans, submits and advances the run's clock (P13.9, #393). The engine
  takes no actions any more, and the protocol's old action names are gone
  (#395, #396).

What remains of the engine's day is a second simulator beside the run:

- **What it is:**
  - `SimulationEngine` (`initialize`, `advance`), `world_builder` and the
    world it steps (`GreenhouseWorld`, with each model's own section);
  - its three contracts (`biology/contract.PlantModel`,
    `environment/contract.EnvironmentModel`, `sensors/contract.SensorModel`)
    and their simple models (`SimpleTomatoModel`, `SimpleEnvironmentModel`,
    `SimpleSensorModel`);
  - its checkpoints (`greenhouse_sim.checkpoints`: `WorldCheckpoints`,
    `InMemoryWorldCheckpoints`);
  - its ground truth (`greenhouse_sim.ground_truth`) and the evaluation
    that scores its observations against it
    (`greenhouse_sim.evaluation.observation_accuracy`).
- **Who uses it:**
  - **The viewer's live mode:** `services/live.py`, its routes
    (`/api/scenarios/{id}/live`), and the viewer's `live` source, which the
    source chooser offers beside a scenario's run. Decision 0041 kept it
    "for the scenarios it serves".
  - **Three examples:** running a simulation (01), storing and querying its
    records (02), and scoring readings against the truth (04).
  - **The root conformance test,** for the simulator's observations.
  - **The public API** (decision 0011): `greenhouse_sim.engine`,
    `.world_builder`, `.checkpoints`, `.ground_truth`,
    `.evaluation.observation_accuracy`, the three contracts and the simple
    models.
  - **About fifteen of the simulator's tests,** among them the reference
    baseline and the run characterization, which pin the engine's days.

Its numbers are not the run's: its air is its own daily climate, not the
house's, and its plants live in it. A reader of the viewer's live mode, or
of an example's records, sees a world no run has.

Three ways were weighed:

1. **Remove the engine's day:** move what uses it onto the run, then delete
   it.
2. **A day façade on the run:** keep `SimulationEngine`'s names, with each
   day advanced on a run. Its world would be the run's, not
   `GreenhouseWorld`, so callers would change anyway. It would also be a
   second interface beside the policy loop that P13.9 built for the same
   purpose.
3. **Keep the engine beside the run, frozen:** the two simulators' numbers
   would go on differing, which is what 0035 set out to end.

## Decision

The engine's day is removed, in four steps, each a pull request of its own,
all four in 0.5.0:

1. **The viewer's live mode gives way to a scenario's run.** Every packaged
   scenario already has a run the viewer draws, with its timeline, and a
   playback the viewer follows (decision 0041). The live source, its
   routes, its stream and `services/live.py` are removed. A `?live=<id>`
   address opens that scenario's run instead. The live mode is not kept as
   a view of a scenario's playback either: the playback the viewer follows
   has pace controls of its own.
2. **The examples run on the run:**
   - 01 plays a scenario's run and reads its observations, as a consumer
     does;
   - 02 stores and queries those records;
   - 04 scores the run's readings against the run's own values: the
     sensors' against the house's air where they stand, and the crop walk's
     against each plant as its model measures it without the walk's errors
     (`CropRegistration.measured`).
3. **Evaluation on the run's truth:** `greenhouse_sim.ground_truth` and
   `greenhouse_sim.evaluation.observation_accuracy` read the run, not
   `GreenhouseWorld`, with the same separation:
   - truth leaves by its own path;
   - only evaluation reads it.
4. **The engine and its world are removed:**
   - `SimulationEngine`, `world_builder`, `GreenhouseWorld` and its model
     sections;
   - the three contracts and their simple models;
   - the world's checkpoints.

   The simple plant's daily rules and its plant record stay
   (`biology/tomato/simple/daily.py`, `world.state.PlantWorld`), since the
   run's simple crop grows by them. The engine's reference baseline and
   characterization tests go with it. The run is pinned by its replay, its
   kept opening day and its run ids.

The public API (decision 0011) loses the modules above, and the README's
table and `test_public_imports.py` say so. It is a breaking change, and
lands in 0.5.0 with that release's others (P13.9's, P14's formats), so that
callers of the engine's day move once; its changelog names it.

## Consequences

- **One simulator:** every record, scene and example describes a run, which
  a consumer, the viewer and a policy all reach the same way.
- **Smaller code:** the engine's day, its contracts and their tests leave.
  The parts' contracts (`CropRung`, the house's air's models, the sensors)
  are the only ones a model is written against, as P14.7's guides will say.
- **What is lost:**
  - the live mode's own pace controls, which a run's playback has its own
    of;
  - the engine's daily climate, which no run used;
  - an engine-only shortcut to a season in seconds: a run of a season takes
    minutes to work out (decision 0041).
- **Downstream callers** of the engine's day move to the run and its
  consumer interface, as callers of its actions already do (P13.9).
- **Supersedes** 0041's "the simple live mode stays", and 0012's stream,
  which only the live mode used: a followed run's view asks its playback
  where its clock stands (decision 0041).
- **Worth revisiting:** if a caller needs a season in seconds that a run
  cannot give, a fast rung of each part, chosen by the manifest, would give
  it within the run, rather than a second simulator.

## Decided in its review

1. **The live mode** is removed, not kept as a pace-only view of a
   scenario's playback: removing it is less to keep, and the playback the
   viewer follows already has pace controls.
2. **The release:** all four steps land in 0.5.0, with its other breaking
   changes (P13.9, P14's formats), rather than in the release after.
