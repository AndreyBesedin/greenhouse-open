# 0045: A release is a pull request the owner merges, and CI tags it

**Status:** Accepted
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

Anyone with write access could also tag a commit as a release.

## Decision

- **A release is a pull request** from a `build/release-<version>`
  branch, titled `build: release <version>`. `uv run release prepare
  <version>` makes its changes: the three packages at the version, the
  simulator's and the adapters' range of the protocol from the version up
  to the next one that may break it, the changelog's Unreleased entries
  under the version and its date, and the lock.
- **The repository's owner, or a release manager** listed in
  `.github/release-managers`, opens it. The workflow reads the list as it
  stood before the pull request, so that a pull request cannot add its own
  author. **The owner merges it.**
- **CI tags it.** When the owner merges a release pull request,
  `.github/workflows/release.yml` checks it (`scripts/release.py verify`),
  tags its merge commit `v<version>`, annotated, and publishes the GitHub
  release with the changelog's section as its notes, once nothing is left
  under Unreleased. A release pull request merged by anyone else, opened by
  anyone else, or failing the check is merged but not released, and the
  workflow's run says why. Each step skips what an earlier run did, so a run
  is run again as it is.
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
  tag, its GitHub release and its notes follow from the merge, so they
  cannot drift from what was merged.
- The tags are made by `github-actions[bot]` rather than by the owner.
- Someone with write access can still push a `v*` tag by hand. A tag
  ruleset that lets only the owner create one would close that, and is the
  owner's to turn on.
- A release that fails the check after its merge is fixed by another pull
  request from the same branch name, or, when the failure was GitHub's, by
  re-running the workflow's run.
- Recording needs a machine with a graphics card and ffmpeg. A release
  made without one keeps the earlier video, and its caption keeps that
  video's version.
- Worth revisiting when the packages are published to PyPI: the workflow
  would build and upload them, and the notes' first line would change.
