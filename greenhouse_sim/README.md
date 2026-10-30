# greenhouse-sim

A deterministic greenhouse simulator that produces canonical observations.
Part of [greenhouse-open](../README.md). Apache-2.0.

- **One simulator, the run.** A scenario's run works out its house's air,
  its sun, its crop and its devices, and publishes only noisy
  `Observation`s of them, as its sensors and the people walking its crop
  would (decisions 0035 and 0059).
- **Actions on the run.** A person, a policy or a schedule gives a run a
  plan of `greenhouse_protocol` actions through its gateway (`/actuation/v1`),
  and the run carries each out at its time, with an outcome (decision 0046).
- **Deterministic.** The same scenario, seed and actions always produce the
  same records.
- **Ground truth for evaluation only.** `greenhouse_sim.ground_truth` reports
  what a run's sensors and its crop walk truly measured, reading by reading,
  and `greenhouse_sim.evaluation` scores observations against it. Nothing on
  the observation path exposes it.
- **Scenarios.** `greenhouse_sim.scenarios` holds ready-made worlds; a
  `ScenarioConfig` describes the greenhouse (its `Envelope` and its
  `Layout`), crop, dynamics and sensor noise, and nothing about who manages
  the greenhouse. Each scenario is a versioned JSON manifest in
  `scenarios/manifests/` (decision
  [0031](../docs/decisions/0031-scenarios-are-versioned-json-manifests.md)),
  and its layouts are JSON files in `scenarios/layouts/` (decision
  [0020](../docs/decisions/0020-scenario-layouts-are-declarative-json-files.md)).
- **Models chosen by the manifest.** Each part of a run is a ladder of
  models, from the simplest to the richest, and a scenario's manifest names
  one rung of each (decision 0054).

A consumer reads a run as it reads any producer, through the local API's
consumer interface (decision 0040); the repository's
[examples](../examples/) play a scenario's run, store its records, score
them against its truth and act on it:

```bash
python examples/01_run_a_simulation.py
```

## How it is built

