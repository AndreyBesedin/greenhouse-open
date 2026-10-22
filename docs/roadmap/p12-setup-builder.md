# P12: Greenhouse Setup Builder

**Status:** Foundation in progress

## Purpose

Author and revise an installation in the browser, starting from an empty
greenhouse, importing a portable file, or copying a repository template.
A person should be able to edit every supported declarative greenhouse
property without editing Python or JSON, preview the scene, batch-edit
multiple rows or pieces of equipment, receive actionable feedback, save an
unfinished version, and import/export it without a database or Git.
After installation editing, a separate lightweight scenario screen selects
where, when and under what weather to simulate it. Keep the headless
simulator independent of the editor.

## Existing foundations and constraints

- `world.envelope.Envelope` already defines rectangular, multi-span pitched
  houses, their openings, surfaces and size constraints.
- `world.layout.Layout` defines parallel crop rows, supports, gutters,
  benches, rails, wires, fixtures, walkways, zones, climate equipment and
  sensors; the scene generator consumes that description.
- `scenarios/layout_files.py` loads schema-backed, declarative JSON
  layouts. Versioned scenario manifests hold the envelope, crop choice,
  weather and simulation settings (`scenarios/manifest_files.py`).
- `scenarios.SCENARIO_REGISTRY` is loaded from packaged files at import time.
  Its lifecycle is unsuitable for interactive draft creation.
- `ScenarioConfig` has one `crop_model`, one `variety` and a
  `rows * columns` count. `CropRows` repeats one geometrical row pattern.
  An author can name a crop for each row, but the simulator cannot yet run
  heterogeneous crops.
- Today's supported tomato simulations are the simple daily model and the
  organ-level model. Their code and parameters are not independent,
  versioned, user-editable model assets.
- `world.site.Site` already holds latitude, longitude, elevation,
  IANA time zone and world x-axis bearing for sun and wind directions.
  `weather.presets.PRESETS` provides synthetic weather cases, not a
  regional historical forecast. Site selection alone does not supply
  credible local weather.

## Design boundaries

1. **Installation vs scenario vs run.** The installation is the physical
   envelope, layout and row plantings. A scenario binds it to a weather,
   model versions, simulation dates, seed and controls. A run binds a
   resolved scenario to an immutable content digest and execution epoch.
   Editing an installation never edits a running scenario.
2. **One domain schema.** Reuse `Envelope`, `Layout`, equipment and
   opening models directly; do not implement second copies in the UI or
   persistent store. The API publishes JSON Schema / generated TypeScript
   types for editor fields. Additional authoring metadata, especially row
   crops, must have an explicit compatibility adapter to `ScenarioConfig`.
3. **Portable canonical data.** Keep JSON as the authoritative interchange
   format initially, consistent with the existing manifests and layouts.
   Export/import a versioned `greenhouse-open.installation` JSON document
   independently of Git, the local database, paths and schema migrations
   in an existing environment. Import creates or replaces an explicit draft
   only with user confirmation, never a published object or active run.
   This file contains the complete installation definition, including
   crop references, but not arbitrary Python implementations. A referenced
   model must be installed to run. A future ZIP bundle may include
   versioned declarative model assets. YAML can be a later optional
   representation, not another canonical model.
4. **Drafts vs publication.** A local SQLite store will hold editable drafts
   and revisions as validated JSON documents plus metadata, not a
   hand-normalized copy of every nested model field. Import/export is an
   independent capability available to offline and database-free workflows.
   Promotion to the shared open-source catalogue is an optional reviewed
   Git pull request. Repository files remain the authority for published
   templates and models. No live Git write is part of a simulator step.
5. **Readiness is graduated.** Invalid values are refused by Pydantic;
   cross-object violations prevent running or publishing but can be
   preserved as drafts. Absence of doors, heating, roof vents or fans raises
   warnings, not hard errors. A greenhouse research case need not have the
   equipment of a commercial production facility.
6. **Performance and compatibility.** The current packaged scenarios,
   URL semantics, seeds, snapshots, checkpoints, and consumer replay stay
   unchanged. The editor is an optional mode. Preview uses the existing
   scene generator, not a second mesh renderer.
