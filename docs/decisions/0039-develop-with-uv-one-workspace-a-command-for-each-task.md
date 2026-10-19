# 0039: Develop with uv: one workspace, a command for each task

**Status:** Accepted
**Date:** 2026-10-18

## Context

On a machine with nothing installed, the README's commands failed:

- `python` is not a command on macOS, whose Python is `python3`.
- `pip install` into a system's Python is refused (PEP 668), and nothing
  created a virtual environment first.
- The browser tests and the demo's recording start the simulator with
  `$PYTHON`, `python` unless set.

Each task had its own recipe, in its own document: the packages, the
hooks, the API, the viewer, the demo, the checks, the browser tests and
the recording.

## Decision

- **uv runs the development side.** The root `pyproject.toml` makes a clone
  a uv workspace of the three packages, with the development tools as its
  `dev` group, and `uv.lock` is committed; `.python-version` names 3.14.
  `uv run` installs Python 3.14 when the machine has none, and the
  packages, editable, with the tools, in `.venv`, before anything it runs.
- **A command for each task,** `uv run <command>`: `help`, `setup`,
  `demo`, `start`, `api`, `viewer`, `check`, `viewer-checks`,
  `browser-tests` and `record-demo`. Each is a console script of the root
  project (`tools/greenhouse_dev`), runs from the repository's root with
  the workspace's Python, and passes what follows its name on.
- **`uv run setup` installs what uv does not:** the viewer's packages,
  Playwright's Chromium and the git hooks. Node 24 stays a prerequisite
  (decision 0008).
- The setup command is `setup`, not `install`: a console script named
  `install` would stand in for the system's `install` in the workspace's
  environment, in what `uv run` starts and in an activated shell. The
  servers start with `start`, since `uv run run` would read badly.
- The pre-push hook runs `uv run check --fast`.
- The packages do not change: each keeps its own metadata and build, and
  installs on its own, with pip or uv. The root project is never
  published.

## Consequences

- The documents quote `uv run` commands, and a test holds every one they
  quote to a command that exists (`tests/test_dev_commands.py`).
- CI and Dependabot still install with pip, from `requirements-dev.txt`
  and the packages' directories. The next change moves CI to `uv sync
  --locked`, Dependabot to its `uv` ecosystem, and removes
  `requirements-dev.txt`, whose pins a test holds equal to the `dev` group
  until then.
- A git worktree gets its own `.venv` from `uv run`, with its own code
  installed, so its tests need no `PYTHONPATH`.
- The commands that start servers run on macOS and Linux: the demo's
  launcher stops its servers by process group.
- Worth revisiting if uv gains a task runner of its own that lists tasks
  with their help, which would replace the root project's console scripts.
