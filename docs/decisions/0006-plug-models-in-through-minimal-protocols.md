# 0006: Plug simulation models in through minimal protocols

**Status:** Accepted
**Date:** 2026-10-03

## Context

The roadmap replaces and adds models at different fidelities: an organ-level
tomato model (P03), environment fields and airflow (P04), richer sensors
(P06). Until now the engine reached the simple models directly, through
`world_builder` and the observation generator, so a second model would have
meant editing the engine. The roadmap asks for contracts only where they are
already justified, not an interface for every possible component.

## Decision

- There are three contracts, one per domain that the roadmap will extend,
  each in its domain's `contract.py`:
  - `PlantModel[StateT]`, generic over the state the model keeps for itself;
  - `EnvironmentModel`;
  - `SensorModel`.
- Contracts are `typing.Protocol`s. Implementations satisfy them by shape;
  they neither import nor inherit them. mypy checks conformance where an
  implementation is used as the protocol.
- Each contract's docstring states the rules an implementation must follow:
  identity and order, inputs left unmodified, determinism, a plant's day
  independent of the rest of the crop, state surviving JSON, and sensor output
  that passes the canonical conformance checks. `test_model_contracts.py`
  checks every listed implementation against them.
- `SimulationEngine`, `initialize_world` and `advance_world` take the models
  as keyword arguments, defaulting to the simple implementations, as the
  engine already did for its executor.
- A plant model's state type is limited to what the world can carry,
  `PlantModelState` in `world/state.py` (see decision 0005).

Deliberately not decided yet, because nothing would use it:

- capability flags that let a backend declare what it supports;
- state for environment models, which the simple model does not need;
- model parameters separate from `ScenarioConfig`.

Each comes with the first model that needs it.

## Consequences

- A new model is a class with the contract's methods, added to the lists in
  `test_model_contracts.py`. The engine does not change.
- The simple models remain the defaults, so existing callers and the
  reference baseline are unaffected.
- A second plant model widens `PlantModelState` to a union of state types,
  and probably motivates separating its parameters from `ScenarioConfig`.
