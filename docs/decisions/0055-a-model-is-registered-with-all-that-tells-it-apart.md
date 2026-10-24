# 0055: A model is registered with all that tells it apart

**Status:** Proposed, with P14.4
([P14](../roadmap/p14-models-by-manifest.md)).
**Date:** 2026-10-24

## Context

Decision 0054 asked for one extension made end to end before the registry
is generalised, and for what it showed to be recorded. P14.3 made it: the
simple crop became a rung of the run beside the organ crop, with its
parameters in a section of their own, its state in a checkpoint, a
conformance test of both and the viewer drawing it (#362, #364, #366,
#367). No organ number changed, and for the same temperatures the simple
crop's plants are the engine's.

What it showed:

- **A per-plant contract holds both models.** `CropRung`
  (`biology/crop_contract.py`) starts a plant, lives its day, carries crop
  work out and stands its crown; the run (`core.crop.RunCrop`) keeps the
  days, the plants kept, the carrying on from other runs and the locks. A
  rung keeps nothing. One method, `recorded`, serves the organ crop alone:
  where a day's crop work ends in a plant's history.
- **The services still tell the models apart.** Eight modules branch on
  the crop's model, not on the contract:
  - the rung built for a scenario, the crop's scene and the carrying on of
    one crop from another (`services/crop.py`);
  - a checkpoint's state model, read by the model's name (`CROP_STATES`),
    and what no run of it reaches (`_implausible`, `services/checkpoints.py`);
  - the walk's measure of a plant and its harvest events (`services/crop_log.py`);
  - the replay's organ counts (`services/replay.py`);
  - the scene and crowns before a run's first day, still drawn through the
    engine for the simple crop (`services/scenarios.py`, `services/sunlight.py`);
  - the run's own crop actions, which only the organ crop takes
    (`services/runs.py`, `services/gateway.py`).

  A third crop model would add a branch to each, and a member to the union
  of crops (`AnyCrop`).
- **A checkpoint's state is told apart by its model's name, beside it.**
  Pydantic cannot tell a union apart by a sibling field, so the state is
  read by a validator that looks the model up. Without it, organ plants
  under a simple crop's names were read as the organ crop's, passed its
  checks, and failed later inside the run.
- **One environment, read in part.** The run gives every model the same
  day (`LocalEnvironment`: temperature, light, CO₂, water status). The
  simple crop reads the temperature alone. Its root zone is its own, and
  drains, while the run says each plant is well watered: two root zones.
  Nothing waters a crop in a run.
- **Parameters fit the registry's pattern.** The crop's section is held
  under a field with its model's name as its `kind`, as the weather's and
  the air field's are. The section must name the rows' crop: the crop part
  has one model, while rows name theirs (decision 0050). Rows of different
  crops (P12.5) are more than one model of a part.
- **Settings without a part.** The simple crop's section still holds four
  settings of the engine's day: the bounds its air drifts within and its
  sensors' noises. The engine's environment and sensors are not parts of
  the registry.
- **A run's identity follows the configuration's shape.** It digests the
  configuration as written, so moving the settings into sections changed
  every run id without changing a number. The simple crop's version, raised
  to 2 when its runs began to grow it, changed its runs' ids for a change
  of numbers, as versions are meant to.
- **Contracts beside the configuration cycle.** The crop's contract could
  not join the engine's in `biology/contract.py`, which imports the
  scenario's configuration, which imports the run's crop: it has a module
  of its own.
- **Library users build and keep configurations.** A downstream
  application builds `ScenarioConfig` with the old settings at its top and
  stores its JSON. Those are read into their sections; reading them as the
  configuration's attributes broke.
- **No model from outside the repository asked for an entry point.**

## Decision

- **A model is registered with all that tells it apart,** so that the run
  and the services ask its registration and never branch on its name. Its
  registration holds:
  - its name, version and parameter model, as today;
  - for a model that keeps state, its state model, and a check of a state
    against the run it is restored into, which says what no run of the
    model reaches;
  - for its part, what the part's services need of a model. For the crop:
    its rung, built from the scenario; how its plants are drawn; and how a
    walk measures a plant.

  A model may answer more than its part asks, as the organ crop answers a
  plant's structure; that answer stays its own route's.
- **A checkpoint reads a state by its registration,** looked up by its
  part and its model's name, never by trying each state model in turn.
- **Every model of a part is given the same environment,** and says in
  its docstring what of it it reads. Water is the irrigation's when the run
  has one: until then a model's own root zone, if it has one, is its own,
  and drains as the model has it.
- **Settings that belong to no part go with the engine.** The engine's
  four settings leave the simple crop's section when the engine's
  environment and sensors become rungs of the run (P14.6), and its section
  then holds the simple crop's own.
- **The crop part keeps one model, its rows'**, until rows of different
  crops (P12.5) decide how a manifest gives each its model and parameters,
  in a decision of their own.
- **No entry point yet.** Models come from the repository until one from
  outside asks; decision 0054's entry point is decided then.

## Consequences

- **P14.6 starts with the crop:** its registration takes over the
  branches above, and the conformance test holds what a registration
  gives (its rung, its drawing, its walk's measure, its state's check), not
  only the rung. The parts it then registers (the house's air, sun and
  glazing, the sensors' sampler, the controller's loops) are registered
  the same way, each with what its part's services ask of it.
- **P14.5's devices follow the same rule:** a device kind is registered
  with its capabilities, parameters and shape, and the climate, the scene
  and the viewer ask its registration.
- **A third crop model** (the crops of plant research) is then a module,
  its parameter and state models and a registration, with no service
  changed.
- **The guides** (`add-a-plant-model` and the others) are written for the
  registration in P14.7.
- **Worth revisiting:**
  - if a part's services ask so much of a registration that the part's
    contract is split in two;
  - if a run's identity should be digested from its models' sections
    rather than from the configuration as written, so that reshaping the
    configuration changes no id; that would change every id once more.
