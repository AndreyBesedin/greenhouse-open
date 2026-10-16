# 0037: The simulator's subpackages tangle no further

**Status:** Accepted
**Date:** 2026-10-16

## Context

`greenhouse_sim` is organized by domain (decision 0004), and two of its
boundaries are checked: an API reaches its package only through its
services (decision 0021), and only the evaluation reads ground truth
(`tests/test_dependencies.py`). Nothing checks the subpackages between.
Ten pairs of them import each other
([repository audit](../audits/2026-10-13-repository-audit.md), `AUDIT.10`):
`core` holds both the engine's day and the run's crop, so it imports the
models it sits above, and `solar` and `weather`, or `cfd` and `services`,
reach into each other.

None of this is a broken import, but each new tangle makes a part harder to
move, test or replace on its own, which is what decision 0035 asks of every
part of the run. Drawing the full table of layers now, with a test holding
it, was weighed and left for later: 0035's move decides where `core`'s two
halves go, and a table drawn before it would be drawn again.

## Decision

- **No new pair of subpackages imports each other.**
  `greenhouse_sim/tests/test_subpackage_imports.py` lists the ten pairs
  that do today, and fails on another. A pair that is untangled leaves the
  list, so the list only shrinks. A top-level module counts as a
  subpackage of its own.
- **Every import counts,** inside a function or for types only. The
  package imports itself by absolute names only, which the test checks, so
  it reads them all.
- **`domain`, the shared vocabulary (decision 0025), imports nothing else
  of the package.**
- The table of layers, with its named exceptions (imports for types only,
  the command lines' entry points), is drawn after 0035's move and
  replaces the list.

## Consequences

- A change that would tangle two subpackages moves the code it needs
  instead, or adds the pair to the list in the open, where its review sees
  it.
- Longer cycles, through three subpackages or more, are not checked yet;
  the table of layers will check them.
- Worth revisiting when 0035's move has given the run its parts: then the
  table replaces this list.
