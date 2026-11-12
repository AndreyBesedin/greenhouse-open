# 0077: A crop parameter set is a file, named and versioned, and told apart by its digest

**Status:** Proposed, with [P20](../roadmap/p20-crop-parameter-assets.md)'s plan
**Date:** 2026-11-11

## Context

- **One set per model, by a literal.** Each crop model grown by area has
  its parameters in one Pydantic model (`TomgroParameters`,
  `VanthoorParameters`), whose defaults are its published set. A
  manifest's crop section names the set a run grows by `parameter_set`, a
  literal of one value per model (`gnvman`, `greenlight_2_0_7`), which
  `services/crop_models.py` looks up in a table of one entry. No other set
  can be named, by a manifest or anything else.
- **Units, sources and bounds are not in the schema.** A parameter's unit
  and source are in its module's comments, and in its reproduction's
  manifest (`research/reproductions/*/manifest.json`, 27 parameters for
  Reduced-State TOMGRO and 37 for Vanthoor's model, each with its value,
  unit and source). Its bounds are its type's, positive or not negative,
  so that a form cannot tell a value a tomato may have from one none has.
- **Calibrated sets are cited by their path.** Decision 0076 calibrated
  both models on AGC4's pre-trial. Each set is a research result,
  `research/validation/agc4/calibrated/<model>.json`: the four parameters
  it changes, with their published values, bounds and fit. The test that
  follows cites it by that path. A path names a file in a commit, not
  numbers: a set edited in place keeps its path, and a reader can tell
  which numbers were run only from the commit.
- **How a run is told apart.** A run's identity covers its configuration
  as written, each part's model and version (decision 0054) and, under
  recorded weather, its file's content as a digest (`services/fields.py`).
  A scenario's file names its recording with its digest and may carry it.
  An upload that does not carry the recording is matched by digest to one
  the simulator knows (`scenarios/scenario_files.py`). An epoch is
  self-contained: all that its worker needs is in the store (decision 0067).
- **A row's variety is a word.** An installation's row crop names its
  model and a variety, which nothing reads (`scenarios/installation.py`).

## Decision

**A parameter set is a file.** One JSON document, held by its JSON Schema
(`parameter_set.schema.json`), says:

- `model`: the crop model it is a set of, by its registered name;
- `name` and `version`: what a person calls it, such as
  `agc4_pretrial_2023`, and its version under that name, from 1;
- `based_on`: the set it starts from, by name, version and digest, a
  published set or another;
- `parameters`: the values it changes from its base, by the parameter
  model's field names; every other value is its base's;
- `why`: for each value it changes, where the value comes from, such as a
  calibration's manifest and result, a publication or a measurement;
- `made_for`: the version of the model it was made with;
- `description`: free text.

