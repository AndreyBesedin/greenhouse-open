# 0031: Scenarios are versioned JSON manifests

**Status:** Accepted
**Date:** 2026-10-12

## Context

A scenario was a `ScenarioConfig` built in a Python module, with its
layouts in JSON files beside it (decision 0020). P09 asks for a reference
scenario that is data-driven and versioned, and its review asked for one
format for every scenario rather than a file for the new one and code for
the others.

## Decision

- Every scenario is a manifest, `scenarios/manifests/<scenario id>.json`
  in the package: a `ScenarioConfig` as Pydantic writes it, with its
  layout named, not written out, since layouts are files of their own.
  The registry lists the manifests, the first scenario first and the
  others by identifier.
- A manifest states `schema_version`, the version of the format it is
  written in. A reader refuses a manifest in a format it does not read,
  rather than guessing at it. A change that an older manifest could not be
  read under raises the version.
- A manifest names its schema, `scenarios/scenario.schema.json`, generated
  from the configuration and kept current by a test, as the layouts' is.
- The simulator checks a manifest when it reads it: it must describe the
  scenario it is named after, fit its greenhouse as any configuration
  must, and have no field the configuration does not, at any depth. Some
  nested models ignore a field they do not know; the reader does not.
- A manifest may carry notes, by what each is about: the scenario as a
  whole or one of its fields. They take the place of the comments the
  scenarios' modules had, which JSON cannot hold.

## Consequences

- A new scenario is a new file, with no code change, as a new layout is.
- The scenarios' constants, which their modules computed (a vent for each
  span, a door's height from its width), are written out in full.
- A configuration's default that changes changes every manifest that does
  not set the field. The manifests hold what each scenario sets, not every
  value it runs with.
- Decision 0020's comments in each scenario's module are now the notes in
  each manifest.