The simulator core is plain Python with no server, database or browser. Its
services do what a client asks of it (list scenarios, draw a scene, play a
scenario's run back), whatever the transport. The local API and the browser
viewer are adapters around them: the API's routes are only the interface to
the services, and nothing depends on the API or the viewer.

```text
greenhouse_sim/
  greenhouse_sim/
    domain/        the shared vocabulary: kinds, categories and stages that
                   more than one package uses; depends on nothing else
    core/          a run's clock and timeline, its crop, and seeded
                   randomness
    world/         the greenhouse's geometry conventions, house, layout and
                   equipment, the simple crop's plants, and the site that
                   places the greenhouse on the Earth
    biology/       plant models; tomato/simple is the simplest,
                   plant/ what fruiting crops' organ-level models share,
                   tomato/organ the tomato's organ-level model
    climate/       the house's air, its equipment and its control
    solar/         the sun's light, inside and on each plant
    sensors/       what instruments report of a run
    scenarios/     ready-made greenhouses, and the registry of models
    evaluation/    scoring against ground truth, its only reader
    weather/       the weather outside: its state at a moment, and where it
                   comes from
    fields/        environment fields: the greenhouse's air, cell by cell,
                   and the format they are exchanged in
    airflow/       airflow models, which produce fields: prescribed
                   patterns today
    cfd/           the air's geometry as a CFD solver is given it, written
                   as an OpenFOAM case, and OpenFOAM run out of process
    scene/         a greenhouse and its crop as a renderable scene for a viewer
    services/      what the simulator does for a client: scenarios, scenes,
                   layouts, fields, CFD geometry, runs played back and the
                   plant lab, independent of any transport
    api/           a thin local HTTP API for the viewer (adapter): the
                   interface to the services
  web/             the browser viewer (adapter, not part of the wheel)
```

- **A run's moments.** At each moment, commands set the devices, the air
  is worked out, the plants live each day that ended at a midnight, and
  the sensors and cameras sample what is there
  ([how a run's moments are worked out](../docs/guides/README.md#how-a-runs-moments-are-worked-out)).
- **Truth and model state.** What a part works out describes what is:
  the air, sizes, ages, stages, harvest. The values a model invents for
  itself, such as a plant's vigour, are its own, and nothing else reads
  them.
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
| Describe a greenhouse | `greenhouse_sim.scenarios`, `greenhouse_sim.world`, `greenhouse_sim.world.envelope` |
| Score readings against the truth | `greenhouse_sim.ground_truth`, `greenhouse_sim.evaluation.observation_accuracy` |
| Draw a simulation | `greenhouse_sim.world.geometry`, `greenhouse_sim.scene.snapshot` |
| Steer a run as a policy | `greenhouse_sim.experiment` |

A run itself is reached through the local API (`python -m greenhouse_sim.api`):
its consumer interface delivers a run's records, and its gateway takes a
plan of actions for it. Everything else is internal and may move.
`tests/test_public_imports.py` lists every public name.

A control policy reaches a run through a port of its own (decision 0061):
what an observation process makes, what it may know of the greenhouse,
and its own plans, as its own principal, and nothing of the simulated
world's truth.
- **In the process,** an experiment steps a run for it, decision by
  decision (`greenhouse_sim.experiment.run_episode`), as
  `examples/03_close_the_loop.py` does.
- **In a process of its own,** given only a port's address and its token,
  it reads the port's server (`python -m greenhouse_sim.api.policy_server`)
  through the protocol's client
  (`greenhouse_protocol.contracts.policy_client`).

The engine's day (`SimulationEngine`), its world, its model contracts, its
simple models and its checkpoints were removed in 0.5.0 (decision 0059):
the run is the one simulator, each of its parts a ladder of models from the
simplest to the richest, and a new model joins it as a rung of one of them
([recipes for contributors](../docs/guides/README.md)).

## The viewer

The browser viewer shows what the simulator is doing, in 3D: a scenario's
run at a moment of it, or followed as it is played back, growing as its
clock moves on, with controls to play, pause and start it over.
`uv run demo`, from a clone, starts both and opens the reference greenhouse
([docs/demo.md](../docs/demo.md)), once `uv run setup` has installed the
viewer's packages (Node 24). Or start the local API, then the viewer:

```bash
uv run api      # http://127.0.0.1:8765/api
uv run viewer   # http://localhost:5173, in a second terminal
```

See [web/README.md](web/README.md) for the viewer's own checks.

## CFD, optionally

The simulator writes a scenario's air as an OpenFOAM case, and runs OpenFOAM
out of process if it is installed or Docker is running
([decision 0027](../docs/decisions/0027-cfd-runs-out-of-process-on-the-fields-grid.md)).
A solved result is kept in `greenhouse_sim/cfd/results/`, keyed by what was
solved, and offered as the scenario's `cfd` field while it is current. So
nothing else needs OpenFOAM or Docker.

```bash
python -m greenhouse_sim.cfd tomato_compartment cases/tomato_compartment --open door_front:1 --mesh
python -m greenhouse_sim.cfd tomato_compartment cases/tomato_compartment --solve  # keeps the result
pytest -m cfd   # the tests that run OpenFOAM; skipped without it
```

The CFD workflow in CI runs them on changes that can affect them, and keeps
what it solved as its `cfd-results` artifact: a kept result that went stale
can be taken from there.

## Benchmark

`python -m greenhouse_sim.benchmark` runs the reference greenhouse's season
from its start, in about five minutes on a laptop, and reports what it cost:
the house's air, the plants' light and the plants' days per simulated day;
an hour of the air cell by cell; the scene a camera's frame is drawn from,
with the crop at its fullest; what there is to draw then; the process's peak
memory; and which of them is the next bottleneck. Run from a checkout, it
compares the report with the one kept in `benchmarks/simulator.json`, with
the machine it ran on, or with the one `--report` names; `--record` keeps
the new one, and `--days 10` measures the season's first days alone. It is a record, not a gate. Every answer of the local API
says how long the simulator took to give it, in a `Server-Timing` header,
which the viewer's HUD shows for the latest request.

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
