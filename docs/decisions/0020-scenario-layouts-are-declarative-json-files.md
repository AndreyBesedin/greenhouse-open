# 0020: Scenario layouts are declarative JSON files

**Status:** Accepted
**Date:** 2026-10-06

## Context

P02 gives every scenario a layout: crop rows, their supports, rails and
wires, walkways, zones and placed fixtures (decision 0019). Written as
Python, a layout can only be changed by changing code, and a second layout
for the same greenhouse means a second scenario. P02.6 asks for layouts that
can be swapped without code changes, with stable identifiers, as a step
towards editing a greenhouse in the viewer.

## Decision

- A scenario's layouts are JSON files, `scenarios/layouts/<scenario
  id>/<name>.json` in the package, each a `Layout` as Pydantic writes it.
  `default.json` is the layout the scenario is defined with; any other file
  is an alternative for the same greenhouse.
- JSON, because the model reads and writes it with no new dependency, and a
  JSON Schema can be published for it. Each file names the schema,
  `scenarios/layout.schema.json`, generated from the model and kept current
  by a test, so an editor can check a file while it is written.
- The simulator checks a file when it reads it, as any layout is checked: it
  must fit its greenhouse and its crop, and a field the model does not have
  is refused rather than ignored, so a typo is an error.
- Identifiers come from the file (fixtures, zones) or from the rows they are
  generated from (`row_<r>_position_<p>`), so a layout read back from the
  file it was written to has the same entities with the same identifiers.
- The local API lists each scenario's layouts, shows a scenario with another
  of them (`?layout=<name>`), and writes a layout as its file holds it
  (`GET /api/scenarios/{id}/layout`). A layout's name is lower case letters,
  digits and underscores, so it cannot reach outside its folder.

## Consequences

- A new layout for a scenario is a new file, with no code change; the viewer
  offers it beside the scenario.
- Layouts are package data: a change to a file is a change to the package,
  reviewed and tested like code.
- Comments cannot live in JSON. Each scenario's module says in a comment what
  its default layout holds.
- An editor in the viewer (P01's "Later") can send a layout in this same
  shape to the API, which checks it as it checks a file.
