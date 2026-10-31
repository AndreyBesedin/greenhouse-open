# 0049: A run started from moves keeps its target changes

**Status:** Accepted; its run no longer served superseded by [0065](0065-a-run-is-a-scenario-at-a-seed-kept-in-a-store-and-played-from-it.md)
**Date:** 2026-10-23

## Context

Decision 0043 made a heating target a run's input at a moment, and let a
playback's run be steered while it plays. A restart of the playback, a new
epoch of the scenario's own run, drops the changes.

Moving equipment changes the house's climate. Moves applied while the view
follows the run played back start the playback over with the layout they
make, from its first day (#271). That went through the same restart, so
the new run also lost the target changes the run had. In the viewer, the
targets went back to the scenario's own, and `&targets=` left the address.
To a platform that had set the targets through the API, they appeared
undone, with nothing on screen saying why
([#305](https://github.com/AndreyBesedin/greenhouse-open/issues/305)).

A run started from moves is the run as it was set up, its equipment
standing elsewhere. A restart without moves asks for the scenario's own
run again.

## Decision

- **A playback started over with another layout keeps the target changes**
  its run had, each at its moment, target and value (`Playback.rearranged`).
  It plays the new layout's run with them from its first day, and its state
  lists them (`PlaybackState.targets`). The run keeps the new layout's
  identity, as a steered run keeps its own (decision 0043).
- **No change acknowledged meanwhile is lost.** The API answers requests on
  threads of their own. A target change, a pace or a command asked of the
  playback being replaced, by a request that found it before the
  replacement took its targets, is handed to the one in its place.
- **A restart with the layout it plays is unchanged.** It is a new epoch of
  the scenario's own run, without the changes (decision 0043).
- **The viewer keeps them too.** Applied, the moves change the run drawn's
  layout and time and keep its `&targets=`, whether or not the view follows
  the run played back.
- **The viewer asks before the moves start the new run** (#305). The question
  sits in the Move panel and says the run starts again from its first day;
  "Back to the moves", or Escape, returns to them.

## Consequences

- Moving equipment in a run whose targets were changed compares the same
  setup, targets and all, with its equipment elsewhere.
- Changes carried into the new run are checked as any run's are. One the
  new layout cannot take refuses the layout, and the playback plays on as
  it was.
- A change set while the old run played lands on the minute after its
  clock. In the new run it holds from that same moment, so the new run
  plays some time under the old targets before reaching it.
