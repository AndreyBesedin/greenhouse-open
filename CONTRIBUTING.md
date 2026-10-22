# Contributing to greenhouse-open

Thank you for considering a contribution. Issues and pull requests are
welcome, from a typo fix to a new dataset adapter.

## Sign your commits (DCO)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/)
instead of a contributor licence agreement. By adding a `Signed-off-by`
line to each commit, you certify that you wrote the change or otherwise
have the right to submit it under the project's licence (Apache-2.0):

```bash
git commit -s -m "fix(sim): describe the change"
```

That adds `Signed-off-by: Your Name <you@example.com>`, using your Git
name and email. Pull requests with unsigned commits cannot be merged.

## Write Conventional Commits

Commit messages and pull request titles follow
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
`<type>(<scope>): <summary>`, for example
`test(sim): capture the simulator baseline before refactoring`. See
[docs/engineering.md](docs/engineering.md#commit-messages) for the types,
scopes and how to mark a breaking change.

A commit message or pull request says what changed, why, what it achieved
and how it was checked, for any reader of the project, not for whoever
asked for it: no one contributor's plans, events, deadlines, commercial needs or requests
([what a public record says](docs/engineering.md#what-a-public-record-says),
decision 0044).

## Set up development checks

With [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node 24
(see `greenhouse_sim/web/.nvmrc`), once, from the clone:

```bash
uv run setup
```

`uv run` installs Python 3.14 when the machine has none, the packages and
the development tools; `setup` adds the viewer's packages, Playwright's
Chromium and the repository's git hooks. The pre-commit hook handles fast
file hygiene, Ruff fixes and formatting, the named-numbers check, and Biome
for viewer files, which needs the viewer's packages for any commit that
touches `greenhouse_sim/web/`, a README fix included. The pre-push hook runs
the repository's fast Python check suite.

You can run the same checks manually:

```bash
uv run pre-commit run --all-files
uv run check --fast
```

Run the full suite before requesting review for a non-trivial change:

```bash
uv run check
```

`uv run help` lists the other commands.

## Before opening a pull request

- Keep the change focused: one concern per pull request.
- Prefer small working commits that keep the branch runnable.
- Separate mechanical moves/renames from behavior changes where practical.
- Add or update tests. A new adapter comes with small synthetic fixtures;
  never commit dataset content.
- Describe an observable/testable result for simulator changes.
- If the change delivers a [roadmap](docs/roadmap/README.md) step, update the
  step's status in its project document. If it sets a lasting technical
  direction, add a [decision record](docs/decisions/README.md).
- Resolve or explicitly acknowledge automated review feedback.
- If the pull request risk gate asks for it, review the complete diff yourself
  and check the manual-review acknowledgement in the pull request body. The
  gate runs again when the description is saved. On a Dependabot pull
  request, a maintainer's approval of its latest commit acknowledges it.
- A package may import only the standard library, itself and the
  dependencies it declares; `tests/test_dependencies.py` enforces this.

The repository deliberately does not require a human approval while it has a
single active developer. See [docs/engineering.md](docs/engineering.md) for
the current risk-based review policy and architecture conventions.

## What belongs here

The shared record format and its contracts, the simulator, dataset adapters,
and evaluation tooling that works from public data. Changes to the protocol
are the most consequential: they affect every producer and consumer, so
open an issue to discuss them first.
