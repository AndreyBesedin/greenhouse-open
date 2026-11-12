# P20: Crop parameters as versioned assets

**Status:** proposed, in progress (P20.1 and P20.2 are done): the steps below, with decision
[0077](../decisions/0077-a-crop-parameter-set-is-a-file-named-and-versioned-and-told-apart-by-its-digest.md),
proposed. It was P12.4 and part of P12.6 in
[the setup builder](archive/p12-setup-builder.md), which closes without it. Part of the
[simulator roadmap](README.md).

## Goal

A crop model's parameters become assets of their own. A set is edited in a form drawn
from the model's schema, within its ranges, saved under a version, compared with
another, exported, and a run is reproduced from its version. A house file names the
versions of the parameters its models use. A study cites the set it ran by its name,
its version and its digest, and a reader checks the numbers by the digest.

## Where it starts

- **One set per model, which nothing else can replace.** Reduced-State TOMGRO's and
  Vanthoor's model's parameters are one Pydantic model each
  (`biology/tomato/tomgro/parameters.py`, `biology/tomato/vanthoor/parameters.py`),
  their defaults the published set. A crop section names it by a literal of one value,
  `parameter_set: Literal["gnvman"]` and `Literal["greenlight_2_0_7"]`
  (`scenarios/crop_parameters.py`), looked up in a table of one entry
  (`TOMGRO_PARAMETERS`, `VANTHOOR_PARAMETERS`, `services/crop_models.py`).
- **Units, sources and bounds outside the schema.** They are in the modules'
  comments and in the reproductions' manifests
  (`research/reproductions/*/manifest.json`), and the schema says only positive or
  not negative.
- **Calibrated sets as research results.** Decision 0076's two sets
  (`research/validation/agc4/calibrated/*.json`) each change four parameters, and the
  test cites them by their paths.
- **What a run's identity already does for a file.** A run under recorded weather is
  told apart by its file's digest, a scenario's file names its recording with its
  digest and may carry it (`services/fields.py`, `scenarios/scenario_files.py`), and
  an epoch keeps all that its worker needs in the store (decision 0067). A set
  follows the recording's path.
- **A form drawn from a schema exists.** The builder's inspector draws a model's
  fields from its JSON Schema (`greenhouse_sim/web/src/builder/schemaForm.ts`).
- **A row's variety is a word that nothing reads** (`scenarios/installation.py`).

## When

Item 8 of the [research priorities](research-validation-priorities.md): once the
registry and the first published model carry versioned parameters. Both tomato
models do, as crop models of the run (milestone B), and decision 0076 has calibrated
them, so its condition holds. P20 changes no file under `research/`, and runs beside
the research priorities' other items.

## What stays stable

- A model's published defaults: a calibration is a set of its own and never changes
  them.
- The registry: P20 adds none of its own. Its forms edit the typed parameters a model
  registers ([decision 0054](../decisions/0054-models-are-chosen-by-the-manifest-from-a-registry.md)),
  and its assets are versions of those.
- Growth algorithms: a form cannot write one. A new model is Python, with its
  conformance tests, and a form edits the parameters of a model that exists.
- The packaged scenarios: their manifests, run ids, seeds, checkpoints and replay
  digests change only where a step says so, with a migration. A run under a published
  set is named as it was (decision 0077).
- The research's own files: decision 0076's calibrated sets, its test and its reports.
  Writing the calibrated sets as sets is the research's step, once P20.2 gives the
  format.

## Design

Decision 0077 settles what a set is, what tells it apart, how a run and a row name
one, and where sets live. In short:

- **A file:** a model, a name and a version, the set it is based on, the values it
  changes with why, the model version and the cultivar it was made for.
- **Its digest:** the SHA-256 of its model and every value it resolves to. Its name
  and version are for people, the digest for checking.
- **The published sets as sets:** `gnvman` v1 and `greenlight_2_0_7` v1, written from
  the code's defaults, their digests pinned by a test.
- **Ranges in the schema:** each parameter's unit, source and range, which a set is
  refused outside of, by field.
