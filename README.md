# greenhouse-open

Open building blocks for greenhouse data: a shared record format, a
deterministic greenhouse simulator, and adapters that turn published
research datasets into that format.

| Package | What it is |
| --- | --- |
| [`greenhouse-protocol`](greenhouse_protocol/) | Canonical records (observations, events, media captures, sensors, semantic actions and their outcomes, greenhouse descriptions) and the contracts a producer or consumer implements: record stores and queries, action execution, conformance checks, and an in-memory reference store. |
| [`greenhouse-sim`](greenhouse_sim/) | A simulator with a hidden truth and noisy sensors. Its runs publish canonical observations, accept semantic actions, and expose ground truth only through a separate evaluation interface. Each part of a run is a ladder of models a scenario's manifest chooses from, and a browser viewer shows what it is doing. |
| [`greenhouse-adapters`](greenhouse_adapters/) | Reproducible adapters from recorded datasets to canonical records, starting with the Wageningen University & Research Autonomous Greenhouse Challenge datasets, and the `greenhouse-data` command. |

## Demo

Greenhouse Open v0.5.0 — Greenhouse Simulation

https://github.com/user-attachments/assets/a09386c8-7823-4321-992f-0261f37bf91d

The whole walk-through at its own pace, each step held under its caption,
recorded from 0.5.0:

[The whole walk-through, on YouTube](https://youtu.be/APUb6oex13o)

## Why a shared format

Simulated, recorded and live greenhouses should look the same to whatever
consumes them. A consumer reads observations and events, asks for them only
up to the instant it is deciding at, and proposes actions that some executor
validates and carries out. It never learns whether the producer was a
simulator, an imported dataset or a sensor gateway. That makes a simulator
a test bed for real decision logic, and a recorded dataset a replay of a
real season.

The simulator matters because it is the one setting where a decision can be
scored against what was really true. Its ground truth leaves by a separate
path from its observations, so decision logic cannot use it by accident.

## Run it

On a machine with [uv](https://docs.astral.sh/uv/getting-started/installation/)
and, for the browser viewer, [Node 24](https://nodejs.org):

```bash
git clone https://github.com/AndreyBesedin/greenhouse-open.git && cd greenhouse-open
uv run setup   # installs everything: Python 3.14 if missing, the packages, the viewer
uv run demo    # starts the simulator and its viewer, on the reference greenhouse
```

`uv run demo` opens the reference greenhouse: 32 tomato plants grown organ
by organ through a spring season, in the air its heater, vents and fans
make under the sun, watched by its sensors and a camera. Ctrl+C stops it.
[docs/demo.md](docs/demo.md) says what to look at, and what the simulator
simplifies.

Every task is a command, run from the clone as `uv run <command>`; what
follows the command's name goes to what it runs (`uv run demo --no-browser`,
`uv run check --fast`):

| Command | What it does |
| --- | --- |
| `uv run help` | lists the commands |
| `uv run setup` | installs what `uv run` does not: the viewer's packages, Playwright's Chromium and the git hooks |
| `uv run demo` | the simulator's API and the viewer, open on the reference greenhouse |
| `uv run start` | the same, open on the viewer's start page |
| `uv run api` | the simulator's local API alone, on port 8765 |
| `uv run viewer` | the viewer's development server alone, on port 5173 |
| `uv run check` | the repository's Python checks, as CI runs them; `--fast` leaves out the slow tests, as a push does |
| `uv run viewer-checks` | the viewer's lint, type check, unit tests and build |
| `uv run browser-tests` | the viewer's browser tests, against the simulator |
| `uv run record-demo` | records the demo's walk-through as a video |

`uv run` itself installs Python 3.14, when the machine has none, and the
three packages with the development tools, in `.venv`, before running any
command. Nothing needs activating, and the shell's own Python is not used.

## Examples

```bash
uv run python examples/01_run_a_simulation.py        # a deterministic run and its observations
uv run python examples/02_store_and_query.py         # store, query, and never see the future
uv run python examples/03_close_the_loop.py          # observe, decide, act, observe again
uv run python examples/04_score_against_ground_truth.py  # how noisy is the sensing?
```

Recorded data, with nothing heavier than about 10 MB downloaded:

```bash
uv run greenhouse-data inventory wur agc4-2024
uv run greenhouse-data prepare wur agc4-2024 --profile tiny
```

`prepare` writes deterministic canonical records under
`GREENHOUSE_DATA_DIR` (default `~/.greenhouse-open/data`). See
[`greenhouse_adapters`](greenhouse_adapters/) for profiles and datasets.

## Install the packages elsewhere

The packages are not on PyPI yet. Into another project's environment, from
a clone:

```bash
uv pip install ./greenhouse_protocol ./greenhouse_sim ./greenhouse_adapters
```

or `python -m pip install` with the same paths, from an activated virtual
environment, not into a system's Python. Python 3.14 or newer. Each package
also installs on its own, with only its declared dependencies
(`greenhouse-sim` and `greenhouse-adapters` need `greenhouse-protocol`).

## Development

`uv run setup` installs the git hooks: before a commit, file hygiene, Ruff
and Biome; before a push, `uv run check --fast`. Before requesting review of
a non-trivial change, `uv run check` runs the full repository check, the
command CI runs; a change to the viewer also runs `uv run viewer-checks` and
`uv run browser-tests`.

Each package is still checked from its own directory with its own configuration,
as a user installing it alone would see it. `tests/` at the top level holds
checks that span packages: every producer against the canonical contract,
each package's declared dependencies, and the examples. The browser viewer
in `greenhouse_sim/web` has its own checks (Biome, TypeScript, Vitest, and
Playwright's browser tests in lanes), which CI runs as separate jobs; see
[docs/engineering.md](docs/engineering.md#local-checks).

Engineering conventions, pull request scope guidance and the solo-developer
review policy live in [docs/engineering.md](docs/engineering.md). Where the
simulator is heading is in [docs/roadmap/](docs/roadmap/README.md), and the
lasting technical decisions behind it are in
[docs/decisions/](docs/decisions/README.md).

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). Datasets are
not redistributed here: the adapters download them from their publishers,
under the publishers' licences.