7. **Batch operations are first-class.** Selecting many rows, fixtures or
   equipment items and assigning properties, copying or distributing
   them is a domain operation, not repeated UI form submissions. Each
   operation validates its full target set and yields one undoable result.
   The editor previews placement and warnings before applying a batch.

## Proposed user flow

1. **Choose a starting point:** empty greenhouse, import a portable
   `.greenhouse.json` file, or clone a published template. Cloning records
   its source revision; the original remains immutable. No Git connection
   or existing SQLite state is required to import a standalone installation.
2. **Basic structure form:** name; greenhouse length and width; roof
   eave/ridge height; spans and structural bays; number of crop rows;
   plants per row, pitch, row spacing and support height. Clearly
   distinguish *roof spans*, *crop rows* and *service lanes*. For now the
   footprint is rectangular with pitched multi-span roofs.
3. **Planting:** each row gets exactly one plant-model revision and variety.
   Support selecting all rows, a range, or arbitrary rows and applying a
   crop choice to them in one action. A row may have a different crop from
   its neighbours in the draft, but the editor must report that the current
   runtime can grow only one model and variety per scenario. Parameter
   variants of an existing model come before new biological implementations.
4. **Preview and edit:** reuse the existing 3D scene; select envelope
   surfaces, rows, fixtures and equipment to edit their fields. Add roof
   vents and doors to surfaces; add fans, heaters, dehumidifiers, sensors,
   walkways, zones and fixtures through category palettes. Support batch
   generation (N vents evenly across chosen roof surfaces), duplication
   (repeat selected sensors or fans with an offset), and bulk property edits
   (height, spacing, model or variety). Every batch has a preview, a clear
   affected-item count, deterministic names, collision warnings, an atomic
   commit and a single undo. Explicitly position items in metres in the
   greenhouse's right-handed, z-up frame.
5. **Validate and save:** save incomplete drafts at any step, including
   configurations that are not yet runnable. Present errors and warnings
   linked to their objects and properties. Import/export without a
   database and independent of Git. A draft edit never changes a run.
6. **Configure scenario (after installation):** offer three simple sections:
   **Location** (site/region preset: latitude, longitude, elevation,
   time zone; house orientation in Advanced), **Period** (start date and
   duration in days), and **Weather** (synthetic weather preset or scenario
   default; richer recorded/seasonal sources later). Do not derive weather
   from the region alone or label synthetic weather as locally observed.
   Resolve these settings and the pinned installation into a runnable
   `ScenarioConfig`. More climate, control and crop-work parameters live
   under Advanced and can be progressively promoted to the simple form.
7. **Simulate:** only a validated, supported, version-pinned scenario may
   start a run. It uses the current run/clock, observation and scene stack.
8. **Share/publish:** export an installation file for direct sharing, or
   optionally propose a Git PR containing its declaration and pinned model
   assets. Track source, research assumptions, versions and citations.

An **advanced properties** panel should expose every editable declarative
field the simulator supports, even when no dedicated widget exists. A JSON
editor with schema validation is a fallback for complex supported fields,
not an excuse to maintain permanently separate UI and file capabilities.
Python-only changes still require code, tests and review.

## Plant-model catalogue and revisions

Separate **implementation**, **parameter set** and **row assignment**:

- A biological implementation supplies Python methods and validated parameter
  models; examples now are tomato simple and tomato organ. Future crop
  implementations follow the model protocols and conformance tests.
- A parameter-set revision stores parameter values, units, descriptions,
  bounds, citation/provenance and the implementation version it requires.
  Its form comes from its schema, rather than a guessed universal plant form.
  A user may fork a parameter set, save drafts, compare revisions, and
  publish one as a JSON asset after review.
- A row selects a compatible, version-pinned asset, with its variety.
  Published scenarios resolve references before running. Mixed row models
  require a run-crop abstraction and heterogeneous planting positions;
  they are deliberately **not** assumed to work today.
- `parameters.py` remains code and the source of default/structural
  assumptions until a tested extraction gives the model an authoritative
  typed parameter object. Avoid duplicating parameters between a Python
  constant and a database definition.

