# P14 clean-up

**Status:** open. Part of [P14](p14-models-by-manifest.md).

The reviews of P14's pull requests find things best done once its steps
are merged, in one pass. Each review adds what it finds here, under its
pull request. The clean-up itself is one pull request at the end of P14,
which ticks each item off or says why it was dropped.

## To do

### From #432, P14.10: Reduced-State TOMGRO registered by area

- [ ] **The light above a crop's scopes, worked out once a house.**
  - **What:** each run's crop grown by area builds its own
    `solar.scopes.ScopeLight` (`services.crop._area_crop`). Its hourly PAR
    above each scope depends on the scenario, its layout and its weather,
    and on none of the run's air. Yet it is worked out again for every
    kept crop of one house once their air differs, as two runs with other
    levels or plans do: `carry_on_from` shares only the days both lived
    alike.
  - **Where to:** beside the plants' light in the sunlight store
    (`services.sunlight`), keyed as it is, by scenario, layout and weather.
  - **Why later:** no packaged scenario grows a crop by area yet, so no
    run pays for it; the cost shows once one does, and several of its runs
    are kept.
