# 0034: Approve Dependabot's pull requests to acknowledge their review

**Status:** Accepted
**Date:** 2026-10-14

## Context

The pull request risk gate holds a higher-risk change until its author
acknowledges reviewing the complete diff, by ticking an item of the pull
request template in the description. The repository has one developer, who
cannot approve their own pull requests, so the tick stands in for an
approval.

Dependabot's pull requests (decision 0033) have no template: their
description is the bot's, with no item to tick. Decision 0033 had the line
added to it by hand, and a description that Dependabot rewrites, when it
moves the pull request to a newer release, loses it. But a Dependabot pull
request is not the maintainer's own, so the maintainer can approve it,
which is how GitHub records that a pull request was reviewed.

## Decision

- **On a Dependabot pull request, a maintainer's approval of its latest
  commit is the acknowledgement.** A maintainer is the repository's owner,
  its organisation's members and its collaborators (the review's
  `author_association`), not any GitHub user. An approval of an earlier
  commit does not cover a later push; a later request for changes, or the
  approval's dismissal, withdraws it; a comment changes nothing.
- **A review runs the gate again:** `pr-risk.yml` runs on
  `pull_request_review` too, reads the pull request's reviews with its
  token (`pull-requests: read`), and `scripts/check_pr_risk.py` decides.
- **Anyone else's pull request keeps the tick,** the maintainer's own
  among them. The tick still acknowledges a Dependabot pull request too.
- The workflow's token is declared read-only (`contents: read`,
  `pull-requests: read`).

## Consequences

- Reviewing a held update is approving it. An update whose auto-merge is
  on (decision 0033), held by the gate alone, merges once approved; one
  that waits for a review, a major or a minor update below 1.0, is merged
  by hand after the approval.
- When Dependabot rebases or updates a pull request, its approval no
  longer covers the latest commit, and the gate asks for another.
- The gate stays a deliberate step of the author's, not a security
  boundary: it runs the pull request's own version of the script, as it
  did.
- Worth revisiting when a second maintainer arrives: their approval of
  anyone's pull request could then acknowledge it, and the ruleset could
  require one.
