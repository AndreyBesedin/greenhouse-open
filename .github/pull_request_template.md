## What changed?

<!-- Keep this focused on one concern. Say what changed and why, for any
reader of the project: no one contributor's plans, events, deadlines,
commercial needs or requests (docs/engineering.md, "What a public record
says"). -->

## Observable / testable result

<!-- What can a reviewer run, inspect, measure, or see? -->

## Changelog

<!-- The entry the next release's notes take (decision 0056), for a user of
the packages or the viewer: what changed and, if anything breaks (a run's
identity, a format, an interface, a default), what, with what is still read.
Name the package first, such as `greenhouse-sim`: or viewer:, in a few
sentences, or a short list if it is several. Write none for a change no user
would notice: CI, documents or tests alone. Do not edit CHANGELOG.md. -->

## Verification

- [ ] Relevant tests added or updated
- [ ] `uv run check --fast` passes
- [ ] Behavior/documentation changes are described above

## Review

- [ ] Copilot review feedback has been resolved or explicitly acknowledged
- [ ] I manually reviewed the complete diff (required only when the risk gate asks for it)

## Scope check

- [ ] This PR does not contain unrelated cleanup or refactors
