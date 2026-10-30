# Crop integration without a global day step

**Status:** Proposed implementation plan. See [decision 0064](../decisions/0064-simulation-time-and-crop-integration.md).

## Why now

The present climate solvers already own their numerical stepping, but crop models do not. `biology/crop_contract.py` requires `live_day`; `core/crop_days.py` stores integer-day states and runs `Growth.lived/next_day`; `services/crop.py` passes `climate.house.mean_between(day * DAY_S, (day + 1) * DAY_S)` and shows the state after `days_ended(time_s)`; `solar/plants.py` offers daily PAR integrals; `services/gateway.py` requires crop actions at `moment % DAY_S == 0`. These are model-specific assumptions leaked into general runtime contracts.

The site already exposes a local timezone and midnight in `world/site.py`; this is sufficient as the foundation for civil-time calendar scheduling, but do not confuse a local calendar day with a fixed 86,400-second duration.

## Implementation sequence

### Phase 0: Baseline and inventory

- Record golden runs, crop states, snapshots, replay digests, action outcomes and checkpoint behavior for existing organ and simple crops. Identify all day-coupled code paths (including crop logs, checkpoint schemas, timeline, replay, UI, benchmarks, and `core/engine.py`).
- Document current public API/manifest compatibility and decide where a version bump is necessary. No behavior change in this phase.

### Phase 1: Temporal crop model contract

- Introduce a model-neutral crop state advancement contract `advance(state, from_time, to_time, drivers, actions) -> state/events` (illustrative, not a frozen signature). Support explicit model identity/version and deterministic seeds.
- Define model-owned integration configuration: fixed/adaptive strategy, tolerances, max step where applicable, requested driver resolution/aggregation, and checkpoint requirements. Do not make the numerical scheme a UI-controlled global setting.
- Provide a legacy daily adapter around `CropRung.live_day` and `CropDays` so existing daily biology retains its equations and expected outcomes. Do not make `CropDays` the contract new models implement.
- Specify boundary and causality ordering: environment interval `[t0,t1)`, scheduled actions at `t1`, then observation, or another explicit consistent ordering; verify no future-driver leakage.

### Phase 2: Environment and aggregation

- Expose timestamped environmental drivers (temperature, CO2, humidity, PAR, etc.) through an interval interface; support model-requested aggregation (time-weighted mean, integral, extrema, daytime/nighttime windows as needed).
- Move daily air means and PAR integrals into the legacy model adapter's requested driver profile. Keep `daily_light_integral` as a convenience, not a mandatory generic crop input.
- Specify missing data, interpolation, sampling, unit conversions, spatial mapping, and caching. Test non-24h and partial windows.

### Phase 3: Arbitrary-time crop state and actions

- Make crop state queryable at an arbitrary valid simulation instant. Remove the generic `days_ended(time_s)` selection; retain last-completed-day behavior only for the explicitly discrete legacy adapter, documented as such.
- Remove the universal `moment % DAY_S == 0` crop-action restriction. Replace with model capability/operation constraints and scheduling policy; support actions at valid arbitrary instants and deterministic same-instant ordering.
- Provide calendar schedules in site-local time (`daily at 09:00`, weekdays, etc.) separately from elapsed-duration schedules (`every 86400 s`). Handle DST gaps and ambiguous times by a documented policy; test both.
- Preserve controller, viewer and gateway target-time APIs and their independent observation cadence.

### Phase 4: Replay, checkpoints and validation

- Store exact instant, model identity/version, model state, scheduler position, and necessary driver/integrator state in checkpoints. Migrate legacy day-indexed checkpoints deliberately, with versioned compatibility or explicit rejection.
- Add tests: consumer query-frequency independence; coarse versus fine target-time advancement; no lookahead; daily legacy parity; non-midnight crop actions; civil 09:00 versus fixed 24h across DST; checkpoint/resume at 13:37; model-specific solver reference tests.
- Ensure numerical tolerance comparisons are used only where appropriate. For deterministic fixed-step models, require exact reproducibility where feasible.

### Phase 5: Remove obsolete day-centric runtime machinery

- Only after parity and conformance, retire or isolate `CropDays`, generic `run_day/days_ended` crop stepping and day-based restrictions. Keep day-based UI reports, agronomic aggregates, daily scheduling and daily replay probes as optional derived features.
- Update P14, crop-model authoring guide, API docs, manifests, examples and decision cross-references. Preserve published model reproduction methodology.

## Out of scope

- Replacing the climate solvers' existing stability bounds or numerical methods.
- Rewriting organ/simple biological equations.
- Building a complex global event scheduler before required by coupling.
- Requiring every model to use a user-configurable timestep.
- Changing daily charts, reports or agronomic concepts simply because they mention days.

## Review questions

1. Should the new contract expose a driver history view, a callable time-series provider, or a materialized interval bundle? Choose based on memory, replay and solver needs.
2. Which crop actions genuinely require model-specific scheduling restrictions, versus legacy implementation restrictions?
3. Which existing public schemas need a version bump and migration?
4. What synchronization guarantees will future coupled climate/crop models require?
