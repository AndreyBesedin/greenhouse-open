---
name: release
description: Make a release of greenhouse-open end to end - check who may release, choose the version, bring the changelog up to what was merged, prepare the release branch (versions, protocol range, dated changelog, lock), open the release pull request, record and cut the demo video, get it uploaded and into the README, hand the pull request to the owner to merge, tag the merge as the owner, and confirm that CI published it. Use this whenever the user asks to release, cut, ship, tag or publish a version ("release 0.4.0", "let's do a release", "bump the version"), to prepare a release pull request, or to record or update the README's demo video for a release.
---

# Make a release

A release is a pull request that the repository's owner merges. The owner
then tags its merge commit, and CI publishes the tag as a GitHub release
(decision 0045). The deliverable is that pull request, complete and green,
with its demo video in the README. After the owner's merge, it is the tag,
pushed through `uv run release tag`, and the GitHub release that the
workflow made, checked and reported. The commands are in
`references/commands.md`.

Never push to `main`, merge the release pull request, or tick its
manual-review box. Never make a tag except with `uv run release tag`, and
never run `gh release create`. `main` takes only merged pull requests. The
merge, the tick and the tag are the owner's: the tag ruleset lets no one
else make a tag, and the command checks the release before it tags. The
GitHub release is the workflow's. Doing any of them by hand skips the
review that a release is for.

## 1. Who may release

Read the GitHub login that `gh` acts as, the repository's owner, and
`.github/release-managers` as it is on `origin/main`. Go on only if the
login is the owner's or is listed there. Otherwise stop, and say who may
release: a login is added to the list by a pull request that the owner
merges. The release's check refuses a pull request opened by anyone else,
whatever this step finds, so a pull request made anyway is wasted.

## 2. Is `main` ready

- Work in a new worktree from `origin/main`, beside the checkout
  (`../greenhouse-open-release-<version>`), never in the user's own
  checkout, which may be on a tag on purpose.
- CI's latest run on `main` passed. A release from a red `main` is not made.
- There is something to release: commits since the last tag, and entries
  under the changelog's `## Unreleased`.
- List the open pull requests. Ask the user which, if any, must land
  first; Dependabot's never hold a release.

## 3. The version

The packages share one version (`CHANGELOG.md`, the paragraph at its top).
Below 1.0:

- **minor** (0.4.0 after 0.3.x) when anything is added or breaks: a feature,
  a changed record or interface, a run's identity or a file format moved;
- **patch** (0.3.1) only for fixes that change no interface.

From 1.0 on, semantic versioning as the changelog says: a major version when
the conformance checks break. Propose the version with the entries that
decide it. The user confirms unless they named one.

## 4. The changelog against what merged

The changelog's section becomes the GitHub release's notes, word for word.
0.2.0 and 0.3.0 both lacked entries for merged work, and a merge that
resolved a conflict in the changelog dropped one of 0.3.0's. So:

- List the pull requests merged since the last tag, and match each to an
  entry. A change a user of the packages or the viewer would notice needs
  one: a feature, a fix, a changed interface, format or default. Changes to
  CI, documents and tests alone, and Dependabot's updates, need none.
- When an entry is missing, compare `main` with that pull request's merge,
  to tell an entry never written from one a later merge dropped.
- Remove duplicates, and keep each entry's pull request or issue number.
- Open the section with a paragraph saying what the version holds, and
  what breaks: run identities, formats, interfaces, with what is still read.
  0.3.0's paragraph is the model.

Every word is a public record (decision 0044). Say what the release holds
and what it changes, never anyone's plans, events or deadlines.

## 5. The release branch and its pull request

- The worktree's branch is `build/release-<version>`, from `origin/main`.
  Run `uv run setup` there once: the video needs the viewer's packages.
- `uv run release prepare <version>`. It moves the three packages and the
  protocol's range, puts the Unreleased entries under `## <version> -
  <today>` beneath an empty `## Unreleased`, and locks. `uv.lock` should
  move the three versions and nothing else: read its diff.
- Write the changelog work of step 4 into the new section.
- The roadmap: mark Done only the steps that the merged work completes,
  in `docs/roadmap/README.md` and in the project's own document.
