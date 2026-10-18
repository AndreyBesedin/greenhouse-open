# 0038: Hook updates merge like development dependencies; review changes with a second maintainer

**Status:** Accepted
**Date:** 2026-10-16

## Context

The [repository audit](../audits/2026-10-13-repository-audit.md) left two
questions about the process (`AUDIT.13`, `AUDIT.21`).

**Hook updates.** A minor or patch update that changes no code merges by
itself (decision 0033). `scripts/dependabot_auto_merge.py` counts
`.pre-commit-config.yaml` and `requirements-dev.txt` as manifests, so it
turns auto-merge on for a pre-commit hook's update and a Python
development tool's, while an action's waits for review because it changes
code that CI runs. The risk gate, a required check, still holds both
files for review, which on Dependabot's pull requests is an approval of
the latest commit (decision 0034): as decision 0033 says, only the
viewer's npm updates merge by themselves. A hook is code, run on the
developer's machine at every commit, but so are the npm packages and the
Python development tools. Every update is proposed three days after its
release (`cooldown`), and merges only once the required checks pass.

**Review.** The repository has one maintainer, so `main` requires CI's
checks and no approval, and the risk gate's tick is the maintainer's own
acknowledgement (`docs/engineering.md`, "Solo-developer review policy";
decision 0034). The audit proposes what changes when a second contributor
arrives, and asks what counts as one: anyone whose pull request is
merged, or a second person who can merge.

## Decision

- **A pre-commit hook's minor or patch update merges by itself,** as an
  npm development dependency's does, and so does a Python development
  tool's. An action's update still waits for review.
- **The solo-developer review policy holds while one person can merge.**
  A pull request from anyone else does not change it: only the maintainer
  can merge it, and reviews its whole diff before doing so.
- **When a second person gets write access,** one change brings in:
  - `main` requiring one approval and resolved review threads;
  - `CODEOWNERS`, naming owners by subpackage;
  - labels for the kinds of contribution (`model`, `device`, `scenario`,
    `viewer`, `good first issue`);
  - a release at the end of every roadmap project.
- The `main` ruleset's other settings stay as they are, while the
  maintainer works on the process.

## Consequences

- The risk gate lets Dependabot's updates of `.pre-commit-config.yaml`
  and `requirements-dev.txt` through without an approval, in a pull
  request of its own, since the gate holds its own script;
  `scripts/dependabot_auto_merge.py` still decides which of them merge by
  themselves. Until then they wait for an approval, as they do now.
- `docs/engineering.md` points here from its review policy, which says
  what holds now: an outside pull request is reviewed whole, and resolved
  threads are asked for but not required. The change that brings in the
  second maintainer rewrites that policy, and revisits decision 0034's
  tick, which another maintainer's approval could then replace.
- Worth revisiting if a hook's update breaks a local commit while CI
  passes, or if a compromised release reaches a hook despite the cooldown:
  hooks would then wait for review, as actions do.
