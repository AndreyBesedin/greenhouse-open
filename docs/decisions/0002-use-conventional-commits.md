# 0002: Use Conventional Commits

**Status:** Accepted
**Date:** 2026-10-03

## Context

Commit summaries were plain imperative sentences. With a long series of small
commits ahead across three packages, a viewer and CI, it should be possible to
see at a glance what kind of change a commit is, which package or area it
touches, and whether it breaks a public interface.

## Decision

Commit messages and pull request titles follow
[Conventional Commits 1.0](https://www.conventionalcommits.org/en/v1.0.0/):
`<type>(<scope>): <summary>`, with `!` and a `BREAKING CHANGE:` footer for
changes that break a package's public interface. The types, scopes and
writing rules are in
[docs/engineering.md](../engineering.md#commit-messages), added in
[#3](https://github.com/AndreyBesedin/greenhouse-open/pull/3). Earlier
history is not rewritten.

## Consequences

- History can be filtered by type and scope, and breaking changes stand out,
  which matters most for `greenhouse_protocol`.
- The convention is enforced by review only. A commit-message check can be
  added to CI if drift appears.
- A changelog could later be generated from the history, though
  `CHANGELOG.md` is written by hand for now.
