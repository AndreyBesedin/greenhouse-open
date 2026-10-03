# P-1: Restructure `greenhouse_sim`

**Status:** in progress. Part of the [simulator roadmap](README.md).

## Goal

Reorganize `greenhouse_sim` into a modular foundation for the visual and
physical simulator (P00 to P09) **without materially changing its behavior
first**. Today the package is a daily logical world with a scalar environment,
simple plant dynamics and noisy canonical observations. After P-1 it has
explicit homes for simulation time, hidden world state, spatial geometry,
biology backends, environment fields, sensor backends, actions, scenarios and
evaluation, plus a thin local API and a browser viewer around the headless
core. P00 then builds the 3D renderer on top.

The current simulator already has properties the future design depends on.
They are assets to keep, not legacy to replace:

- hidden truth is separate from observations;
- the same semantic actions serve simulation and future real executors;
- behavior is deterministic from explicit seeds;
- ground truth leaves only through an evaluation interface;
- `SimulationEngine` is plain Python with no database, server or UI;
- scenarios are separate from management policy;
- characterization tests pin current behavior;
- dependency tests keep each package independently publishable.

## What must stay stable

Unless a step explicitly says otherwise:

1. the public contracts of `greenhouse_protocol`;
2. the examples;
3. the deterministic reference scenarios (`gh_001`, `gh_002`, `gh_demo`);
4. the separation of hidden world and observations;
5. evaluation-only ground truth;
6. the semantic action path;
7. running `greenhouse_sim` with no UI, server or database;
8. the existing characterization tests.

## Target layout

Indicative; exact module names may change during implementation. The fixed
point is that the API and the viewer are adapters around the simulator core,
never part of it.

```text
greenhouse_sim/
  greenhouse_sim/
    core/          engine, checkpoints, seeded randomness, simulation time
    world/         hidden world state, identifiers, geometry contracts
    biology/
      tomato/
        simple/    the current daily model, kept as the reference model
    environment/   environment state, the simple model, field interface
    sensors/       observation generation and sensor models
    actions/       validation and execution
    scenarios/
    evaluation/
    api/           thin local adapter for the viewer
  web/             React and TypeScript viewer
  tests/
```

The viewer lives with the simulator because it is the simulator's
visualization and debugging interface. Simulator releases can ship a
compatible viewer, contributors work on the whole experience in one place,
`greenhouse_protocol` stays UI-independent, and downstream applications can
use the simulator and protocol without the viewer.

