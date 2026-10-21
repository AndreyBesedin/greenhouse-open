# 0044: Public records speak for the project

**Status:** Accepted
**Date:** 2026-10-21

## Context

Decision 0001 keeps product plans, business strategy, customer information
and private systems out of the repository's documents. Commit messages,
pull request descriptions, issues, review replies, the changelog and
release notes are public records too, and they had drifted the other way:
some described work as done for one contributor, timed to that
contributor's events and deadlines, or as the answer to their requests.

This is an open project. Whatever a contributor builds on it, the project
is not built for any one of them, and its history should not read as if
it were. A record written for whoever asked for a change also ages
badly: the person, the event and the deadline mean nothing to the next
reader, while what changed, why and how it was checked still do.

## Decision

Every public record of the project describes the change for any reader of
the project:

- **what** changed, and **why**: the problem in the code, or the project's
  goal it serves;
- the **result**, and **how it was evaluated**: the tests, the measurements,
  the QA it passed;
- what **limits** it or is left: bottlenecks, known gaps, follow-ups.

It leaves out any particular person's or organisation's plans, events,
deadlines, commercial needs and requests. A choice the maintainer made is
recorded as the project's decision, with its reasons, in the record or in
a decision record, not as someone's wish. A use case is named generically,
as downstream applications are ("a consumer following a run beside the
viewer"). Dates and versions stay as facts (when something landed, what a
release holds), never as someone's deadline.

The records this covers: commit messages, pull request titles and
descriptions, issues, review comments and replies, the changelog, release
notes and tags, as well as the documents decision 0001 already covers.

## Consequences

- The history explains itself to anyone, as decision 0001 meant the
  documents to.
- Writing takes a moment's translation when work is prompted by one
  contributor's need: the record states the need in the project's terms,
  or not at all.
- Records written before this decision are not rewritten.
- `docs/engineering.md` states the rule for contributors, `AGENTS.md` for
  coding agents and reviewers, and the pull request template reminds the
  author.
