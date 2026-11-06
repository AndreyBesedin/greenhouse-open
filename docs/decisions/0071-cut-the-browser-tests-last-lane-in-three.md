# 0071: Cut the browser tests' last lane in three

**Status:** Accepted
**Date:** 2026-11-06

## Context

Decision 0032 cut the browser tests into four lanes on CI, so that no lane
of stages that run alone took longer than the `chromium` lane. Its last
lane, `crop`, then took 2.4 minutes. A stage added after `crop` joins
that lane, with no change to CI, and from 3 to 6 November five did: the
replay, the worker's runs, the README's demo, the plan's QA (P13.10) and
P14.7's QA. On the last thirteen runs of `browser tests (crop)` its tests
took 9 to 17 minutes, the job 10 to 18, while `chromium` took 3 to 6.

CI's runners are of two speeds, and the same stages took 9 to 10 minutes on
the faster and 14 to 17 on the slower. Their minutes on the slower, from
the simulator's request log (the `github` reporter prints no test's
duration):

| Stage | Minutes |
| --- | --- |
| `crop` | 1.9 |
| `reference-schedule` | 0.6 |
| `replay` | 2.5 |
| `worker-runs` | 3.0 |
| `plan-qa` | 1.6 |
| `models-qa` | 2.9 |
| `p09-final-qa` | 3.4 |
| `readme-demo` | 1.1 |

They run alone because each works the simulator hard (`playwright.config.ts`
says why each is in `ONE_BY_ONE`), so they cannot share a machine; they can
run on machines of their own, as 0032's lanes do.

## Decision

- **The stages from `crop` on are cut into three lanes:** `crop` to
  `replay`; `worker-runs` to `plan-qa`; `models-qa` to the last stage. With
  0032's first three, CI runs six lanes. The stages keep their order.
- **A lane of stages that run alone is cut so that it takes no more than
  about ten minutes, its setup included, on CI's slower runners.** This
  replaces 0032's rule that no such lane take longer than the `chromium`
  lane.
- Everything else in 0032 stands: a lane's start in `LANE_STARTS`, its name
  in the matrix of `.github/workflows/ci.yml`, which the configuration holds
  in step, and every stage, one after another, on one simulator locally.

## Consequences

- On the slower runners, from the table above, the three lanes' tests take
  5.0, 4.6 and 7.4 minutes, and on the faster about 2.6, 3.6 and 3.8, where
  the one lane took 17.0 and 10.0. The last, the longest, holds the two
  walks through the reference greenhouse (`p09-final-qa`, `readme-demo`),
  which run last of all as before.
- CI runs two more jobs for each pull request, each repeating the setup of
  about a minute. The repository's ruleset requires each lane by its name,
  so `browser tests (worker-runs)` and `browser tests (models-qa)` join its
  required checks.
- A stage added at the end of the chain still joins the last lane, now
  `models-qa`. Worth cutting again when a lane passes ten minutes on the
  slower runners; the `chromium` lane can be split with `--shard` (0032).
