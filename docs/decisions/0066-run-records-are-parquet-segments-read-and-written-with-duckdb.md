# 0066: Run records are Parquet segments, read and written with DuckDB

**Status:** Accepted
**Date:** 2026-10-31

## Context

Decision 0065 keeps a run in a store as segments of records, checkpoints of
models' states, an intervention log and commits. [P17.1](../roadmap/p17-runs-and-playbacks.md)
measured what they weigh and how they are read, on the reference greenhouse
and on `tomgro_house`, and at 32, 128 and 512 plants.

- **Records are tabular.** A day's 3,888 observations are 1.53 MB of JSON and
  49.2 kB as gzip JSON, read by parsing the whole day: 57 ms to select one
  type. As zstd Parquet the same day is 24.8 kB, and selecting one type takes
  1.2 ms. Parquet with snappy was 56 kB, with gzip 30.9 kB.
- **A DuckDB file held for writing cannot be read elsewhere.** While one
  process holds it, no other process opens it, read-only included (`Could not
  set lock on file`), so a viewer could not follow an epoch that a worker is
  computing. This is DuckDB's rule; SQLite in WAL mode lets readers work beside
  a writer, and a small index beside Parquet payloads is possible. The test
  settles nothing about them.
- **Checkpoints are not tabular in general.** A crop grown by plant keeps
  organs for each plant: about 4.6 kB of JSON a plant at day 1, about 65 kB by
  day 120, so 10,000 plants are about 650 MB of JSON in one checkpoint. A crop
  grown by area keeps scopes and steps, and is small whatever the plant count
  (decision 0062).
- **Analysis reads many runs.** Evaluating policies and comparing seeds ask
  for a quantity across epochs.

## Decision

- **A segment's records are Parquet files,** zstd-compressed, one file for
  each log (observations, events, outcomes), immutable once written and named
  in a commit. A consumer's cursor is a position in the epoch's log,
  counted across its segments in order.
- **DuckDB reads and writes them,** and answers queries across segments and
  runs (`read_parquet` over a glob). It is a runtime dependency of
  `greenhouse_sim`, added by the pull request that first needs it (P17.3).
  DuckDB writes Parquet itself, so no other Parquet library is added.
- **The store is immutable objects and a commit written last** (decision
  0065), the same layout for a folder and an object store. That is an
  architectural choice, made for those two backends and for readers that need
  no lock, not a finding that no database file could serve. A database kept
  beside the objects, for an index or a catalogue, is not excluded; it would
  be rebuildable from them.
- **A checkpoint is an opaque object with a content type.** Its model
  serializes it. JSON compressed with zstd is the default; a model that keeps
  a large population declares a columnar or array format for it. The store
  keeps the bytes and the type, and assumes nothing of either.
- **The manifest, the commits and the intervention log are small JSON** (the
  log as JSON Lines): readable, diffable, written whole.
- **The list of runs is derived** from the manifests, never written by
  workers to a shared database. An index that makes it quick may be kept and
  rebuilt.

## Consequences

- **A dependency is added** (DuckDB, MIT-licensed, a Python wheel; 2.0.0 installs
  on Python 3.14 on macOS arm64, where this was tested). The pull request that adds it
  checks the wheels CI and the lowest-dependencies lane install, adds its
  licence to `NOTICE` if the repository's rule requires it, and pins it in
  `uv.lock`.
- **Records halve in size and are quick to select;** the consumer interface
  reads a segment's rows by position without parsing a day.
- **The records now written as gzip JSON by `Playback` move to Parquet** in
  P17.3; a stored epoch's format is named in its manifest, so a later one can
  change.
- **Worth revisiting** if DuckDB has no wheel for a platform the project
  supports, when `pyarrow` writes the same files; or if the Parquet files'
  number makes listing slow, when segments are merged.
