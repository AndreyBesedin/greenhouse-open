# Working in this repository

For anyone changing this repository, by hand or through an assistant: where
the rules are, what to run, what not to edit by hand, and where a change
belongs. The rules themselves live in the documents named here; this page
only points at them.

## The rules

- [docs/engineering.md](docs/engineering.md): the packages' boundaries,
  pull request scope, naming, tests, the review policy and the local
  checks.
- [CONTRIBUTING.md](CONTRIBUTING.md): installing the packages, the hooks
  and the viewer's dependencies.
- [docs/decisions/](docs/decisions/README.md): lasting technical decisions.
  An accepted record is not edited, apart from its status line; a change of
  course is a new record that supersedes it.
- [docs/roadmap/](docs/roadmap/README.md): what is being built, project by
  project, and what was built against what was planned.

## Before a commit, and before a push

```bash
pre-commit run --files <the files changed>
python scripts/check.py --fast   # the pre-push hook runs it too
```

A change to the viewer runs its checks from `greenhouse_sim/web`, after
`npm ci` with Node 24: `npm run lint`, `npm run typecheck`,
`npm run coverage` and `npm run build`. The Biome hook needs `npm ci` for
any commit that touches `greenhouse_sim/web/`, a README included.

Commits and pull request titles follow Conventional Commits
(`type(scope): summary`, decision 0002), and every commit is signed off
(`git commit --signoff`).

## Generated files

Not edited by hand; each is written by the command beside it, and a test
fails when it drifts from its source.

- The viewer's contracts in `greenhouse_sim/web/src/scene/generated/`,
  `greenhouse_sim/web/src/fields/generated/` and
  `greenhouse_sim/web/src/cfd/generated/`: `npm run generate` in
  `greenhouse_sim/web`, from the schemas below.
- The schemas beside their models, such as
  `greenhouse_sim/greenhouse_sim/scene/snapshot.schema.json` and
  `greenhouse_sim/greenhouse_sim/scenarios/scenario.schema.json`, and the
  golden files under `greenhouse_sim/tests/fixtures/`: the test that holds
  each, run with `--update` from `greenhouse_sim/`, for example
  `python tests/test_scene_schema.py --update`. The commit says why they
  moved.
- The browser's screenshot baselines: drawn by CI's visual checks, never
  locally.

## Where a change belongs

- A record producers and consumers share: `greenhouse_protocol`, which
  depends on no other package here. Its changes are the most consequential.
- Simulation: `greenhouse_sim`, organized by domain (decision 0004). The
  reference scenario runs through the climate run
  (`greenhouse_sim/greenhouse_sim/climate/`), the sun
  (`greenhouse_sim/greenhouse_sim/solar/`) and the organ-level crop
  (`greenhouse_sim/greenhouse_sim/core/crop.py`), served by
  `greenhouse_sim/greenhouse_sim/services/`. The engine's day
  (`greenhouse_sim/greenhouse_sim/core/engine.py`) and its model contracts
  drive the simple daily model, the examples and the live stream, not the
  reference scenario; which path a new model joins is still to be decided.
- An API route: the route checks the request and maps the result; the
  logic is a service's (decision 0021).
- A dataset: `greenhouse_adapters`, from a manifest to canonical records.
- The viewer: `greenhouse_sim/web`, which only displays what the simulator
  serves.

## The documents

Public and technical: they describe this open project only (see
[docs/engineering.md](docs/engineering.md)).
