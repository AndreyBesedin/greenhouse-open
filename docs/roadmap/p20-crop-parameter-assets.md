# P20: Crop parameters as versioned assets

**Status:** proposed, not started. It was P12.4 and part of P12.6 in
[the setup builder](archive/p12-setup-builder.md), which closes without it. Part of the
[simulator roadmap](README.md).

## Goal

A crop model's parameters become assets of their own. A set is edited in a form drawn
from the model's schema, within its bounds, saved under a version, compared with
another, exported, and a run is reproduced from its version. A house file names the
versions of the parameters its models use.

## When

Item 8 of the [research priorities](research-validation-priorities.md): once the
registry and the first published model carry versioned parameters. Until then there
is little worth versioning: the sets a person would edit are the published models',
and those are still being reproduced ([P14](archive/p14-models-by-manifest.md)).

## What stays stable

- A model's published defaults: a calibration is a set of its own and never changes
  them.
- The registry: P20 adds none of its own. Its forms edit the typed parameters a model
  registers ([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)),
  and its assets are versions of those.
- Growth algorithms: a form cannot write one. A new model is Python, with its
  conformance tests, and a form edits the parameters of a model that exists.
- The packaged scenarios: their manifests, run ids, seeds, checkpoints and replay
  digests change only where a step says so, with a migration.

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P20.1 | Crop model parameters as versioned assets, edited by schema-driven forms (was P12.4) | A tomato parameter set edited, saved, compared, exported, and a run reproduced from its version | Proposed |
| P20.2 | House files carrying their models' parameter versions, every model field reachable (from P12.6) | A re-imported installation is the same, with the same model references | Proposed |
| P20.3 | The QA scenario below, run and recorded | Each step passes in the browser | Proposed |

## QA scenario (proposed)

In the browser: edit a tomato parameter set within its bounds and see a value outside
them refused, save it under a new version, compare it with the published set, and run
with it. Download the house file, upload it into an empty builder, and run it again:
the same parameter versions and the same run. The published set reads as it did.
