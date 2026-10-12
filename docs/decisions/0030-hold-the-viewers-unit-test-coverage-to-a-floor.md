# 0030: Hold the viewer's unit-test coverage to a floor

**Status:** Accepted
**Date:** 2026-10-11

## Context

The frontend audits (FE-AUDIT.4) found the viewer's coverage neither
measured nor enforced: 129 tests at the first audit, 370 now, and no way to
tell what they leave out. The audit asked for coverage of the handwritten
code, its baseline recorded, and thresholds in CI that a change cannot
lower unnoticed, without tests written only to raise a percentage.

## Decision

- **Vitest's V8 coverage** (`@vitest/coverage-v8`, at Vitest's own version)
  measures the unit tests, as `npm run coverage`. It counts the handwritten
  code under `src`: not the contracts generated from the simulator's
  schemas (each area's `generated` folder), the tests, or `src/testing`.
- **The thresholds are the baseline, rounded down:** on 2026-10-11, 65.54%
  of statements, 57.48% of branches, 60.84% of functions and 66.40% of
  lines, held at 65, 57, 60 and 66 in `vite.config.ts`. They are raised
  when tests are added, and lowered only with the reason why.
- **CI's viewer checks run `npm run coverage`** in place of `npm test`, so a
  change that lowers coverage below a threshold fails them.
- `App`, the 3D drawing and the QA pages count as not covered: the browser
  and screenshot tests run them, and their coverage is not measured.

## Consequences

- What the unit tests leave out is visible, file by file, with
  `npm run coverage -- --coverage.reporter=text`.
- A threshold is a floor, not a target. It says nothing of whether a test
  checks what a person sees or does; reviews still do.
- The unit tests take about half a second more with coverage: 3.2 s
  against 2.7 s on a developer's machine.
