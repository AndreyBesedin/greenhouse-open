# Decision records

Short, numbered records of decisions that set a lasting technical direction
for this repository: architecture boundaries, shared contracts, runtime
dependencies, supported platforms and the development workflow. When to
write one is described in
[docs/engineering.md](../engineering.md#roadmap-and-decision-records).

A record is written in the pull request that implements the decision. Once
accepted it is not edited, apart from its status line. A decision that
changes course is a new record that supersedes the old one.

| Record | Decision | Status |
| --- | --- | --- |
| [0001](0001-keep-roadmap-and-decisions-in-the-repository.md) | Keep the roadmap and decisions in the repository | Accepted |
| [0002](0002-use-conventional-commits.md) | Use Conventional Commits | Accepted |
| [0003](0003-require-python-3-14.md) | Require Python 3.14 | Accepted |
| [0004](0004-organize-greenhouse-sim-by-domain.md) | Organize `greenhouse_sim` by simulation domain | Accepted |
| [0005](0005-keep-model-state-apart-from-the-world.md) | Keep a model's own state apart from the world | Accepted |

## Template

Name the file `NNNN-short-title.md`, using the next free number.

```markdown
# NNNN: Decision in a few words

**Status:** Accepted | Superseded by [NNNN](NNNN-title.md)
**Date:** YYYY-MM-DD

## Context

What forces the decision: the problem, the constraints, the options that
were weighed.

## Decision

What was decided, stated so that someone can check whether the code follows
it.

## Consequences

What becomes easier or harder, what has to happen next, and what would make
the decision worth revisiting.
```
