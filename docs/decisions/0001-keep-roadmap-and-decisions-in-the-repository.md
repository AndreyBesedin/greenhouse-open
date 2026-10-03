# 0001: Keep the roadmap and decisions in the repository

**Status:** Accepted
**Date:** 2026-10-03

## Context

The simulator is entering a long, staged restructuring and expansion. Its
work is planned in private notes alongside other, unrelated material, and
commits and pull requests had started to cite step identifiers from those
notes. A reader of this open repository could see the identifiers but not
what they referred to, or why the work was shaped the way it was.

## Decision

The repository carries its own account of where it is going and why:

- each roadmap project has a public document in [`docs/roadmap/`](../roadmap/README.md),
  adapted from the private planning notes in the first pull request that
  implements it, and updated by the pull requests that deliver its steps;
- lasting technical decisions are recorded in `docs/decisions/` in the pull
  request that implements them;
- commits, pull requests and code comments cite only what these documents
  define;
- public documents describe this open project only, and leave out product
  plans, business strategy, customer information and private systems.

## Consequences

- Anyone can follow the reasoning behind a change from the repository alone.
- Planning stays private and free-form. The cost is adapting a project's plan
  into a public document when work on it starts, and keeping that document
  current as steps land.
- When the implementation departs from the plan, the public document records
  what was actually done, so it stays an accurate account.
