# 0047: Python lint rules, a family at a time

**Status:** Accepted
**Date:** 2026-10-22

## Context

Ruff has formatted and linted the Python since 0.1.0, with five rule
families: `E`, `F`, `I`, `UP` and `B`. The repository audit (`AUDIT.11`)
ran others over the packages and found a few hundred findings, most of them
from a handful of rules, and some of those rules against what this codebase
does on purpose: `TRY003` for the long messages it builds in `raise`, `D1`
for docstrings it writes by judgment. It asked for a family at a time, each
pull request fixing what it finds, recorded beside decision 0010, the
viewer's counterpart.

The rules are written four times: in `ruff.toml`, which lints the root's
tests, scripts and tools, and in each package's `pyproject.toml`, which
lints its own directory. They had always agreed, but nothing held them to
it.

## Decision

- **A family is turned on in a pull request that fixes what it finds.**
  Families with a handful of findings may share one pull request, a commit
  each.
- **A finding is a claim to check, not a defect by count.** Where a rule
  contradicts something the code does on purpose, the rule is switched off
  in the configuration, with the reason beside it, rather than the code
  bent to it or silenced line by line.
- **One set of rules everywhere.** The four configurations say the same,
  and `tests/test_lint_config.py` fails when they do not.

The families as they stand:

| Family | State | Where it is off, and why |
| --- | --- | --- |
| `E`, `F`, `I`, `UP`, `B` | on, since 0.1.0 | |
| `SIM` | on (#292) | `SIM300`: a range is written as a number line (`low < value < high`), and a named constant is compared with the number it should be |
| `PERF`, `ERA`, `PIE`, `C4` | on | `C408` allows `dict(name=value)`, which the tests use for a record's defaults |
| `N` | on | `N818`: an exception is named for what happened (`NotFound`, `InvalidManifest`), as the standard library's own are, and the protocol's are its users'; `do_*`, which `http.server` names its handlers' methods, is no mixed case to fix |
| `DTZ` | on | `DTZ001` in the tests: a test builds a wall-clock time on purpose, to see it refused, or as a dataset's rows give it; and the adapters' Excel epoch, wall-clock by nature, says so on its line |
| `RUF`, `ARG`, `C901`, `PLR0913` | next, a pull request each | `PLR0913` once the services take one run request (W11, done) |
| `TRY`, `D1` | not planned | the messages built in `raise`, and docstrings written by judgment, are this codebase's choice |

Other families wait for a reason: a defect one of them would have caught.

## Consequences

- A rule turned on keeps its class of mistake out for good, at the cost of
  a pull request that reads every place it finds.
- The table above is kept as families are turned on; a rule switched off
  later says why in the configuration and here.
- More findings from a family are not more defects: a family is taken for
  what its findings show, not for its count.
