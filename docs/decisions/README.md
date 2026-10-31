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
| [0006](0006-plug-models-in-through-minimal-protocols.md) | Plug simulation models in through minimal protocols | Accepted; the engine's day its contracts plug into superseded by 0035 |
| [0007](0007-world-coordinates-metres-right-handed-z-up.md) | World coordinates are metres, right-handed, z up | Accepted |
| [0008](0008-build-the-viewer-with-npm-node-24-and-vite.md) | Build the viewer with npm, Node 24, Vite and strict TypeScript | Accepted |
| [0009](0009-a-standard-library-local-api-until-streaming-is-needed.md) | A standard-library local API until streaming is needed | Accepted; streaming superseded by 0012; "serves no ground truth" superseded by 0036 |
| [0010](0010-check-the-viewer-with-biome-vitest-and-playwright.md) | Check the viewer with Biome, Vitest and a Playwright smoke test | Accepted; Node-only unit tests superseded by 0029; browser tests in `viewer checks` superseded by 0032 |
| [0011](0011-the-public-api-is-the-top-level-modules-contracts-and-scene.md) | The public API is the top-level modules, the model contracts and the scene | Accepted; the engine's modules, its model contracts and its simple models superseded by 0059 |
| [0012](0012-stream-to-the-viewer-with-server-sent-events.md) | Stream to the viewer with Server-Sent Events | Accepted; superseded by 0059, whose first step removes the live mode and its stream |
| [0013](0013-describe-debug-overlays-as-data-in-world-coordinates.md) | Describe debug overlays as data, in world coordinates | Accepted |
| [0014](0014-compare-screenshots-in-a-pinned-container-in-ci.md) | Compare the renderer's screenshots in a pinned container in CI | Accepted |
| [0015](0015-batch-repeated-shapes-and-benchmark-on-a-graphics-card.md) | Batch repeated shapes, and benchmark the renderer on a graphics card | Accepted |
| [0016](0016-the-greenhouse-has-its-own-frame.md) | The greenhouse has its own frame, described by its envelope | Accepted |
| [0017](0017-envelope-surfaces-face-into-the-greenhouse.md) | Envelope surfaces face into the greenhouse, and carry a category | Accepted |
| [0018](0018-openings-lie-on-a-surface-and-expose-an-aperture.md) | Openings lie on a surface, and expose an aperture | Accepted |
| [0019](0019-fixtures-say-what-they-are-made-of-and-what-they-obstruct.md) | Fixtures say what they are made of, and what they obstruct | Accepted |
| [0020](0020-scenario-layouts-are-declarative-json-files.md) | Scenario layouts are declarative JSON files | Accepted; its comments in the scenarios' modules superseded by 0031 |
| [0021](0021-routes-are-the-interface-services-hold-the-logic.md) | Routes are the interface; services hold the logic | Accepted |
| [0022](0022-plant-organs-are-named-by-where-they-sit.md) | Plant organs are named by where they sit, and draw from a seed hierarchy | Accepted |
| [0023](0023-plants-vary-through-a-shared-vigour-and-keep-their-draws.md) | Plants vary through a shared vigour, and keep what they drew | Accepted |
| [0024](0024-plants-take-their-environment-a-day-at-a-time.md) | Plants take their environment a day at a time, and it only holds growth back | Accepted |
| [0025](0025-shared-vocabulary-in-a-domain-package-and-a-generic-plant.md) | Shared vocabulary lives in a domain package, and a crop builds on a generic plant | Accepted |
| [0026](0026-environment-fields-are-cell-centred-grids-of-packed-floats.md) | Environment fields are cell-centred grids, published as packed floats | Accepted |
| [0027](0027-cfd-runs-out-of-process-on-the-fields-grid.md) | CFD runs out of process, on the environment field's own grid | Accepted |
| [0028](0028-the-world-has-a-site-and-its-x-axis-a-compass-bearing.md) | The world has a site, and its x axis a compass bearing | Accepted |
| [0029](0029-test-hooks-mounted-in-a-dom-file-by-file.md) | Test hooks and components mounted, in a DOM, file by file | Accepted |
| [0030](0030-hold-the-viewers-unit-test-coverage-to-a-floor.md) | Hold the viewer's unit-test coverage to a floor | Accepted |
| [0031](0031-scenarios-are-versioned-json-manifests.md) | Scenarios are versioned JSON manifests | Accepted |
| [0032](0032-run-the-browser-tests-in-lanes-on-ci.md) | Run the browser tests in lanes on CI | Accepted |
| [0033](0033-update-dependencies-with-dependabot.md) | Update dependencies with Dependabot, minor and patch updates merging by themselves | Accepted; its review tick on Dependabot's pull requests superseded by 0034 |
| [0034](0034-approve-dependabots-pull-requests-to-acknowledge-them.md) | Approve Dependabot's pull requests to acknowledge their review | Accepted |
| [0035](0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md) | One simulator, the run, with every part on a ladder of fidelity | Accepted |
| [0036](0036-the-api-shows-people-the-truth-a-policy-reads-observations.md) | The API shows people the truth; a policy reads observations only | Accepted |
| [0037](0037-the-simulators-subpackages-tangle-no-further.md) | The simulator's subpackages tangle no further | Accepted |
| [0038](0038-hooks-merge-like-dev-dependencies-review-waits-for-a-second-maintainer.md) | Hook updates merge like development dependencies; review changes with a second maintainer | Accepted |
| [0039](0039-develop-with-uv-one-workspace-a-command-for-each-task.md) | Develop with uv: one workspace, a command for each task | Accepted |
| [0041](0041-one-run-for-the-viewer-and-a-consumer-played-back-against-one-clock.md) | One run for the viewer and a consumer, played back against one clock | Accepted; the simple live mode it kept superseded by 0059 |
| [0042](0042-a-season-a-thermostat-and-the-heat-it-gives-as-a-modelled-record.md) | A season, a thermostat, and the heat it gives as a modelled record | Accepted |
| [0043](0043-a-target-changed-while-a-run-plays-steers-it-from-then-on.md) | A target changed while a run plays steers it from then on | Accepted |
| [0044](0044-public-records-speak-for-the-project.md) | Public records speak for the project | Accepted |
| [0045](0045-a-release-is-a-pull-request-the-owner-merges.md) | A release is a pull request the owner merges and tags, and CI publishes it | Accepted; the Unreleased entries each pull request wrote superseded by 0056 |
| [0046](0046-one-action-format-and-plan.md) | One action format, and a plan a run's gateway carries out | Accepted |
| [0047](0047-python-lint-rules-a-family-at-a-time.md) | Python lint rules, a family at a time | Accepted |
| [0048](0048-a-simulators-state-is-one-object-passed-explicitly.md) | A simulator's state is one object, passed explicitly | Accepted |
| [0049](0049-a-run-started-from-moves-keeps-its-target-changes.md) | A run started from moves keeps its target changes | Accepted |
| [0050](0050-an-installation-is-the-house-part-of-a-scenario.md) | An installation is the house part of a scenario | Accepted |
| [0051](0051-drafts-are-kept-in-a-local-sqlite-file.md) | Drafts are kept in a local SQLite file | Accepted |
| [0052](0052-a-simulators-authorisation-is-a-file-it-is-given.md) | A simulator's authorisation is a file it is given, the local operator's by default | Accepted |
| [0053](0053-the-viewer-draws-only-when-something-changes.md) | The viewer draws only when something changes | Accepted |
| [0054](0054-models-are-chosen-by-the-manifest-from-a-registry.md) | Models are chosen by the manifest, from a registry | Accepted |
| [0055](0055-a-model-is-registered-with-all-that-tells-it-apart.md) | A model is registered with all that tells it apart | Accepted |
| [0056](0056-a-changelog-is-written-at-release-from-the-pull-requests-merged.md) | A changelog is written at release, from the pull requests merged | Accepted |
| [0057](0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md) | Published models are reproduced, then integrated, then validated | Proposed |
| [0058](0058-a-climate-controller-switches-each-loop-at-its-edge.md) | A climate controller switches each loop at its edge, from the house's air | Proposed |
| [0059](0059-the-engines-day-gives-way-to-the-run.md) | The engine's day gives way to the run | Accepted |
| [0060](0060-two-published-tomato-models-become-crop-models-of-the-run.md) | Two published tomato models become crop models of the run | Accepted |
| [0061](0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md) | Greenhouse decisions are benchmarked through interfaces built for it | Accepted |
| [0062](0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md) | A crop model declares its scope, drivers, outputs and capabilities | Accepted |
| [0063](0063-a-data-file-is-generated-committed-or-fetched-by-one-rule.md) | A data file is generated, committed or fetched, by one rule | Accepted |
| [0064](0064-a-runs-crop-steps-at-its-models-step-not-the-runs-day.md) | A run's crop steps at its model's step, not the run's day | Accepted |
| [0065](0065-a-run-is-a-scenario-at-a-seed-kept-in-a-store-and-played-from-it.md) | A run is a scenario at a seed, kept in a store and played from it | Proposed |

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
