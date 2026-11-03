# Dependency updates

How Dependabot is set up here (decision 0033, recorded 2026-10-13 and configured
the same day), and what still moves by hand. Part of
[engineering](engineering.md).

`.github/dependabot.yml` checks every weekday (Dependabot's `daily`), and
opens pull requests for the updates found, in:

- **npm:** the viewer's `greenhouse_sim/web/package.json` and its lockfile;
- **uv:** the development tools pinned in the root `pyproject.toml`'s
  `dev` group, and uv and `poetry-core` in its `toolchain` group, all locked
  in `uv.lock` (decision 0039), and nothing else of the workspace:
  its uv support still mistakes a workspace's own packages for PyPI's
  ([dependabot-core#14004](https://github.com/dependabot/dependabot-core/issues/14004))
  and can rewrite a member's requirements in a grouped update
  ([#15786](https://github.com/dependabot/dependabot-core/issues/15786));
- **pip:** the three packages' `pyproject.toml`, whose ranges move only
  when a release falls outside them; `uv lock` on the pull request's branch
  then brings `uv.lock` along, which CI's `uv sync --locked` asks for;
- **GitHub Actions:** the actions `.github/workflows/` uses;
- **pre-commit:** the hooks' `rev`s in `.pre-commit-config.yaml`.

A pull request overtaken by a newer release is closed by Dependabot for the
newer one. One that needs more than its version change is completed by
hand on its branch.

**What merges by itself:** a minor or patch update that changes no code
and passes every check, that is a pull request

- whose commits are all Dependabot's, the last push its own too,
  changing only dependency manifests and lockfiles, and none of whose
  dependencies' maintainers changed;
- whose update Dependabot's metadata calls minor or patch; below 1.0, patch
  only, since there a minor release may break, as `three`'s do (0.186 to
  0.187);
- whose required checks have all passed: CI's jobs, the visual checks and
  the risk gate.

A workflow on Dependabot's pull requests (`dependabot-auto-merge.yml`)
reads the update (`dependabot/fetch-metadata`), decides with
`scripts/dependabot_auto_merge.py` and, when the first two hold, turns on
GitHub's auto-merge, which merges once the third holds too; a later push
that breaks the first two turns it off again. Everything else waits for a
review: majors, minor updates below 1.0, and whatever was completed by
hand. As the risk gate stands, only npm's updates can merge by themselves:
it holds every Actions and `pyproject.toml` change for a review, which on
Dependabot's pull requests is an approval of the latest commit (decision
0034). Dependabot proposes a release only once it is three days old (its
`cooldown`), so that one found compromised is usually withdrawn first.

The repository's settings changed for it. Auto-merge is allowed. The
`main protection` ruleset lists CI's checks as required: auto-merge waits
on required checks only, and with none it would merge at once. Its
"Restrict updates", which let only admins update `main`, gave way to those
checks, since a merge turned on with the workflow's token is not an
admin's. Admins bypass the ruleset as before.

What the repository already ties together:

- **Vitest and `@vitest/coverage-v8`** run only at the same version: one
  group. So do `three` and `@types/three`.
- **Playwright:** `@playwright/test` and the visual checks' container image
  in `ci.yml`, `mcr.microsoft.com/playwright:v<version>-noble-amd64`, are
  the same version. Dependabot does not move the image: `@playwright/test`
  comes in a pull request of its own, which fails the visual checks, and a
  root test that names the image to move to (`tests/test_pins.py`), until
  the image is moved by hand; screenshots that then differ get new
  baselines from CI, as any do.
- **ruff** is pinned twice, in the root `pyproject.toml` and as the
  pre-commit hook's `rev`. The two come in two pull requests, ruff's alone
  in its ecosystem's, and are merged together.
- **uv** comes in a pull request of its own. Every CI job installs the uv
  `uv.lock` records (setup-uv's `version-file`), and that uv builds the root
  project itself while its version is inside the root's `uv_build` range: a
  release outside it fails a root test until the range is widened by hand.
- **`poetry-core`**, which builds the three packages, comes in a pull
  request of its own too. The workspace's build pin, the root
  `pyproject.toml`'s `build-constraint-dependencies`, follows it by hand:
  a root test fails until it does, naming the version to move to.
- **`@types/node`** stays on the major of the viewer's Node, 24.
- **The packages' runtime dependencies** are ranges, what a user may install
  them with (`pydantic>=2.9`, `numpy>=2.0`, `openpyxl>=3.1.5,<4.0.0`), not
  pins. A range changes only when a release falls outside it
  (`increase-if-necessary`, which pip supports), as a major, reviewed; a
  lower bound is not raised for its own sake. Their bound on each other,
  `greenhouse-protocol`, is left to their own releases.

The checks as they stand:

- **Sign-off:** Dependabot's commits carry `Signed-off-by: dependabot[bot]`,
  so `commits are signed off` passes them as it is; a commit pushed onto a
  bot's branch by hand is signed off as any other.
- **The risk gate:** a bot's description has no checkbox, so for an update
  the gate holds, a maintainer's approval of its latest commit is the
  acknowledgement (decision 0034). The lockfile is not counted against the
  gate's thresholds.
- **CI time:** each update runs a pull request's checks. Minor and patch updates
  are grouped by ecosystem, which keeps the day's runs few; majors come one pull
  request each.

**Done when** each ecosystem's first pull request has passed its checks and
been merged, a minor npm update has merged by itself and a major one has
waited, and the couplings above are in the configuration's groups or
written beside it.
