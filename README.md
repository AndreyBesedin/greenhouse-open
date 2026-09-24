# greenhouse-open

Open building blocks for greenhouse data: a shared record format, a
deterministic greenhouse simulator, and adapters that turn published
research datasets into that format.

| Package | What it is |
| --- | --- |
| [`greenhouse-protocol`](greenhouse_protocol/) | Canonical records (observations, events, media captures, sensors, semantic actions and their outcomes, greenhouse descriptions) and the contracts a producer or consumer implements: record stores and queries, action execution, conformance checks, and an in-memory reference store. |
| [`greenhouse-sim`](greenhouse_sim/) | A simulator with a hidden world and noisy sensors. It publishes canonical observations, accepts semantic actions, and exposes ground truth only through a separate evaluation interface. |
| [`greenhouse-adapters`](greenhouse_adapters/) | Reproducible adapters from recorded datasets to canonical records, starting with the Wageningen University & Research Autonomous Greenhouse Challenge datasets, and the `greenhouse-data` command. |

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

## Install

The packages are not on PyPI yet. From a clone:

```bash
python -m pip install ./greenhouse_protocol ./greenhouse_sim ./greenhouse_adapters
```

Python 3.12 or newer. Each package also installs on its own, with only its
declared dependencies (`greenhouse-sim` and `greenhouse-adapters` need
`greenhouse-protocol`).

## Examples

```bash
python examples/01_run_a_simulation.py        # a deterministic run and its observations
python examples/02_store_and_query.py         # store, query, and never see the future
python examples/03_close_the_loop.py          # observe, decide, act, observe again
python examples/04_score_against_ground_truth.py  # how noisy is the sensing?
```

Recorded data, with nothing heavier than about 10 MB downloaded:

```bash
greenhouse-data inventory wur agc4-2024
greenhouse-data prepare wur agc4-2024 --profile tiny
```

`prepare` writes deterministic canonical records under
`GREENHOUSE_DATA_DIR` (default `~/.greenhouse-open/data`). See
[`greenhouse_adapters`](greenhouse_adapters/) for profiles and datasets.

## Development

```bash
python -m pip install -e ./greenhouse_protocol -e ./greenhouse_sim -e ./greenhouse_adapters \
    -r requirements-dev.txt
for p in greenhouse_protocol greenhouse_sim greenhouse_adapters; do
    (cd $p && ruff check . && ruff format --check . && mypy && pytest -q)
done
ruff check tests examples && mypy && pytest -q   # cross-package tests and examples
```

Each package is checked from its own directory with its own configuration,
as a user installing it alone would see it. `tests/` at the top level holds
checks that span packages: every producer against the canonical contract,
each package's declared dependencies, and the examples.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). Datasets are
not redistributed here: the adapters download them from their publishers,
under the publishers' licences.
