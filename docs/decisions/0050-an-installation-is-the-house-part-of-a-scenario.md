# 0050: An installation is the house part of a scenario

**Status:** Accepted
**Date:** 2026-10-23

## Context

A greenhouse is authored before it is simulated (P12): its walls and roof,
what stands inside it, and which crop each row grows. A scenario's manifest
(decision 0031) already holds all of that, beside what a run needs
besides: the weather, the period, the controller, the seed and the models'
settings.

A first draft of the setup builder wrote an installation as a second file
format with its own versions, one inside the document and one outside. A
manifest and an installation would then describe the same house twice,
under two version numbers and two sets of migrations, and the step that
turns an installation into a scenario would have translated between them.
It also named crops by free strings ("tomato.simple") rather than by the
crop models the simulator runs.

## Decision

- **An installation is the house part of a scenario's manifest:** its
  envelope, its layout and the crop each row grows (`builder.InstallationDraft`).
  Weather, period, control, seed and model settings are a scenario's, and
  stay out of it.
- **One format, one version.** An installation's file holds those fields
  as a manifest writes them, the layout written out rather than named, and
  the manifests' format version (`manifest_files.SCHEMA_VERSION`). A change
  to the house part of the manifests' format changes the installation's
  file with it, by the same migration. The file may name its JSON Schema,
  `builder/installation.schema.json`, published with the others (W12), and
  is refused if it has a field a draft does not.
- **A crop is named by the simulator's own crop model** (`CropModel`) and a
  variety, for each row.
- **A draft keeps what cannot run yet.** Values no greenhouse can have are
  refused as the models refuse them. What only the parts together get
  wrong (an item through a wall, a row without a crop, rows of different
  crops a run cannot grow) is a finding, naming the items and rows it
  concerns, and absent doors, vents, heaters or fans are warnings.
- **The manifest takes the installation in next** (P12.1): a manifest
  holds, or names, an installation in place of its own envelope, layout and
  crop fields, by a manifest migration. That step waits for a simulator
  able to register a scenario at runtime (decision 0048's series), and the
  installation's model moves into `scenarios` then, so that the builder
  imports it and `scenarios` never imports the builder.

## Consequences

- A packaged scenario's house reads as an installation unchanged, and an
  installation becomes a scenario by adding a scenario's own fields, with no
  translation between formats.
- Until P12.1, a manifest still writes its house fields itself. They are
  written from the models a draft is made of, so the two cannot differ in
  shape. A new manifest format that changes the house part must also
  migrate installation files: until it does, the reader refuses a file in
  any version but the current one.
- Rows growing different crops can be drafted but not run: a run grows one
  model and one variety (`ScenarioConfig`). Running them is P12.5.
- Worth revisiting if an installation must outlive the manifests' format,
  for example as an exchange format between simulators: it would then need
  versions of its own.
