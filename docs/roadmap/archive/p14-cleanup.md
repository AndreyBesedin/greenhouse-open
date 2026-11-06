# P14 clean-up

**Status:** closed with [P14](p14-models-by-manifest.md) on 2026-11-06: nothing open.

The reviews of P14's pull requests find things best done once its steps
are merged, in one pass. Each review adds what it finds here, under its
pull request. The clean-up itself is one pull request at the end of P14,
which ticks each item off or says why it was dropped.

## To do

### From #432, P14.10: Reduced-State TOMGRO registered by area

- [x] **The light above a crop's scopes, worked out once a house.** Each
  run's crop grown by area built its own `solar.scopes.ScopeLight`, though
  its hourly PAR depends on the scenario, its layout and its weather, and
  on none of the run's air. It is now kept beside the plants' light in the
  sunlight store (`services.sunlight.scope_light`), keyed as it is, and a
  day's hours are worked out once, whichever run asks first
  (`test_run_tomgro.py`, `test_scope_light.py`). No number changes, so no
  run's id or digest does.