Existing tooling (Python packages with their own `pyproject.toml`, pytest,
strict mypy, Ruff, GitHub Actions) stays. A change of package manager or
workspace layout happens only if it clearly improves the combined Python and
TypeScript workflow.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P-1.1 | `test(sim): capture the simulator baseline before restructuring` | Done ([#4](https://github.com/AndreyBesedin/greenhouse-open/pull/4)) |
| P-1.2 | `refactor(sim): introduce internal package boundaries without behavior change` | Done ([#9](https://github.com/AndreyBesedin/greenhouse-open/pull/9)) |
| P-1.3 | `refactor(sim): isolate current dynamics as the simple reference backend` | Done ([#10](https://github.com/AndreyBesedin/greenhouse-open/pull/10)) |
| P-1.4 | `refactor(sim): separate world state from model-specific latent parameters` | Done ([#11](https://github.com/AndreyBesedin/greenhouse-open/pull/11)) |
| P-1.5 | `feat(sim): introduce backend capability contracts as minimal protocols` | Planned |
| P-1.6 | `feat(sim): introduce a scene and geometry snapshot contract` | Planned |
| P-1.7 | `chore(web): add the browser package inside greenhouse_sim` | Planned |
| P-1.8 | `feat(api): add a thin local simulator-viewer adapter` | Planned |
| P-1.9 | `ci: extend CI to the browser package` | Planned |
| P-1.10 | `docs(sim): document the new architecture and developer workflow` | Planned |

### P-1.1: Capture the simulator baseline

Give the restructuring a measurable answer to "did this change the
simulator?".

- Pin every import path that the examples, the package README and downstream
  applications use (`tests/test_public_imports.py`). When a module moves, its
  old path keeps resolving through a re-export until removing it is a
  deliberate change.
- Cover `InMemoryWorldCheckpoints`, which had no tests and is about to move.
- Record a day-by-day baseline of every reference scenario
  (`tests/test_reference_baseline.py`). Each scenario is run with all its
  plants for its full duration, under a fixed action schedule that reaches
  every action type and every validation refusal. Each day is reduced to
  digests of hidden state, observations, ground truth and action outcomes,
  and each run to a readable summary of its final state.

Design choices:

- A failure names the scenario, the first day that diverged and the parts
  that moved, so a behavior change is located rather than merely detected.
- The hidden-state digest leaves out the random draws the simple model makes
  when it creates a plant or a fruit. P-1.4 can move those into
  model-specific state without touching the baseline, unless their effect
  changes.
- Floats are rounded to six decimal places before hashing, so differences
  between platforms' maths libraries are not read as behavior. The baseline
  is generated on macOS and verified on Linux in CI.

### P-1.2: Introduce internal package boundaries

Create `core/`, `world/`, `biology/`, `environment/`, `sensors/` and
`actions/`, and move code into them incrementally, with re-exports at the old
paths. The existing characterization and conformance tests change only in
their imports. The risk gate and dependency tests that name file paths are
updated in the same change, so moving a file never silently removes it from
their protection.

As implemented (see [decision 0004](../decisions/0004-organize-greenhouse-sim-by-domain.md)):

| Before | After |
| --- | --- |
| `engine.py`, `checkpoints.py`, `rng.py` | `core/` |
| `world.py` | `world/state.py` |
| `dynamics/growth.py`, `ripening.py`, `water.py` | `biology/tomato/` |
| `dynamics/environment.py` | `environment/simple.py` |
| `observations.py` | `sensors/generation.py` |
| `actions.py`, `validation.py`, `executor.py` | `actions/effects.py`, `actions/validation.py`, `actions/executor.py` |

- One commit per domain. Every moved file is unchanged apart from its import
  lines, and the reference baseline from P-1.1 passes unchanged after each
  commit.
- `greenhouse_sim.engine`, `.checkpoints` and `.executor` remain as
  re-export modules, and `greenhouse_sim.world` re-exports the state types,
  so every path in `tests/test_public_imports.py` still resolves. Paths that
  were internal (`rng`, `observations`, `validation`, `actions`,
  `dynamics.*`) are not re-exported; their importers were updated.
- `records`, `world_builder`, `ground_truth`, `scenarios` and `evaluation`
  stay where they were. `world_builder` is P-1.3's subject.
- The risk gate's sensitive paths follow the engine, the randomness and
  observation generation, and a new test fails if any sensitive path stops
  existing.

### P-1.3: Isolate the current dynamics as the simple reference backend

The current daily tomato and environment logic becomes explicitly the
*simple* model: fast enough for smoke tests and examples, a comparison point
for future models, and usable while P03 and P04 mature. It stops defining how
plant and environment simulation work in general. Reference scenarios produce
the same baseline.

As implemented:

- The daily tomato rules (growth, ripening, water) move into
  `biology/tomato/simple/`. That leaves `biology/tomato/` for P03's
  organ-level model, which is a different model rather than an evolution of
  these rules.
- One plant's day (`initial_plant`, `advance_plant`) moves out of
  `world_builder` into `biology/tomato/simple/daily.py`. The simple
  environment model in `environment/simple.py` derives its own random stream
  from the scenario seed and the day. `world_builder` is left only composing
  the two: the environment advances, then each plant responds to it. Its
  public functions are unchanged.
- The package docstrings of both simple models state what they model, what
  they leave out and why they stay. One known limit is that fruit ripens long
  before it nears its target size, so harvested fruit averages between about
  0.2 g and 2 g across the reference scenarios.
- A new test pins that a plant develops identically whatever other plants
  share the greenhouse, because each plant's randomness is keyed by its own
  identity. Batching and parallel runs depend on that.

Open questions for P-1.4 and P-1.5:

- `ScenarioConfig` mixes the description of the world (size, seed, duration,
  sensor noise) with the simple models' tuning parameters. Separating them
  changes a public type, so it waits until backends have contracts and their
  own parameters.
- Watering adds to the simple model's water reservoir directly from
  `actions/effects.py`, so an action's effect is tied to one plant model.
  That coupling has to be resolved when world state and model state are
  separated. *Resolved in P-1.4.*

### P-1.4: Separate world state from model-specific parameters

Separate simulator identity and semantic state from the simple tomato model's
latent parameters (such as growth multipliers and ripening targets) and from
the current scalar environment, so that new tomato or environment models do
not grow one world module. No move to array storage yet. Ground-truth access
rules stay enforced.

As implemented (see [decision 0005](../decisions/0005-keep-model-state-apart-from-the-world.md)):

- `PlantWorld` and `Fruit` keep only what the world is. The simple tomato
  model's own values (a plant's growth multiplier and water stress; a fruit's
  target diameter, growth-rate multiplier and ripening day) move to
  `SimpleTomatoState` in `biology/tomato/simple/state.py`, keyed by plant and
  fruit identifier, and the world carries it as `GreenhouseWorld.plant_model`.
- The model's rule functions take that state explicitly, and draw random
  values in the same order, so the reference baseline is unchanged.
- Watering now fills the root zone in the action's own code, instead of
  calling into the tomato model.
- Two new tests: a world saved as JSON loads back unchanged, and nothing
  outside the model and `world_builder` reads `plant_model`.
- The environment needed no split: the simple environment model keeps no
  values of its own beyond the temperature and humidity it produces.
- This is a breaking change to the world types and their serialized form.
  Worlds saved before it do not load, which is acceptable while the packages
  are unpublished.

### P-1.5: Introduce minimal backend contracts

Only the interfaces the roadmap already justifies: plant development,
environment and sensor generation. No empty interfaces for hypothetical
components. Contract tests run the existing simple backends.

### P-1.6: Introduce a scene and geometry snapshot contract

The minimal simulator-side types P00 needs: entity identifier, transform,
geometry descriptor, and visual or debug metadata, with no renderer concepts
in the domain state. The first snapshot may contain only the ground,
reference markers and placeholder plants. It is deterministic, serializable
and schema-valid.

### P-1.7: Add the browser package

`greenhouse_sim/web/` with React, TypeScript and Vite, frontend tests and
build, and a bootstrap page that identifies itself as the `greenhouse-sim`
viewer and shows build metadata.

### P-1.8: Add a thin local API adapter

A minimal local API around `SimulationEngine`: health, version metadata, the
scenario registry and the initial scene snapshot. It owns no simulation
logic, is not needed to run the simulator, and does not expose ground truth
on the observation path. Visible result: the browser lists `gh_001`, `gh_002`
and `gh_demo` from Python. Core tests run without importing the API, and API
integration tests run separately.

### P-1.9: Extend CI to the browser package

Keep the Python checks and add frontend install, tests, build and a
lightweight browser smoke test. Expensive CFD or rendering work stays out of
default CI.

### P-1.10: Document the architecture and workflow

Update the package README and the root README: the roadmap, the core and
viewer boundary, the package layout, how to run the examples and the viewer,
and the guarantee that the core stays headless.

## Final QA: `refactor-baseline`

Before P00 starts:

1. The examples still run.
2. The reference scenarios still match their recorded baseline.
3. Protocol conformance tests pass.
4. Ground truth is still evaluation-only.
5. `SimulationEngine` runs without web or API dependencies.
6. The simple plant and environment model runs through the new backend
   boundaries.
7. A scene snapshot is generated deterministically.
8. The browser package builds and lists the current scenarios.
9. Python checks and the new frontend checks pass in CI.

## Acceptance criteria

- [ ] `greenhouse_protocol` and `greenhouse_adapters` keep their roles.
- [ ] `greenhouse_sim` has internal boundaries compatible with P00 to P09.
- [ ] The current simulator survives as a fast reference backend.
- [ ] Current behavior is characterized before any model changes.
- [ ] The API and viewer are optional and do not reach into the headless
      core.
- [ ] The scene-snapshot boundary exists for P00.
- [ ] CI covers the Python packages and the viewer.
- [ ] No dependency on private or proprietary code is introduced.
