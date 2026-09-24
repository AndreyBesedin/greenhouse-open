# greenhouse-sim

A deterministic greenhouse simulator that produces canonical observations.
Part of [greenhouse-open](../README.md). Apache-2.0.

- **A hidden world, noisy sensors.** `GreenhouseWorld` holds what is really
  true, including latent variables no sensor measures. Each step publishes
  only noisy `Observation`s of it.
- **Semantic actions.** `SimulationEngine.apply_actions` validates each
  `RequestedAction` against the world and executes the accepted ones through
  a pluggable `ActionExecutor`, returning an `Event` for each.
- **Deterministic.** The same scenario, seed and actions always produce the
  same records.
- **Ground truth for evaluation only.** `greenhouse_sim.ground_truth` reports
  the noiseless values, and `greenhouse_sim.evaluation` scores observations
  against them. Nothing on the observation path exposes them.
- **Scenarios.** `greenhouse_sim.scenarios` holds ready-made worlds; a
  `ScenarioConfig` describes size, crop, dynamics and sensor noise, and
  nothing about who manages the greenhouse.

The dynamics are deliberately simple today: air temperature, humidity, a
per-plant water reservoir, stem growth, trusses and fruit ripening. They
are reached through one module, so richer or specialised physics can
replace them without changing the engine's interface.

```python
from datetime import UTC, datetime
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY

engine = SimulationEngine(SCENARIO_REGISTRY["gh_002"])
world = engine.initialize(["gh_002_plant_001"], greenhouse_id="gh_002")
step = engine.advance(world, day=1, timestamp=datetime(2026, 3, 1, tzinfo=UTC), simulation_id="run")
print(step.observations)
```

## Dependencies

`greenhouse-protocol`, Pydantic 2 and NumPy.