- **A run names a set as it names its driver profile,** by name and version; a run
  under any set but a published one is told apart by its digest.
- **Kept, carried and copied:** in the store for those saved, in a scenario's or a
  house's file for those it names, and beside each epoch for the one it runs.
- **Covered:** the two models grown by area. The organ and simple crops wait until a
  calibration asks.

## Steps

Each step is a pull request, or two where it says so. P20.1 and P20.2 are what a
study needs to cite a set; the steps after them are for runs and people.

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P20.1 | **Parameters described:** each field of `TomgroParameters` and `VanthoorParameters` gives its unit, source and range in the schema it publishes; a test holds the units and sources to the reproductions' manifests | Each parameter's schema says its unit, source and range, each range with its source or saying it has none; no run id, checkpoint or replay digest moves | Done: each field says what it is, its unit, its source and its range, published as `parameters.schema.json` beside each model; a range's most comes from the equations or the quantity's meaning (TOMGRO's αF, DFmax, m and TRGH; Vanthoor's θ, ηCO2,AirStom and the two PAR reflections), every other end is its type's and says so; constants, D, T25K and TRGH fixed, read only, each saying why; decision 0076's calibrations, values and bounds, lie within |
| P20.2 | **A set as a file:** its format and schema (`parameter_set.schema.json`), its digest, the published sets as sets with their digests pinned, and a set read, checked, resolved against its base and compared with another, in the package | A set based on a published one resolves to its values, a value outside its range is refused by field, two sets are compared parameter by parameter, and a published default changed without the model's version fails a test | Done: `biology/parameter_sets.py` and `parameter_set.schema.json`; a set names its cultivar (none for the published sets); a fixed parameter at another value, a value with no why and Vanthoor's ordered pairs out of order are refused; the published sets' digests pinned by model version |
| P20.3 | **A run under a set:** `parameter_set_version` in the crop sections; the simulator's sets looked up, the published and those it keeps; the run's identity and its manifest answer; the store keeping the set beside the epoch, for its worker, a resume and a fork | A run under a set reads the same when repeated, and differs from the published set's; the packaged runs' ids are unchanged; a worker runs it from the store alone | Proposed |
| P20.4 | **Sets kept and served:** routes to list a model's sets, read one, save one, compare two, download one and upload one; kept in the store, each version written once; the answers' schemas published and the viewer's contracts generated | The same numbers saved twice are one version; a value outside its range is refused by field; a name and version kept with another digest is refused | Proposed |
| P20.5 | **The form,** in two pull requests: a set edited in the viewer from its model's schema, each field with its unit, source and range (`schemaForm.ts`), saved as a version, compared with its base and downloaded; then chosen for a run in a scenario's form for a new run | A browser test edits a set, sees a value outside its range refused, saves it, compares it with its base, and starts a run under it | Proposed |
| P20.6 | **Files carry their sets** (was P20.2, from P12.6): a row crop names its set; an installation's and a scenario's file carry each set they name that is not published, and an upload is matched by digest; every field of an installation's models reachable in the builder | A re-imported installation is the same, with the same model and set references; an upload carrying a set the simulator keeps under its name and version with another digest is refused | Proposed |
| P20.7 | The QA scenario below, run and recorded | Each step passes in the browser | Proposed |

## QA scenario (proposed)

In the browser: edit a tomato parameter set within its ranges and see a value outside
them refused, save it under a new version, compare it with the published set, and run
with it. The run's answer names the set's name, version and digest. Download the house
file, upload it into an empty builder, and run it again: the same parameter versions
and the same run. The published set reads as it did, and a run under it keeps its id.

## Open questions

Decision 0077's, to settle before the step each touches:

1. Whether a calibrated set is ever packaged: before its model's validation, after
   it, or never (P20.3).
2. Whether a set's name and version need a namespace across simulators, beyond its
   digest (P20.4).
3. Whether a run under a set made for another version of its model is refused, or run
   and said so (P20.3).