- The walk-through, `greenhouse_sim/web/e2e/demo.spec.ts`: when the release
  adds something a viewer can see, add a step that shows it, as 0.3.0 did
  for heating targets, with its caption. Run it as a browser test before
  recording.
- Run the checks that `AGENTS.md` asks for. `uv run check --fast` always
  runs. When the walk-through changed, also run `uv run viewer-checks` and
  the walk-through as a browser test.
- Commit with the title `build: release <version>`, signed off, with the
  session's attribution trailer. The body says what moved and why: the
  versions, the range, the changelog's corrections, the roadmap.
- Push, and open the pull request with that title. Fill in the template
  (`.github/pull_request_template.md`): what changed, the result
  (`importlib.metadata.version` and the viewer's build line say the
  version), the verification with test counts. Leave "I manually reviewed
  the complete diff" for the owner.

## 6. The demo video

Record it from the release branch, after the version commit, so that the
viewer's build line in the video names the version.

1. `uv run record-demo` plays the walk-through in Chromium on the
   graphics card, with a caption on each step. It needs ffmpeg and takes
   about three minutes. It prints three paths: the recording, the video cut
   for the README (`greenhouse-open-<version>.mp4`), and the video's first
   frame as a PNG.
2. **Look at the first frame** (Read the PNG). It is the README's preview,
   and it must show the whole house with its crop, as the caption "1. Opened
   on day 86, its first day with red fruit" introduces it. The info panel
   should name day 86 and its entities (12912 in 0.3.0), and the panels
   should be filled in. A blank page, a loading message, or the house
   without plants, with "before day one" in the info panel, means the cut
   came too early. Do not
   upload it. Find what the opening shot did not wait for (the mark is
   written in `demo.spec.ts` once the view is drawn), fix that, and record
   again.
3. Look at a few frames through the video as well (the command is in
   `references/commands.md`). Each caption should sit on the view it names.
4. The command refuses a video over 10 MB, the most GitHub takes as an
   upload.
5. **The upload is the user's.** GitHub plays a video in a README only when
   it hosts it at `github.com/user-attachments`, and it offers no API for
   that. Ask the user to drag the MP4, by its full path, into a comment on
   the release pull request and post it. Stop the turn and wait for them.
6. Read the URL from the comment that the owner or a release manager
   posted. Download it and compare its SHA-256 with the local file's, to
   check it is this recording. If they differ, ask the user which upload
   is meant; never guess.
7. `uv run release video <url>` points the README's demo at it and sets the
   caption's version. Commit `docs(readme): the demo video recorded from
   <version>`, signed off, and push it to the release branch.

Without a machine that can record, leave the README as it is: its caption
keeps the earlier video's version, which is still true. Say so in the pull
request.

## 7. Hand it to the owner

- Watch the checks (`gh pr checks <n> --watch`), and report their state
  once they finish. The risk gate holds a release pull request until the
  owner ticks the manual review: it changes package metadata.
- If you pushed after the owner ticked the box, untick it. The diff they
  reviewed is no longer the diff, and the first line of your report says
  that you unticked it.
- Tell the owner what is left: read the diff, tick, and merge with a merge
  commit, then the tag (step 8).

## 8. After the merge

- **The tag.** When `gh` acts as the owner, fetch, check out the merge
  commit (detached) in the worktree, and run `uv run release tag <n>`. It
  checks the release and pushes `v<version>`, annotated. When `gh` acts as
  a release manager, ask the owner to run that command, and give it to
  them with the pull request's number.
- If `tag` refuses, it says why. A refusal, such as a range left behind or
  entries left under Unreleased, is fixed by a pull request from a branch
  of the same name, `build/release-<version>`, which the owner merges and
  tags in turn.
- **The release.** The tag's push runs the `Release` workflow. Watch it,
  then check that the GitHub release is the latest, on `v<version>`, with
  the changelog's section as its notes. If the run failed, its log says
  why. Only a failure on GitHub's side is run again. If the workflow
  itself is broken, tell the owner: a release published by hand is theirs
  to ask for.
- Report: the tag, the release's URL, the video's URL, and anything left.
  Then remove the worktree and its local branch.