This design avoids pretending a form can author a brand-new executable plant
growth algorithm. New mathematical model implementations remain Python;
forms can author scientifically bounded parameterizations of those models.

## Implementation slices

| Gate | Work | Acceptance |
| --- | --- | --- |
| **12.0 Authoring foundation** | Typed installation drafts, basic generator, row crop references, readiness findings, portable JSON import/export, first atomic bulk crop assignment | JSON round-trip, invalid-input checks, no packaged scenario changes, no database dependency |
| **12.1 Resolution and storage** | Installation/scenario/run identity, resolver into existing `ScenarioConfig`, tiny scenario defaults, local SQLite draft revisions and immutable run snapshots; publish schemas | Save/reopen/revert; export/import without SQLite; launch supported homogeneous scenario; old scenarios/replay unchanged |
| **12.2 Wizard, preview and scenario UI** | Setup Builder route, blank/template/import launch, structure form, existing scene preview, row batch selection and three-part location/period/weather step | Create/preview/import/export/save/reopen/run; keyboard flow and browser QA |
| **12.3 Batch equipment and opening editor** | Typed catalogue, surface-mounted doors/vents, climate units, sensors, fixtures, multiple selection, array/clone/distribute, property inspector, atomic undo | Batch placement with valid geometry and stable IDs; collisions explained, rejected or previewed; schema fields editable |
| **12.4 Plant-model assets** | Model registry, schema-driven parameter forms, forked drafts, versioned parameter assets and citations | Edit a tomato parameter set, save, compare, export and reproduce a run using a pinned version |
| **12.5 Row-specific runtime support** | Generalize current `CropRows` and `ScenarioConfig` limitations, crop model contract and scene/checkpoint/log handling | Different models/varieties per row reproducibly simulated, or explicitly refused for unsupported combinations |
| **12.6 Publication and completeness** | Optional reviewed Git publication, portable bundles with declarative model assets, templates, parity checklist between schemas and UI | Re-import yields same installation and model references; all supported declarative fields reachable through UI or advanced editor |

### Gate 12.0 scope and limitations

The first additive backend slice defines `builder.InstallationDraft`,
`basic_installation`, `import_installation`, `export_installation` and
`assign_crop_to_rows`. It generates rectangular pitched greenhouses and
homogeneous row geometry, records crop references, warns about missing
facilities, exports/imports a portable versioned file and edits a group of
rows atomically. It does **not** persist drafts, resolve crop model IDs,
publish schemas, generate bulk equipment, instantiate arbitrary per-row
crop models or run them. The standalone JSON document round-trips without
Git, SQLite or changes to packaged scenarios. Compatibility with
`ScenarioConfig` is the next gate.

## Test and review expectations

- Unit tests: invalid dimensions, roof below eaves, overlapping or
  out-of-envelope fixtures, duplicate identifiers, missing crop assignments,
  missing optional equipment and schema round-trip.
- Integration tests: drafts to `ScenarioConfig`, stable run digests, seed
  determinism, portable document versions, missing model references,
  imports without a database, and migrations of persisted draft versions.
- Batch tests: selected rows retain unselected assignments, stable placement
  identifiers, deterministic spacing, empty/invalid selections, all-or-nothing
  validation, geometry collisions, one undo for a complete batch.
- Viewer tests: keyboard forms, selected geometry, undo/redo, unfinished
  drafts, validation messages, scenario settings and advanced-property parity.
- Safety: unknown fields rejected, no arbitrary code execution or path
  traversal, bounded revision size, atomic persistence, immutable published
  assets and no draft mutation during simulation.

## Decisions to validate at later gates

- Local SQLite first; if a hosted collaborative application is introduced,
  keep the same document/revision contract with an interchangeable store.
- Whether row assignments eventually sit on explicit row objects rather than
  alongside today's homogeneous `CropRows`; migrate rather than maintain
  two contradictory representations.
- The level of collaboration: reviewed Git PRs first, concurrent multi-user
  editing and permissions only when demanded by a real workflow.
- Whether the first UI exposes an advanced JSON editor before all bespoke
  forms are ready, to preserve format parity without overbuilding controls.
