# 0032: Run the browser tests in lanes on CI

**Status:** Accepted
**Date:** 2026-10-13

## Context

CI's `viewer checks` job (decision 0010) ran the viewer's browser tests
after its lint, type check, unit tests and build. By P09 they took about
14 of its 15 minutes, and the job took 9 to 21 minutes from one run to the
next: the last to finish of a pull request's checks.

About 5 of those minutes are most specs, run in parallel on the runner's
two workers. The other 9 are specs that work the simulator hard (the plant
lab, the sun's light, a day's weather, P09's runs through days). Two of
them at once starve each other's waits on the one simulator they share, so
each runs alone, stage after stage, in Playwright projects that depend on
one another. Through those 9 minutes one worker is idle, and the simulator
is the bottleneck, not the runner.

The roadmap's note on test suite and CI time scheduled this after P09.

## Decision

- **The browser tests are cut into lanes that run at once on CI, each on a
  machine of its own with a simulator of its own**, so that a stage still
  never shares a simulator with another. `playwright.config.ts` lists every
  stage in order: first every spec that runs in parallel (`chromium`), then
  each stage that runs alone. A lane starts at the first stage and at each
  stage named in `LANE_STARTS`, and is named for the stage it starts at.
- **There are four lanes:** `chromium`; `renderer-smoke` to `sun`;
  `weather-day` to `checkpoints`; `crop` to the last stage. Each lane of
  stages that run alone takes about as long as the `chromium` lane, from
  the times of a run at the top of P09's stack.
- **CI runs one job per lane** (`browser tests (<lane>)`), as a matrix with
  `fail-fast: false`, so one run shows every lane's failures. The job names
  its lane in `BROWSER_TEST_LANE`, and the matrix's size in
  `BROWSER_TEST_LANES`. The configuration refuses a lane it does not cut,
  and a matrix that does not run every lane. A matrix that left a lane out
  would otherwise pass without running its tests.
- **`viewer checks` keeps the lint, type check, unit tests and build.**
- **Locally nothing changes:** `npm run e2e` runs every stage, one after
  another, on one simulator. `BROWSER_TEST_LANE=<lane> npm run e2e` runs one
  lane as CI does.

## Consequences

- A pull request's checks take about as long as the longest lane, about
  6 minutes, setup included, where `viewer checks` took 13 to 21.
- Each lane repeats the setup: the viewer's dependencies, the simulator's
  wheels, Chromium and the build, about a minute. CI runs three more jobs
  for each pull request. A free account runs 20 jobs at once, so pushing a
  long stack of pull requests at once queues more of them.
- A stage added at the end of the chain joins the last lane, with no
  change to CI. A new lane needs its start in `LANE_STARTS` and its name in
  the matrix. Missing either, the configuration refuses to run.
- Lanes share nothing: a stage no longer finds the simulator warmed by the
  stages that ran before it on CI. A stage that needed that was already
  depending on the order it ran in.
- Worth revisiting when a lane grows well past the others. The `chromium`
  lane can be split with Playwright's own `--shard`, as its specs run in
  parallel anyway. A lane of stages that run alone can be cut again.
