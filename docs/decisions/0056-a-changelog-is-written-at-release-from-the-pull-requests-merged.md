# 0056: A changelog is written at release, from the pull requests merged

**Status:** Accepted
**Date:** 2026-10-24

## Context

Every pull request that changed something a user would notice added its
entry under `CHANGELOG.md`'s Unreleased section (decision 0045). Each
entry went at the top of that one section, so any two such pull requests
open at once conflicted there, and so did each pull request with every
other that merged before it. Merging main back into a branch to resolve
the changelog was the most frequent conflict in the repository; a stack
of pull requests repeated it at every level. The conflicts were also where
entries went wrong: 0.2.0 and 0.3.0 lacked entries for merged work, and a
resolution dropped one of 0.3.0's (decision 0045). Releases already
reconcile the changelog with the pull requests merged since the last tag,
because the entries written along the way could not be trusted to be
complete.

Commit history alone would not do instead. Its merge commits, merges of
main into branches and fixes to reviews are not changes a user notices.
What a release says, such as which run identities change and what format
is still read, needs a sentence someone wrote, not a commit subject.
Decision 0002 left the changelog written by hand "for now".

## Decision

- **No pull request edits `CHANGELOG.md`,** except a release's.
- **A pull request's description gives its entry** under `## Changelog`,
  in the template. The entry is a few sentences for a user of the packages
  or the viewer: what changed and what breaks, with what is still read,
  naming the package first. A change no user would notice says `none`:
  CI, documents or tests alone. A bot's pull request, Dependabot's, gives
  none. A CI check, beside the risk gate, fails a description that gives
  neither an entry nor `none`, and editing the description runs it again.
- **A release writes the version's entries** from the pull requests merged
  since the last tag. `uv run release prepare` collects each one's entry,
  in the order they were merged, each item ending with its pull request's
  number. It waits, refusing, while one gives neither an entry nor `none`:
  that description is given one, and `prepare` runs again. The release
  pull request opens the section with its paragraph, and the owner reviews
  the whole section there, as before. `uv run release changes` prints what
  the next release would take, at any time.
- **Moving over:** the entries already written under Unreleased are the
  next release's first. A pull request whose own diff edited the changelog
  has its entry there. One merged before this decision with neither gives
  its entry, or `none`, at that release, as any other.

The changelog stays the published record. Its version sections are the
GitHub releases' notes, word for word, and a tag is still refused while
entries are left under Unreleased (decision 0045).

## Consequences

- Pull requests no longer conflict over the changelog.
- An entry is reviewed twice: with its pull request, in its description,
  and with the release, in the section.
- A pull request that forgets its entry fails its check. One merged without
  it, before the check, holds up the next release until its description
  gives one.
- The Unreleased section stays empty between releases. What `main` holds
  since the last one is `uv run release changes`.
- This supersedes decision 0045's Unreleased entries written by each pull
  request, and settles decision 0002's "written by hand for now": each
  entry is still written by hand, in its pull request.
