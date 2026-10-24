# 0045: A release is a pull request the owner merges and tags, and CI publishes it

**Status:** Accepted; the Unreleased entries each pull request wrote superseded by [0056](0056-a-changelog-is-written-at-release-from-the-pull-requests-merged.md)
**Date:** 2026-10-22

## Context

Releases 0.1.0 to 0.3.0 were made by hand: a pull request moving the three
packages' versions and dating the changelog, then a tag, a GitHub release
and a demo video recorded, cut and uploaded for the README. Each step was
a chance to slip, and several did:

- 0.2.0's pull request left the simulator's and the adapters' range of the
  protocol at `>=0.1.0,<0.2`, which excluded the protocol it released.
- Both 0.2.0 and 0.3.0 lacked changelog entries for merged work, and a
  merge that resolved a conflict in the changelog dropped one of 0.3.0's.
- The README's caption named 0.2.0 above 0.3.0's video.
- Playwright records the walk-through from the page's opening, blank until
  the house is drawn, and GitHub shows a README's video by its first frame
  until it plays. Every recording had to be cut by hand, and a cut chosen
  by eye can land on the house before its crop is drawn.

Anyone with write access could also tag a commit as a release, and move
or delete a release's tag.

## Decision

- **A release is a pull request** from a `build/release-<version>`
  branch, titled `build: release <version>`. `uv run release prepare
  <version>` makes its changes: the three packages at the version, the
  simulator's and the adapters' range of the protocol from the version up
  to the next one that may break it, the changelog's Unreleased entries
  under the version and its date, and the lock.
- **The repository's owner, or a release manager** listed in
  `.github/release-managers`, opens it. The check reads the list as it
  stood before the pull request, so that a pull request cannot add its own
  author. **The owner merges it.**
- **The owner tags it.** Once merged, `uv run release tag <pull request>`,
  run by the owner from the merge commit, checks the release
  (`scripts/release.py`). It tags the merge commit `v<version>`, annotated,
  and pushes the tag. The check refuses a pull request merged or tagged by
  anyone else, or opened by anyone else. It also refuses one whose
  packages, protocol range or changelog do not agree with the version, or
  that leaves entries under Unreleased. A tag ruleset, `tags: owner only`,
  lets only the owner's admin role create, move or delete a tag.
- **CI publishes it.** The tag's push runs `.github/workflows/release.yml`,
  which checks the release again, from the merged pull request it finds
  for the tagged commit, and publishes the GitHub release with the
  changelog's section as its notes. A tag that fails the check is not
  published, and the run says why. Publishing skips a release already
  published, so a run is run again as it is.
- **The demo video is recorded from the release's branch** with `uv run
  record-demo`. The walk-through marks when its opening shot is drawn, with
  the house and its crop in view. The command cuts the recording from
  there, at twice the speed, to an MP4 GitHub plays, and saves the first
  frame for checking. GitHub offers no API for an upload that a README
  plays. So the video is uploaded by hand, dragged into a comment on the
  release pull request, and `uv run release video <url>` points the
  README at it in the same pull request.
- The steps, for a person or a coding agent, are the release skill's
  (`.claude/skills/release/SKILL.md`).

## Consequences

- A release is reviewed as its pull request, like every other change. Its
  tag, its GitHub release and its notes follow from what was merged, and
  cannot drift from it.
- The tag is the owner's own act, one command after the merge, and the
  ruleset leaves no one else able to make one. CI could not push it
  instead: on a repository a personal account owns, GitHub Actions cannot
  bypass a ruleset, and a stored deploy key with write access, which
  could, would be a standing credential.
- A release refused after its merge, before its tag, is fixed by another
  pull request from the same branch name, merged and tagged in turn.
- Recording needs a machine with a graphics card and ffmpeg. A release
  made without one keeps the earlier video, and its caption keeps that
  video's version.
- Worth revisiting when the packages are published to PyPI: the workflow
  would build and upload them, and the notes' first line would change.
