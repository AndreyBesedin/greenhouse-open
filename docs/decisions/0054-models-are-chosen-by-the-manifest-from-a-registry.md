# 0054: Models are chosen by the manifest, from a registry

**Status:** Accepted, with P14.1
([P14](../roadmap/p14-models-by-manifest.md)).
**Date:** 2026-10-23

## Context

Decision 0035 made the run the one simulator, each part of it a ladder of
models. The repository audit found that models are still chosen by code,
not by the manifest (`AUDIT.2`):

- **Parts the manifest chooses:** the weather, the air field drawn, and the
  crop, as unions in the scenario's configuration.
- **Parts code chooses:** the house's air, sun and glazing, each device and
  the controller.
- **One part on two paths:** the simple crop runs only in the engine's day,
  and in a run means no crop at all.
- **Settings at the top:** one model's settings sit at the top of every
  scenario (`AUDIT.4`).
- **Ten files for a device:** adding one touches ten files across the
  simulator and the viewer (`AUDIT.3`).
- **No record of models:** a run's identity covers its parameters but not
  the models or their versions. A checkpoint tells one crop model from
  another by testing for the organ crop.

## Decision

- **Each part of a run has one contract and named models.** A model
  implements its part's contract, a Protocol (decision 0006). It has:
  - a name, unique within its part;
  - a version, changed whenever its numbers change for the same parameters;
  - a parameter model;
  - a state model, if it keeps state.

  A conformance test holds every model of a part.
- **A registry holds them,** each part's models by name, with a default:
  today's choice. The packaged models register in the package. Models from
  another package register through an entry point (`greenhouse_sim.models`),
  loaded only when a manifest names one, once the project decides to admit
  them.
- **The manifest chooses.** Its next format adds `models`: for each part, a
  model by name and its parameters, in a section checked against that
  model's parameter model. A part left out runs its default. No model's
  settings sit at the top of a scenario.
- **A run records its models.**
  - A run's identity covers each part's model, version and parameters, and
    its manifest answer lists them.
  - A checkpoint keeps each stateful model's state under its part, name and
    version. A run restores only a checkpoint of the same models and
    versions.
- **Devices are known by their capabilities and their shape,** not by
  their kind. The run, the scene and the viewer act on capabilities, so a
  device kind is a registered set of capabilities, parameters and a shape.
- **One complete extension comes first:** a model added end to end through
  the manifest, with its section, state, conformance test and viewer. What
  it shows the registry needs is recorded before the other parts move.

## Consequences

- **Adding a model or a device:** it is a module and a registration, held
  by its part's conformance test. The recipes in `docs/guides/` say so once
  P14 lands.
- **Packaged runs and consumers:**
  - A manifest migration that moves today's choices into `models` changes
    no run.
  - Recording model versions in a run's identity changes the packaged runs'
    ids once. The changelog announces it to consumers (decision 0040).
- **The simple crop:** it becomes a rung of the run, and the engine's
  second path for the crop goes.
- **The viewer:** it stops switching on device kinds and draws a device by
  its shape and capabilities. A device kind it was not built with is still
  drawn and listed.
- **Worth revisiting:**
  - if models from other packages need isolation from the simulator's
    process;
  - if a part's models need different contracts at different rungs, which
    would make the part two parts.

## Open questions, settled

The design's open questions are settled as it proposes, or, where it
proposed none, as the steps it lists have them:

1. **The pilot** is the simple crop as a rung of the run (P14.3).
2. **A model's version enters the run's identity** with P14.2, changing
   the packaged runs' ids once.
3. **Models from other packages** wait until a model from outside the
   repository asks for one: no entry point is loaded in P14. P14.4 records
   what the pilot showed, and the entry point is decided then.
4. **The crop part and rows:** the crop's section gives the parameters of
   the model the rows grow, and names it as they do; a manifest whose
   section names another is refused. Parameters for each variety are
   P12.4's, built on that section.
5. **Capabilities and actions** share one vocabulary, decided with P13's
   executor step.
