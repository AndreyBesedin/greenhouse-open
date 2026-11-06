# 0070: A finished project moves to the roadmap's archive

**Status:** Accepted
**Date:** 2026-11-06

## Context

`docs/roadmap/` holds one document per project (decision 0001), and every
project's document stays there once it is done. By 2026-11-06 the folder held
124,309 words, 65,341 of them in the documents of projects marked Done (P-1,
P00 to P10, P15, P16), and more in clean-ups and audits of the frontend whose
work is finished. A person or a coding agent looking for what is open searches
all of it, and a finished project's "not yet" reads as if it were still open.

The rules stood in the way of moving them: an accepted decision is not edited
apart from its status line, and an audit is not rewritten once its work
begins. Decisions 0046, 0054, 0055, 0058, 0059, 0064 and the audit of
2026-10-13 link to projects' documents by relative path, so a moved document
would leave those links broken, or the project would have to stay where it
is.

The options weighed:

- **Leave every document in place:** nothing breaks, nothing is gained.
- **Move only what no frozen record links to:** P09, P11, P13, P14 and P16
  stay, as do the clean-ups beside them, and the line between the two kinds
  of done projects is an accident of which were cited.
- **Move every finished project, and allow a link to follow it:** a link's
  path changes in a frozen record, and none of its words do.

## Decision

- **`docs/roadmap/archive/`** holds the documents of finished projects: a
  project marked done, with its clean-up and its QA reports once their plans
  are done or carried elsewhere, and documents of finished work such as the
  frontend maintenance. They stay in `docs/roadmap/`, as decision 0001 has
  it, and keep their names.
- **A project moves when it closes,** in the pull request that marks it done
  or in one that moves several together. Its row stays in the roadmap's
  index, pointing into the archive, so that its step identifiers are still
  found from there.
- **A link follows what it points to.** When a document moves, every
  relative link to it is updated, in accepted decisions and audits too. That
  is not an edit of the record: only the link's path changes, never its
  words. Nothing else in a frozen record changes with it.
- **The archive is read on demand.** `AGENTS.md` tells a coding agent to open
  an archived document only when a task cites its steps or asks for its
  history; what is open is found outside it.
- **Decisions stay where they are.** About 364 files cite them by number,
  and the index's status column already says which are superseded.
- A test resolves every relative link in the repository's documents
  (`tests/test_publishable.py`), so that a move cannot leave one broken.

## Consequences

- `docs/roadmap/` outside the archive holds what is open, proposed or
  current: the projects in progress, the proposed ones, future work, the
  research priorities and the latest QA.
- A link from outside the repository to a moved document's old path stops
  resolving; a link pinned to a commit keeps working. Earlier commit
  messages and pull requests that cite a path name the old one.
- A pull request that moves a document also edits the links into it, so it
  touches files it would not otherwise: decisions, audits, guides and code
  comments that cite the path.
- Worth revisiting if the archive itself grows large enough to need an index
  of its own, or if projects are reopened often enough that moving them back
  costs more than it saves.
