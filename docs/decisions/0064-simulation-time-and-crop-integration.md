# 0064: Simulation time is continuous; crop integration owns its cadence

**Status:** Proposed
**Date:** 2026-10-30

## Context

The simulator already accepts target instants in the gateway and its climate models advance by their own methods: spatial transport selects stability-bounded substeps (at most 10 s), while well-mixed house air integrates over bounded stretches. Yet crop execution is tied to a run-wide day: `CropRung.live_day`, `Growth.lived/next_day`, `CropDays`, daily climate means, daily light integrals, and crop-action validation at multiples of `DAY_S`. A viewer can ask for arbitrary moments but receives the crop at the last completed day. This prevents continuous and subdaily scientific crop models and incorrectly makes a calendar reporting unit into an execution primitive.

The site already has an IANA time zone and local midnight (`world/site.py`). Solar calculations depend on physical instants and site location, not on the crop's daily stepping.

## Decision

1. **Authoritative time:** the run advances over instants or elapsed durations, not integer days. A calendar day is a derived, site-local interval used for reporting, display, agronomic aggregation, and civil-time schedules. It is never the base integration unit. Keep explicit units and timezone-aware conversions.
2. **Model-owned numerical integration:** each crop model declares its supported temporal driver requirements and advances from `t0` to `t1` using its scientifically appropriate integration method, fixed step or adaptive solver. The runtime must not silently impose a global crop timestep or assume that a daily model's step applies to all crops. Reference-model solver choices and tolerances remain reproducible and versioned.
3. **Driver windows are explicit:** environment providers expose time-indexed drivers and aggregation over a requested interval with a specified method (e.g. time-weighted mean, integral, day/night split, extrema). The model requests what it needs. Do not hardcode 24-hour means or daily PAR integrals into the generic crop contract. A legacy daily adapter may request them as its own model-specific policy.
4. **Calendar schedules are distinct from durations:** `every day at 09:00` means 09:00 in the site's configured civil timezone, accounting for daylight-saving changes; `every 24 hours` means fixed elapsed seconds. Neither is encoded as `moment % DAY_S == 0`. Crop actions occur at supported instants with explicit applicability constraints; no universal midnight-only rule. Sun position and sunrise/sunset remain astronomical calculations, not action scheduler primitives.
5. **Observations are independent:** consumers choose when to request snapshots and observations; they do not change numerical integration or the resulting physical trajectory. A crop snapshot at time `t` describes the state at `t`, not silently the last midnight, unless the specific legacy model's discrete state semantics are explicitly indicated.
6. **Checkpoints and replay:** state includes its exact simulation instant and model identity/version, numerical/driver history needed to resume deterministically, and any scheduled event cursor. Daily digests may remain a reporting/test convenience, not a checkpoint constraint. Preserve deterministic replay and stable action ordering for equal timestamps.
7. **Compatibility:** preserve existing organ/simple daily models through a clearly labeled daily adapter; do not rewrite their scientific behavior as part of this migration. Existing manifest defaults and published replay expectations remain stable until an explicit versioned migration. No separate global day engine.

## Consequences and boundaries

- The crop runtime becomes temporal-model-neutral. Different crop models may use daily, hourly, continuous or adaptive integration; the model contract is the extension point.
- Environment history must be available without requiring all data to be materialized in memory; interval aggregation needs defined interpolation, missing-data, units and boundary semantics.
- A model's allowed integration step is not the same as consumer polling or controller decision frequency.
- `0024` remains historical context for the legacy organ model, but its **universal** daily interface is superseded by this decision once accepted.
- This decision does not require implementing a general-purpose multi-rate scheduler immediately. Start with target-time advancement and model-owned stepping; add event-driven coordination when actual coupling requires it.
- For tightly coupled crop/climate feedback, the runtime must eventually define synchronization and causality boundaries, rather than let each subsystem independently advance past an intervention.

## Acceptance criteria

- Same deterministic crop trajectory at a fixed target instant regardless of UI snapshot frequency or query order.
- A subdaily model can update and be observed between midnights without modifying generic run or viewer code.
- A daily reference model reproduces its pre-migration baseline under its legacy adapter.
- Aggregation windows/methods are explicit and tested, including partial intervals.
- A civil-time daily 09:00 schedule differs correctly from an elapsed 24-hour schedule across DST.
- A crop action can be planned at a non-midnight supported instant, and its outcome is replayable.
- Checkpoint/resume at a non-midnight instant agrees with uninterrupted execution.
