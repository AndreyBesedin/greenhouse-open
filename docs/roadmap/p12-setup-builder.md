# P12: The setup builder

**Status:** in progress: P12.0, P12.1 and P12.2 are done, and P12.3 has
begun; the rest is proposed.
Part of the [simulator roadmap](README.md).

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
  not versioned assets yet: the audit's project for models chosen by the
  manifest (`AUDIT.1` to `AUDIT.4`, after decision 0035, named P10 in the
  audit's work plan before the roadmap's P10 took the consumer interface)
  is where they become so.
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
| P12.3 | Equipment and openings: palettes, surface-mounted doors and vents, many items placed, copied and spaced at once, a property inspector | Items placed many at a time with valid geometry and stable ids; collisions explained or refused; every field editable | In progress: the simulator's edits of many items at once (`builder.items`), its findings of items that collide, the API's `POST /api/builder/edit`, the builder's palette and its items chosen many at once, and the inspector: every field of an item and of the house's envelope and rows, items chosen in the view, and the items an error names outlined on the house. Zones and fixtures placed one by one are left to place and inspect |
| P12.4 | Crop model parameters as versioned assets, edited by schema-driven forms | A tomato parameter set edited, saved, compared, exported, and a run reproduced from its version | Proposed, building on the audit's project for models chosen by the manifest |
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

## QA scenario (proposed)

In the browser: start from the reference greenhouse's house, add a row of
roof vents over two slopes in one edit and undo it, give two rows another
variety and see the builder say the run cannot grow them, put them back,
export the file, import it into an empty builder, and run it: the run's
scene and its first day match the reference greenhouse's.

## Open questions

- Whether a row's crop belongs on an explicit row object rather than beside
  `CropRows`, which repeats one row; P12.5 migrates rather than keeping
  both.
- Whether the first editor ships the schema-driven "Advanced" panel before
  every dedicated control.
