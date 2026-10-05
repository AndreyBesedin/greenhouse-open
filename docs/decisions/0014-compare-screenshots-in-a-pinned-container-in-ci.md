# 0014: Compare the renderer's screenshots in a pinned container in CI

**Status:** Accepted
**Date:** 2026-10-05

## Context

P00.7 adds screenshot regression tests for the renderer. What a browser
draws with WebGL depends on the graphics stack and the fonts: the viewer is
developed on macOS, where Chromium draws through the GPU, and checked in
CI on Linux, where it draws in software. The same page differs by many
pixels between the two, and `ubuntu-latest` itself changes over time.

The options were a baseline per platform (each kept up to date by hand,
and never compared on the platform that has none), a tolerance loose enough
to absorb platform differences (which would also let real changes through),
or one pinned environment that draws every baseline and every comparison.
Docker is installed on the development machine but not always running, so
CI is the environment that is always there.

## Decision

- The renderer's screenshots are drawn and compared only in CI's "visual
  checks" job, inside `mcr.microsoft.com/playwright:v1.63.0-noble-amd64`.
  The image's version moves with `@playwright/test`; it is the amd64 image,
  so that a local Docker run on Apple silicon draws as CI does.
- The canonical page is `/qa/renderer?seed=42`: a QA scene built in the
  viewer from the seed, independent of the simulator, from the default
  camera, with a plant selected, every overlay drawn and the plants coloured
  by height. It changes when the renderer changes, not when a model does.
- A pixel differs when its colour moves by more than 0.2 on Playwright's
  scale, and a screenshot fails when more than 100 pixels differ. Moving one
  stem by its own width changes about 200.
- A comparison never overwrites a baseline. A missing one is drawn and the
  test fails. When a renderer change is intended, or the first baseline is
  wanted, the failed job's `visual-results` artifact holds what was drawn;
  it is reviewed and committed as the baseline, where the pull request
  shows the image difference.
- Elsewhere the comparisons are skipped. A functional test of the QA page
  runs with the other browser tests, on every platform.

## Consequences

- A screenshot fails only for a change in what the renderer draws, not for
  a change of machine.
- Updating a baseline takes a CI run: push, download the artifact, review,
  commit.
- Upgrading Playwright means upgrading the image too; Playwright reports a
  mismatch between them.
- Running the comparisons locally in the same image, with Docker, can be
  added when it is wanted.