**Its digest tells it apart.** A set's digest is the SHA-256, whole and
in hexadecimal, of the canonical JSON (sorted keys, no spaces, as a
manifest's is written for its digest) of its model's name and every value
it resolves to, its base's values included. It is not shortened, as a
manifest's is, since a reader outside the repository checks it. Nothing else enters it. A reader can check a set's numbers by
its digest wherever they found it, whatever it was called there, and two
sets of the same numbers have one digest.

**Its name and version are for people.** A set saved under a name takes
the next version of that name. Saved with numbers a version of it already
has, it is that version. A version once saved is never changed or reused,
and a correction is a new version. A simulator refuses a set under a
name and version it keeps with another digest.

**A study cites a set by all three:** its model, name and version, and its
digest, as in `vanthoor_katzin`, `agc4_pretrial_2023` v1, `sha256:…`,
with the model's version and the commit. The digest is what a reader
checks, and the name and version are what they read.

**The published sets are sets.** Each model's defaults are its published
set, version 1, under the name its crop section gives today (`gnvman`,
`greenlight_2_0_7`), based on none. The package writes them from the
parameter model, and nothing stores them. A test pins their digests, so
that a default changed while the model's version stays the same fails
it. They are never edited (decision 0076): a calibration is a set based
on one.

**A parameter declares its unit, source and range.** Each field of a
model's parameter model gives, in the schema it publishes, its unit, its
source and a range: the least and most value a set may give it, each with
where it comes from. A range is wide: the values a tomato, or the
model's equations, allow. A field with no range of its source has its
type's, and says so. A set that gives a value outside a range is refused,
by field. A calibration's bounds are narrower and stay its manifest's
(decision 0076). A test holds the units and sources to the reproduction's
manifest.

**A run names a set as it names its driver profile.** A crop section
gives `parameter_set` and `parameter_set_version`, as it gives
`driver_profile` and `driver_profile_version`, the version being 1 when
left out. The simulator finds the set among the published sets and those
it keeps, and refuses a run that names one it has not.

- A run under a published set is named as it was, so that no packaged
  run's id, checkpoint or replay digest changes.
- A run under any other set is told apart by its set's digest, as a run
  under recorded weather is by its file's.
- A run's manifest answer lists its set's name, version and digest
  beside its model and the model's version.

**Where sets live.**

- *Published:* in the package, from code.
- *Kept:* in the simulator's store, in its party's namespace (decision
  0067), saved through the API and written once.
- *Carried:* a scenario's file and an installation's file carry each set
  they name that is not published, as a scenario's file carries its
  recording. An upload is matched by digest, and refused if the simulator
  keeps a set of the same name and version with another digest.
- *With an epoch:* the store keeps the set an epoch runs beside its
  manifest, so that its worker, a resume and a fork run the same numbers
  whatever is kept or deleted after.
- *As a research result:* beside the study that made it, under
  `research/`, in this format. It is neither packaged nor kept by a
  simulator until someone uploads it.

**A row names the set it grows.** An installation's row crop gives its
model, its variety and its set, by name and version. The crop section's
set is the rows', as its model is, and a manifest whose section names
another is refused. The variety stays a word, what was planted, and the
set is the numbers grown. Rows of different sets are P21's.

**What it covers:** the models whose parameters are one parameter model,
Reduced-State TOMGRO and Vanthoor's model. The organ crop's parameters,
spread over its organs' modules, and the simple crop's, wait until a
calibration asks for a set of theirs. Any model registered with a
parameter model can then have sets without a change to this decision.

## Consequences

- **Decision 0076's calibrated sets can become sets,** each based on its
  model's published set and changing the four parameters it calibrated,
  and its test can cite each by digest. The numbers are those committed,
  and nothing is fitted again. Converting them is the research's own step.
- **The crop sections' literals become names the simulator looks up,**
  and their schema changes with them; the viewer's contracts are
  generated again.
- **The parameter models gain metadata,** and the schemas they publish
  change; no number of a run does.
- **Deleting a kept set ends no run,** since an epoch keeps the set it
  runs: it only stops new runs from naming it.
- **A parameter added to a model changes every set's digest,** its
  published set's included. Runs under sets other than the published ones
  change their ids once; the model's version changes too if the numbers
  do.
- **Worth revisiting:**
  - if sets of other parts' models, such as the climate's or a
    device's, are asked for;
  - if a store shared by several parties needs sets they share.

## Open questions

1. **A cultivar:** whether a set names the cultivar it was made for,
   beside the row's variety. AGC4's two years' cultivars are not known to
   be the same (decision 0076).
2. **Packaging a calibration:** whether a calibrated set is ever
   packaged, so that every simulator offers it: before its model's
   validation (milestone C), after it, or never.
3. **Names across simulators:** two simulators may each save
   `agc4_pretrial_2023` v1 with other numbers. Their digests tell them
   apart, and an upload of the second where the first is kept is refused.
   Whether that is enough, or whether names need a namespace, such as the
   party or the source.
4. **Another model version:** whether a run under a set made for another
   version of its model is refused, or run and said so. Proposed: run,
   with `made_for` beside the model's version in its manifest answer.
