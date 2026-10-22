# P12: Greenhouse Setup Builder

**Status:** Foundation in progress

## Purpose

Author and revise an installation in the browser, starting from an empty
greenhouse or copying a repository template. A person should be able to edit
every supported declarative greenhouse property without editing Python or
JSON, preview the scene, receive actionable validation feedback, save an
unfinished version, and eventually start a simulation from a published
revision. Keep the headless simulator independent of the editor.

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
   YAML can be an optional view/import-export format, not another canonical
   model. Code-backed plant models are referenced, never embedded or
   executed as uploaded source in the browser/API.
4. **Drafts vs publication.** A local SQLite store will hold editable drafts
   and revisions as validated JSON documents plus metadata, not a
   hand-normalized copy of every nested model field. Export is a portable
   installation bundle with pinned model references; promotion to the shared
   open-source catalogue is a reviewed Git pull request. Repository files
   remain the authority for published templates and models. No live Git
   write is part of a simulator step.
5. **Readiness is graduated.** Invalid values are refused by Pydantic;
   cross-object violations prevent running or publishing but can be
   preserved as drafts. Absence of doors, heating, roof vents or fans raises
   warnings, not hard errors. A greenhouse research case need not have the
   equipment of a commercial production facility.
6. **Performance and compatibility.** The current packaged scenarios,
   URL semantics, seeds, snapshots, checkpoints, and consumer replay stay
   unchanged. The editor is an optional mode. Preview uses the existing
   scene generator, not a second mesh renderer.

## Proposed user flow

1. **Choose a starting point:** empty greenhouse, or clone a published
   template. Cloning records its source revision; the original remains
   immutable.
2. **Basic structure form:** name; greenhouse length and width; roof
   eave/ridge height; spans and structural bays; number of crop rows;
   plants per row, pitch, row spacing and support height. Clearly
   distinguish *roof spans*, *crop rows* and *service lanes*. For now the
   footprint is rectangular with pitched multi-span roofs.
3. **Planting:** each row gets exactly one plant-model revision and variety.
   Different rows may make different choices in a draft. The editor must
   clearly report that the runtime currently supports only one model and
   variety per scenario. Parameter variants of an existing model become
   possible before brand-new biological implementations.
4. **Preview and edit:** reuse the existing 3D scene; select an envelope
   surface, row, fixture or piece of equipment to edit its fields. Add
   roof vents and doors to surfaces; add fans, heaters, dehumidifiers,
   sensors, walkways, zones and fixtures through category palettes.
   Explicitly position items in the greenhouse's metre, right-handed,
   z-up coordinate system. Show coverage and geometry violations inline.
5. **Validate, save and simulate:** save unfinished drafts at any step.
   Present errors and warnings with a link to the item and property. Only
   a fully resolved, supported scenario may start a run. A revision
   selected by a run does not change if someone edits the draft.
6. **Publish/share:** export/install a portable bundle locally, or propose
   a reviewed Git PR containing its declaration and pinned model assets.
   Track source, author-supplied modelling assumptions, versions and
   research citations.

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
| **12.0 Authoring foundation** | Typed installation draft reusing `Envelope`/`Layout`, basic structure generator, row references, geometry/readiness findings | JSON round-trip, representative valid and invalid inputs, no changes to packaged scenarios |
| **12.1 Runtime resolution and storage** | Separate installation/scenario/run identity, a resolver into the existing `ScenarioConfig`, local SQLite draft revisions and immutable run snapshots; schema publication | Save, reopen, edit and revert; launch supported homogeneous draft; existing scenarios and replay identical |
| **12.2 Structure wizard and viewer** | Route for Setup Builder, blank/template launch, form, scene preview, editable row properties and advanced schema fields | End-to-end create/preview/save/reopen; no regression in viewer screenshot QA |
| **12.3 Equipment and opening editor** | Reusable typed catalogue, surface-mounted doors/vents, climate units, sensors, fixtures, move/rotate with property inspector | Geometry/identifier conflicts explained and repairable; existing layout fields editable |
| **12.4 Plant-model assets** | Model registry, schema-driven parameter forms, forked drafts, versioned parameter assets and citations | Edit a tomato parameter set, save, compare, export and reproduce the same run using a pinned version |
| **12.5 Row-specific runtime support** | Generalize current `CropRows` and `ScenarioConfig` limitations, crop model contract and scene/checkpoint/log handling | Different models/varieties per row reproducibly simulated, or explicitly refused for unsupported combinations |
| **12.6 Publication and completeness** | Export/import bundle, reviewed Git publishing, templates, parity checklist between JSON schemas and UI | Re-import produces equal models and scene; every supported declarative field is reachable via the UI or advanced editor |

### Gate 12.0 scope and limitations

The first additive backend slice defines `builder.InstallationDraft` and
`basic_installation`. It generates the rectangular pitched greenhouse and
homogeneous row geometry, records a crop reference for each row, and reports
missing doors, vents and heating as warnings. It does **not** persist drafts,
resolve crop model IDs, publish schemas, instantiate arbitrary per-row crop
models or run them. A draft can be round-tripped without modifying any
existing scenario files. Full compatibility with `ScenarioConfig` is the
explicit next gate.

## Test and review expectations

- Unit tests: invalid dimensions, roof below eaves, overlapping or
  out-of-envelope fixtures, duplicate identifiers, missing crop assignments,
  missing optional equipment and schema round-trip.
- Integration tests: drafts to `ScenarioConfig`, stable run digests, seed
  determinism, migrations of persisted versions and model reference failures.
- Viewer tests: keyboard forms, selected geometry, undo/redo, unfinished
  drafts, validation messages, and advanced-property parity.
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
