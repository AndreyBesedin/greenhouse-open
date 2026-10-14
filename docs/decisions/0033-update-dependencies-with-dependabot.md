# 0033: Update dependencies with Dependabot, minor and patch updates merging by themselves

**Status:** Accepted; its review tick added to a Dependabot pull request's description by hand superseded by an approval, [0034](0034-approve-dependabots-pull-requests-to-acknowledge-them.md)
**Date:** 2026-10-13

## Context

No dependency was updated by a bot. The viewer's npm packages, the
development tools pinned in `requirements-dev.txt`, the packages' runtime
ranges, the actions the workflows use and the pre-commit hooks moved only
when someone moved them. The roadmap put Dependabot first after P09: checked
every day, an update that changes no code and passes every check merging by
itself, the rest waiting for a review.

The ruleset of `main` required a pull request for every change, let only
admins update `main`, and required no checks. GitHub's auto-merge waits on
required checks only: with none, it merges at once. And a merge turned on
by a workflow's token is not an admin's, which the restriction of updates
refuses.

## Decision

- **Dependabot checks every weekday** (`.github/dependabot.yml`; its
  `daily` runs Monday to Friday): the viewer's npm packages,
  `requirements-dev.txt`, the three packages' `pyproject.toml`, the actions
  in `.github/workflows/` and the pre-commit hooks. It opens a pull request
  for each update, or group of updates, and proposes a release only once it
  is three days old (`cooldown`). Its commit messages are Conventional
  Commits (decision 0002): `build(deps)` and `build(deps-dev)` for packages,
  `ci(deps)` for actions and hooks.
- **What moves together is grouped:** Vitest with `@vitest/*`; `three` with
  `@types/three`; minor and patch updates of each ecosystem otherwise; each
  major alone. `@playwright/test` comes alone, since the visual checks'
  container image has to move with it by hand, and ruff alone, since its
  pre-commit hook's `rev` comes in a pull request of its own. `@types/node`
  stays on the major of the viewer's Node (decision 0008). The packages'
  runtime ranges change only when a release falls outside them
  (`increase-if-necessary`), and their bound on each other,
  `greenhouse-protocol`, is left to their own releases.
- **A minor or patch update that changes no code merges by itself.**
  `.github/workflows/dependabot-auto-merge.yml` runs on
  `pull_request_target`, from `main`, and runs nothing of the pull
  request's own. It reads the update with `dependabot/fetch-metadata`,
  pinned by commit, and `scripts/dependabot_auto_merge.py` decides. The
  update merges by itself when Dependabot pushed last and every commit is
  its own, verified; when every dependency's update is minor or patch, and
  patch only below 1.0, where a minor release may break; when no
  dependency's maintainers changed; and when the pull request changes only
  manifests and lockfiles. The workflow then turns GitHub's auto-merge on,
  as a merge commit, and turns it off for a pull request that no longer
  qualifies.
- **The ruleset of `main` requires CI's checks** (`repository checks`,
  `viewer checks`, the four `browser tests` lanes, `visual checks`,
  `commits are signed off` and `pull request risk gate`), **and no longer
  restricts updates to admins.** Every change still comes through a pull
  request, and one merged by anyone but an admin merges only once every
  required check has passed. Admins bypass the ruleset, as before. The
  repository allows auto-merge.

## Consequences

- As the risk gate stands, only npm's updates merge by themselves. It
  holds every change to `.github/`, a `pyproject.toml`,
  `requirements-dev.txt` or `.pre-commit-config.yaml` for the manual-review
  tick. A bot's description has no checkbox, so the tick is added to it by
  hand.
- Each update runs every check, the repository checks the longest at about
  20 minutes. The day's updates share a free account's 20 jobs at once with
  everything else.
- A merge turned on with the workflow's token starts no workflow, so `main`'s
  own CI does not run on it. The pull request's checks ran on its merge with
  `main` as it was then; the ruleset does not ask for the branch to be up to
  date. Two updates of the same lockfile conflict, and Dependabot rebases
  the second, whose checks then run again.
- The ruleset names the required checks. A renamed job, or a new lane,
  takes its name into the ruleset; otherwise a pull request that is not an
  admin's waits for a check that never comes.
- Worth revisiting if an update that merged by itself breaks `main`, or if
  the development tools should merge by themselves too: the risk gate would
  then pass Dependabot's minor and patch updates of `requirements-dev.txt`.
