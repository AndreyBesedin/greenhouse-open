# P12: The setup builder

**Status:** in progress: P12.0 to P12.3 are done, and their QA scenario
[recorded](#recorded-at-88f35bae): all but its first day's check passed. The
rest is proposed. Part of the [simulator roadmap](README.md).

## Goal

Author and revise a greenhouse installation in the viewer: start from an
empty house, a packaged scenario's house or a file, edit every property the
simulator's models describe without editing Python or JSON, preview it in
the scene, edit many rows or pieces of equipment at once, see what stops it
running, keep an unfinished version, and exchange it as a file without a
database or a repository. A separate, short step then says where, when and
under what weather to simulate it. The simulator stays usable without the
builder.

## What stays stable

- The packaged scenarios, their manifests, run ids, seeds, checkpoints,
  replay digests and the consumer interface: the builder adds, it changes
  none of them until a step says so with a migration.
- The scene: a preview is the scene the simulator already generates, not a
  second renderer.
- One description of a house: the builder edits the simulator's own models
  (`Envelope`, `Layout`), and an installation is the house part of a
  scenario's manifest (decision 0050), not a second format.

## What exists to build on

- `world.envelope.Envelope`: rectangular, multi-span pitched houses, their
  openings, surfaces and frames; `world.layout.Layout`: crop rows, their
  supports, rails and wires, fixtures, walkways, zones, equipment and
  sensors. The scene is generated from both.
- Scenario manifests (decision 0031) hold the house, the crop, the weather,
  the period and the run's settings, under one format version with its
  migrations (`scenarios/manifest_files.py`); layouts are files of their own
  (`scenarios/layout_files.py`). Both publish a JSON Schema.
- The scenario catalogue (decision 0048) can register a scenario at
  runtime, beside the packaged ones; it becomes safe for runs once each
  simulator has its own stores, at the end of that decision's series.
- `ScenarioConfig` grows one `CropModel` and one variety over
  `rows × columns` positions, and `CropRows` repeats one row pattern.
- Two tomato models, simple and organ by organ. Their parameters are code,
  not versioned assets yet: [P14](p14-models-by-manifest.md), the audit's
  project for models chosen by the manifest (`AUDIT.1` to `AUDIT.4`, named
  P10 in the audit's work plan), is where they become so.
- `world.site.Site` (latitude, longitude, elevation, time zone, the house's
  bearing) and the weather presets, which are synthetic: a site alone
  supplies no local weather.

## Design

1. **Installation, scenario, run.** An installation is the house: envelope,
   layout and the crop each row grows (decision 0050). A scenario adds the
   weather, the period, the controller, the seed and the models' settings.
   A run is a scenario resolved to its content's digest and played as
   epochs. Editing an installation never changes a scenario or a run.
2. **One schema.** The builder edits `Envelope` and `Layout` directly, and
   the viewer reads their published JSON Schemas; no second copy of a field
   lives in the editor or a store.
3. **A portable file.** An installation's file holds its fields as a
   manifest writes them, under the manifests' format version, and may name
   `installation.schema.json`. It names crops by model and variety and holds
   no code: a model it names must be one the simulator runs.
4. **Drafts and publication.** Drafts and their revisions are kept as
   validated documents, locally first; exchanging a file needs no store.
   Publishing an installation as a packaged scenario is a reviewed pull
   request, and the repository's files stay the packaged scenarios'
   authority.
5. **Readiness is graduated.** A value no greenhouse can have is refused by
   the models. What the parts get wrong together (an item through a wall, a
   row without a crop) is an error a draft may keep but a run may not;
   absent doors, vents, heaters or fans are warnings, since a research house
   may do without them. Each finding names the items and rows it concerns.
6. **Many at once.** Choosing many rows, fixtures or pieces of equipment
   and changing, copying or spacing them is an operation of the draft, not
   repeated form submissions: it checks everything it changes first, and is
   undone in one step.

## How a person uses it

1. **A start:** an empty house, a packaged scenario's house (copied; the
   original is not changed), or a file.
2. **The house:** name, length and width, eave and ridge heights, spans and
   bays; then the crop rows: how many, plants per row, pitch, spacing and
   support height. Roof spans, crop rows and service paths are told apart.
3. **The crop:** each row a crop model and a variety, chosen for all rows,
   a range or any rows at once. Rows of different crops can be drafted,
   and the builder says a run cannot grow them yet.
4. **Preview and edit:** the scene, its surfaces, rows, fixtures and
   equipment selected and edited in place; doors and vents added to
   surfaces, equipment, sensors, walkways and zones from palettes; a row of
   vents spread over chosen roof slopes, fans or sensors repeated at an
   offset, one property changed over a selection. Each such edit shows what
   it will change and how many items, names them predictably, explains a
   collision, and is undone in one step. Positions are in metres in the
   house's frame.
5. **Check and keep:** a draft is kept at any step, runnable or not, with
   its errors and warnings beside the items they concern; it is exported
   and imported as a file.
6. **The scenario:** where (a site), when (a start date and a number of
   days) and under what weather (a preset, or the scenario's own). A
   weather is never presented as observed at the site when it is
   synthetic. More settings stay under "Advanced".
7. **Simulate:** a draft without errors, resolved to a scenario, runs as
   any scenario does.
8. **Share:** the file, or a reviewed pull request adding it as a packaged
   scenario.

An "Advanced" panel reaches every field the models have, schema-driven,
where no dedicated control exists yet; it is a fallback, not a second way
to describe a house.

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P12.0 | An installation drafted from a form's values, assessed, edited many rows at a time, exchanged as a file; decision 0050 | A file reads back as the draft it was written from; a refused file names its fields; findings name their items and rows; no packaged scenario changes | Done |
| P12.1 | A manifest holds or names an installation, by a manifest migration; a draft resolved into a scenario and registered at runtime; drafts and revisions kept locally | A packaged scenario's run id unchanged by the migration; a draft without errors runs; drafts saved, reopened and reverted; files exchanged without the store | Done |
| P12.2 | The builder in the viewer: start, house form, preview, rows chosen together, the scenario step | Create, preview, import, export, save, reopen and run a house in the browser, by keyboard too; its browser QA | Done: the builder page at `/builder` (a start from the form, a draft, a file or a scenario's house; rows chosen together; undo and redo; save, export, and the scenario step and run), with its browser tests. The findings are listed by the rows they concern; shown on the house, and every field reached, with P12.3's property inspector |
| P12.3 | Equipment and openings: palettes, surface-mounted doors and vents, many items placed, copied and spaced at once, a property inspector | Items placed many at a time with valid geometry and stable ids; collisions explained or refused; every field editable | Done: the simulator's edits of many items at once (`builder.items`): equipment, sensors, zones, fixtures placed one by one, doors and vents, with its findings of items that collide; the API's `POST /api/builder/edit`; the builder's palette and its items chosen many at once; and the inspector: every field of an item and of the house's envelope and rows, items chosen in the view (a pipe run or a rail by any of its parts), and the items an error names outlined on the house; with their browser tests |
| P12.4 | Crop model parameters as versioned assets, edited by schema-driven forms | A tomato parameter set edited, saved, compared, exported, and a run reproduced from its version | Proposed, building on [P14](p14-models-by-manifest.md), models chosen by the manifest |
| P12.5 | Rows of different crops run | Different models or varieties per row simulated reproducibly, or refused by name | Proposed |
| P12.6 | Publication: a reviewed pull request from the builder, files carrying their models' parameter versions, every model field reachable | A re-imported installation is the same, with the same model references | Proposed |

### P12.0: what it does, and what it leaves

`greenhouse_sim.builder` holds the draft (`InstallationDraft`: an
installation id, a name, an `Envelope`, a `Layout`, a `RowCrop` per row;
`scenarios.installation.Installation` since P12.1),
its assessment (`assess_installation`, `Finding`s with a code, a message,
and the items and rows concerned), the first form's draft
(`basic_installation`), one edit of many rows (`assign_crop_to_rows`) and
the file (`export_installation`, `import_installation`, refusing with a
`Problem` per field at fault, and `installation.schema.json`).

It keeps no draft, resolves nothing into a scenario, places no equipment,
and runs no row of another crop; P12.1 to P12.5 do.

### P12.1: the manifest's installation, drafts kept, and drafts run

A manifest in format 4 holds its house as an installation, under
`installation`: its id and name, its envelope, its layout by name (a
scenario's layouts stay files of their own, with their alternatives), and
the crop every row grows. The installation's model,
`scenarios.installation.Installation`, moved from the builder, which
imports it. `scenario_house` gives a scenario its house from it, the
layout's crop rows and their planting positions as the run's rows and
columns, and refuses an installation a run cannot grow: no crop rows, a
row without a crop, rows of different crops (P12.5).

A format 3 manifest is migrated: its house fields become its installation,
named for its scenario, every row growing its crop. The packaged manifests
are written in format 4, read to configurations equal to format 3's, so
every run id and replay digest stays. A manifest's version, its content's
digest, changes, and with it the kept opening day's and the checkpoints'
manifest field.

A manifest naming an installation's file, rather than holding it, waits
for something that needs it: a draft is run by registering its scenario
with the simulator, not by writing a manifest.

Drafts and their revisions are kept in a local SQLite file (decision
0051, `builder.drafts`), each revision its installation's file, so that a
revision saved in an older format is read as the file is. A change names
the revision it was made on and is refused if another was saved since.

The API keeps them (`services.drafts`): drafts are listed, opened at any
revision with what stops them running, saved from an installation's file,
reverted and deleted, a change on a stale revision answered as a conflict
(409). The server keeps them in `~/.greenhouse-sim/drafts.sqlite3`, or the
file `--drafts` names; where its default cannot be made, it keeps none.

A draft runs as a scenario of its own (`POST /api/drafts/{id}/run`): its
installation at a revision, with a start date and days (a year and a day
at most), a site, a seed and a weather by name, registered with the
simulator answering (decision 0048) as `<draft>_r<revision>` or the name
given. It is then listed, drawn and run as any scenario is. A draft the
assessment finds errors in is refused with each, and a run under a
packaged scenario's name, or one registered otherwise, is a conflict.

The browser tests' server keeps drafts in that default file too: a test
that saves one gives the server a file of its own, so as never to write
to the user's.

### P12.4 and the models chosen by the manifest

The audit plans a project for models chosen by the manifest: a model's
identity and version, its state in a checkpoint, reproducibility, how the
viewer meets models it was not built with, and the simple model's numbers
in a section of their own, by a versioned manifest migration. P12.4 starts
when that project has given a crop model an identity, a version and typed
parameters: its forms edit those parameters, and its assets are those
versions. P12.4 adds no registry of its own.

Until then a form cannot author a growth algorithm: new models are Python,
with their conformance tests, and a form edits the parameters of an
existing one within their bounds.

## Tests and review

- The models' own checks for impossible values; findings for what the
  parts get wrong together; a file's round trip and its refusals by field;
  edits of many items that change everything chosen or nothing.
- From P12.1: a draft resolved to a scenario with a stable run id, the
  manifest migration's run ids unchanged, drafts' revisions migrated.
- From P12.2: keyboard forms, selection, undo and redo, unfinished drafts,
  the findings shown by their items, the scenario step, every field
  reachable.
- Safety: unknown fields refused, no code imported, a file's size bounded,
  drafts saved atomically, packaged scenarios never changed by an edit.

## QA scenario

In the browser: start from the reference greenhouse's house, add a row of
roof vents over two slopes in one edit and undo it, give two rows another
variety and see the builder say the run cannot grow them, put them back,
export the file, import it into an empty builder, and run it: the run's
scene and its first day match the reference greenhouse's.

### Recorded at `88f35bae`

Run on 5 November 2026 on `88f35bae`, 0.6.0 and what merged after it, on the Vite development
server (StrictMode) in a headed Chromium drawing with the machine's GPU (ANGLE Metal, Apple M2),
with an API and a state folder of its own. Exporting is now *Download house file*, and a run is
started by *Save and start a run*, on a worker, in its replay; they were walked in place of the
scenario's words.

| Step | Result | What was seen |
| --- | --- | --- |
| Start from the reference greenhouse's house | Passed | *Copy its house*: a draft not saved, 23 items and 4 rows, nothing found against it, and it can run. |
| Roof vents over two slopes, in one edit | Passed | Four on each of `roof 1 left` and `roof 2 left`: "Placed 4 roof vents on 2 surfaces.", 31 items, `roof_vent_4` to `roof_vent_11`, drawn on the roof. Over `roof 1 right`, which holds a vent: "Doors or vents overlap: roof_vent_1 with roof_vent_5, roof_vent_1 with roof_vent_6", the items outlined on the house, and it cannot run. |
| Undo | Passed | One step: 23 items, and it can run. |
| Two rows given another variety | Passed | "Rows grow different crops; a run grows one model and one variety." *Save and start a run* is disabled, and the run step says why. |
| Put back | Passed, once the model is chosen too | The rows' form starts at the `simple` model whatever the rows grow, so typing only the variety back leaves rows 2 and 3 on another model, and the same error. Choosing `organ` as well: it can run. |
| Export | Passed | *Download house file*: `<identifier>.house.json`. |
| Import into an empty builder | Passed | *Start again*, which asks first, then the file: the same 23 items and 4 rows, nothing found against it. |
| Run it | Passed | From 1 March 2026, seed 42, 2 days: `ref_qa_10816_r1-climate-806a05ba`, finished on a worker, its replay drawn. |
| Its scene matches the reference greenhouse's | Passed for the house | The 148 entities that are not plants' are equal, but for the scenario's name each holds; the envelope, layout, crop and site read from the file equal the scenario's. The plants differ, 2,883 entities against 2,958: a plant is drawn from its identifier and seed (`transplant`), and its identifier holds the scenario's name, so a house copied under another name grows other plants at the same seed. |
| Its first day matches the reference greenhouse's | **Failed as written** | The house's air starts at 18 °C, not 14 °C, and averages 10.1 °C over the day, not 17.0 °C. A house's file holds no more than the house (design point 1): the run has neither the scenario's heating loops (`control`), its daily commands (`daily`), its weather, its crop work, its start of the air (`climate`) nor its `airflow`. The run step offers the presets by name, and not the reference's season. |

What is left: to say what this check should compare. Either the scenario's words change to the
house and its plants' rows, as design point 1 has it, or copying a scenario's house offers to keep
that scenario's settings for the run, as `services.drafts` keeps those of a scenario that is not
packaged (`_kept_from_its_scenario`). Until that is decided the check stands as failed. P12.0 to
P12.3 keep their status: what each was accepted for passed in the walk.

Also seen: the house form's labels *Origin Position X* and *Origin X* say little of what tells them
apart. The console was clean but for the renderer library's deprecation warning.

Not run: the house form and palette by keyboard alone, which the browser tests do in part; a
packaged scenario's own file, whose upload is refused as a packaged scenario's
(`e2e/scenario-file.spec.ts`); a first day compared at the replay's own readings, the comparison
above being the API's climate run of each scenario.

A browser test holds what can be held: `builder.spec.ts`, the reference greenhouse's house edited,
put back, through its file and run, its scene's house equal to the scenario's.

## Open questions

Answered from the code at the commit above, or carried on:

- **Whether a row's crop belongs on an explicit row object rather than beside
  `CropRows`, which repeats one row.** Not yet asked of the code: `Installation.row_crops` holds a
  crop per row number beside `CropRows`, and a run refuses rows that differ
  (`scenario_house`), so nothing yet needs rows to be objects. Carried into P21, rows of different
  crops, which migrates rather than keeping both.
- **Whether the first editor ships the schema-driven "Advanced" panel before every dedicated
  control.** It did, by another name: no panel is called "Advanced", and the *Envelope and rows*
  form and the items' inspector are read from the published schema (`builder/schemaForm.ts`), so
  every field of an item and of the house's envelope and rows is reached now. The fields of a crop
  model are not, which P20, crop parameters as versioned assets, carries.
