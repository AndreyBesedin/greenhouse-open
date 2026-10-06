# greenhouse-sim

A deterministic greenhouse simulator that produces canonical observations.
Part of [greenhouse-open](../README.md). Apache-2.0.

- **A hidden world, noisy sensors.** `GreenhouseWorld` holds what is really
  true. Each step publishes only noisy `Observation`s of it.
- **Semantic actions.** `SimulationEngine.apply_actions` validates each
  `RequestedAction` against the world and executes the accepted ones through
  a pluggable `ActionExecutor`, returning an `Event` for each.
- **Deterministic.** The same scenario, seed and actions always produce the
  same records.
- **Ground truth for evaluation only.** `greenhouse_sim.ground_truth` reports
  the noiseless values, and `greenhouse_sim.evaluation` scores observations
  against them. Nothing on the observation path exposes them.
- **Scenarios.** `greenhouse_sim.scenarios` holds ready-made worlds; a
  `ScenarioConfig` describes the greenhouse (its `Envelope` and its
  `Layout`), crop, dynamics and sensor noise, and nothing about who manages
  the greenhouse. Each scenario's layouts are JSON files in
  `scenarios/layouts/` (decision
  [0020](../docs/decisions/0020-scenario-layouts-are-declarative-json-files.md)).
- **Pluggable models.** Plant, environment and sensor models plug into the
  engine through small contracts. Simple reference models are the default.

```python
from datetime import UTC, datetime
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

engine = SimulationEngine(SCENARIO_REGISTRY["gh_002"])
world = engine.initialize(["gh_002_plant_001"], greenhouse_id="gh_002")
step = engine.advance(world, day=1, timestamp=datetime(2026, 3, 1, tzinfo=UTC), simulation_id="run")
print(step.observations)
```

More complete runs are in the repository's [examples](../examples/).

## How it is built

The simulator core is plain Python with no server, database or browser. The
local API and the browser viewer are adapters around it: they depend on the
core, never the other way round.

```text
greenhouse_sim/
  greenhouse_sim/
    core/          the engine, world checkpoints and seeded randomness
    world/         the hidden world's state, and geometry conventions
    biology/       plant models; tomato/simple is the reference model
    environment/   environment models; simple.py is the reference model
    sensors/       sensor models: what instruments report of the world
    actions/       validating and carrying out semantic actions
    scenarios/     ready-made worlds
    evaluation/    scoring against ground truth, its only reader
    scene/         the world as a renderable scene for a viewer
    api/           a thin local HTTP API for the viewer (adapter)
  web/             the browser viewer (adapter, not part of the wheel)
```

- **A day.** The environment model produces the day's climate, the plant
  model develops the crop in it, and the sensor model reports what
  instruments would read. Each model is passed to `SimulationEngine` and
  defaults to the simple reference model. What a model must do is stated in
  its domain's `contract.py`, and contract tests check every implementation.
- **World and model state.** The world's entities describe what is: sizes,
  ages, stages, root-zone water, harvest. The values a model invents for
  itself, such as a plant's vigour, live in that model's own section of the
  world (`GreenhouseWorld.plant_model`), which nothing else reads.
- **Geometry.** Metres and radians, right-handed axes with z up, the ground
  at z = 0.
- **Headless by design.** Tests fail if a simulator module imports the API,
  if a simulator run loads a web framework, an HTTP server or the API, or if
  anything but evaluation reads ground truth.

## Public API

Import from these modules. They stay where they are while the implementation
behind them moves.

| To | Import from |
| --- | --- |
| Run a simulation | `greenhouse_sim.engine`, `greenhouse_sim.scenarios`, `greenhouse_sim.world`, `greenhouse_sim.world.envelope` |
| Keep a run between steps | `greenhouse_sim.checkpoints` |
| Carry out actions another way | `greenhouse_sim.executor` |
| Advance a world without the engine | `greenhouse_sim.world_builder` |
| Score readings against the truth | `greenhouse_sim.ground_truth`, `greenhouse_sim.evaluation.observation_accuracy` |
| Write or compose a model | `greenhouse_sim.biology.contract`, `greenhouse_sim.environment.contract`, `greenhouse_sim.sensors.contract`, and the simple models in `greenhouse_sim.biology.tomato.simple.model`, `greenhouse_sim.environment.simple`, `greenhouse_sim.sensors.generation` |
| Draw a simulation | `greenhouse_sim.world.geometry`, `greenhouse_sim.scene.snapshot` |

Everything else is internal and may move. `tests/test_public_imports.py`
lists every public name.

## The viewer

The browser viewer shows what the simulator is doing, in 3D: a scenario
before its first day, or live, growing day by day as the simulator advances
it, with controls to pause, step, reset and change its speed. Start the local
API, then the viewer:

```bash
python -m greenhouse_sim.api                    # http://127.0.0.1:8765/api
cd greenhouse_sim/web && npm ci && npm run dev  # Node 24
```

See [web/README.md](web/README.md) for the viewer's own checks.

## Where it is going

The simulator is growing into a visual, physical simulation environment,
one project at a time: the [roadmap](../docs/roadmap/README.md) describes
the projects and their status, and the
[decision records](../docs/decisions/README.md) explain the choices made
along the way.

## Dependencies

`greenhouse-protocol`, Pydantic 2 and NumPy. The local API uses only the
standard library. The viewer is a separate npm package and is not part of
the Python distribution.
