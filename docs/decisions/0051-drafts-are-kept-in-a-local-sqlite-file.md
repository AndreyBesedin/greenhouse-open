# 0051: Drafts are kept in a local SQLite file

**Status:** Accepted
**Date:** 2026-10-23

## Context

The setup builder (P12) keeps a draft at every step, runnable or not, with
its revisions: a person saves, reopens an earlier revision, and goes back
to it. P12 left open where: in a local SQLite file, or as files beside the
packaged scenarios. Either keeps the same document and revision contract.

The editor will run in a browser, against the simulator's API. Two of its
windows can have the same draft open, and the API answers each request on
a thread of its own, so two saves can meet. A save must be kept whole or
not at all, and one made on a revision that is no longer the latest must
not quietly replace what the other window saved.

Files beside the packaged scenarios would put unfinished houses in the
repository's working tree, where a packaged scenario is a reviewed file
(decision 0031), and would need a lock and a rename per save to be whole.

## Decision

- **One SQLite file holds every draft and revision** (`builder.drafts.DraftStore`),
  made with its folder where it is asked for. Python's standard library
  reads it, and it adds no dependency.
- **A revision is its installation's file** (`builder.portable`): the text
  an export writes, read back as an import reads it. A revision saved in
  an older format is read as such a file is, so the store needs no
  migration of its own when the manifests' format changes. Only its own
  table has a version, in the file's `user_version`, and a file in another
  is refused.
- **A draft is named by its installation's identifier**, and its revisions
  are numbered from 1. Reverting saves an earlier revision again as the
  latest, so nothing saved is lost but by deleting the draft.
- **A change names the revision it was made on.** A save, revert or delete
  on a revision that is no longer the latest, or a new draft under an
  identifier already kept, is refused. Each change reads and writes in one
  transaction that holds the file's write lock from its start, so of two
  changes on the same revision one is kept and the other refused.
- **Publishing stays a reviewed pull request** (P12.6): the store is never
  where a packaged scenario comes from.

## Consequences

- Drafts live on the machine that serves the API, in the file it is given,
  and are backed up or moved by copying it. They are not shared between
  people.
- Revisions are kept until their draft is deleted; nothing prunes them.
- The installation's file is the one format to migrate: a change to it is
  made once, for exports, imports and the store together.
- Worth revisiting if drafts must be shared between people or machines: a
  server's database would then keep the same documents and revisions.
