# 0069: `uv run setup` installs Node when the machine's is missing or too old

**Status:** Accepted
**Date:** 2026-11-06

## Context

Decision 0039 made `uv run` provide Python 3.14 and every Python package,
and left Node 24 (decision 0008) a prerequisite. On a machine whose Node was
22, `uv run setup` stopped at its first step, saying Node 24 was needed and
how to get it, and the clone could neither install the viewer's packages nor
commit to `greenhouse_sim/web/`, whose Biome hook runs on Node. The machine's
Node is often another project's: an `nvm` default or a distribution's
package, older than the viewer's.

The options weighed:

- **Keep Node a prerequisite** and say better how to get it: each
  contributor still installs and switches Node by hand.
- **Always install Node into the workspace,** whatever the machine has:
  every clone and worktree downloads Node, and one with the right Node on
  its path gains nothing.
- **Install it when the machine's is missing or too old,** into the
  workspace's environment, where `uv run` already finds the workspace's
  Python and tools.

nodeenv installs a released Node, prebuilt for the machine, into a Python
virtual environment's `bin` (`Scripts` on Windows). pre-commit already
depends on it.

## Decision

- **`uv run setup` uses the Node on the workspace's path when it is the
  version `greenhouse_sim/web/.nvmrc` names, or newer.** Otherwise it
  installs the latest release of that version into the workspace's `.venv`,
  with nodeenv (pinned in the `dev` group), then goes on with that Node's
  npm. It finds that release in Node's list,
  `https://nodejs.org/dist/index.json`, itself, and gives nodeenv the exact
  version: nodeenv 1.11 cannot read the list's pre-releases when it looks
  for a release of a version itself.
- **The workspace's Node is for the workspace's commands:** `uv run` puts
  `.venv`'s `bin` first on the path, so every `uv run` command, and
  `uv run npm …`, uses it. The machine's own Node, outside the workspace,
  does not change.
- **The Biome hook runs through `uv run`,** so that a commit finds that Node
  when the machine has none, as the pre-push hook already runs through it.
- CI does not change: it installs the Node `.nvmrc` names with
  `actions/setup-node`, which `uv run setup` then finds on the path.

This supersedes decision 0039's "Node 24 stays a prerequisite"; the rest of
0039 stands.

## Consequences

- A clone needs uv and nothing else before `uv run setup`, apart from
  Chromium's system libraries on Linux, which need `sudo`.
- `.venv` holds Node, about 140 MB unpacked. A worktree whose machine lacks
  the right Node downloads its own, as it installs its own Python packages.
  Removing `.venv`, or a `uv sync` that recreates it for another Python,
  removes that Node; `uv run setup` installs it again.
- `npm` run from a shell outside `uv run`, without `.venv` activated, is the
  machine's: the viewer's README says to put `uv run` before it.
- When `.nvmrc` moves to a new version, `uv run setup` installs it over the
  workspace's Node, as it would on a machine with only the older one.
- Worth revisiting if nodeenv reads pre-releases again, which would let
  setup pass `--node=<version>` and drop its own reading of Node's list, or
  if uv comes to provide Node itself.
