# 0010: Check the viewer with Biome, Vitest and a Playwright smoke test

**Status:** Accepted
**Date:** 2026-10-03

## Context

Decision 0008 left TypeScript linting, formatting and the viewer's CI to
P-1.9. The Python packages are formatted and linted by one fast tool, Ruff,
and checked by one canonical command in CI. P-1.9 asks for frontend install,
tests, build and a lightweight browser smoke test, and no expensive rendering
or CFD work in default CI. Screenshot regression tests are planned for P00.

## Decision

- **Biome** formats and lints the viewer: one tool and one dev dependency,
  as Ruff is for Python. Its configuration is `biome.json` at the repository
  root, scoped to `greenhouse_sim/web/**`, so the npm scripts, CI and the
  pre-commit hook all find the same file.
- Biome's **`noMagicNumbers`** is an error, carrying the named-numbers
  convention over from Python, with test files exempt in both languages.
- **Vitest** runs unit tests in Node.
- **Playwright**, with Chromium only, runs a smoke test against the real
  stack: it starts the simulator's local API and the production build,
  checks the page lists the scenarios from Python, and fails on any console
  or page error. P00's screenshot tests will build on the same setup.
- CI gains a **`viewer checks`** job: `npm ci`, Biome in CI mode, the type
  check, the unit tests, the build and the smoke test. The Python job is
  unchanged.
- A **pre-commit hook** runs the viewer's own Biome, from `node_modules`, on
  staged viewer files, so the hook can never use a different Biome version
  from the lockfile.

## Consequences

- Viewer changes get the same fast local feedback and the same CI gate as
  Python changes.
- Contributors who touch the viewer run `npm ci` once, so the hook can find
  Biome. Contributors who do not are unaffected.
- CI installs Chromium for the smoke test, which costs about a minute per
  run.
