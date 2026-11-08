# 0073: A change in a replay steers a running epoch at its own clock

**Status:** Accepted
**Date:** 2026-11-08

## Context

Decision 0043 has a target changed while a run plays steer it from its clock's
next minute, and the viewer's own play (P13.8) steers a playback through its
plan. Decision 0065 keeps a run's epochs in a store, computed by workers, and
P17.8 gave an epoch a log of the changes made to it, asked through the store
(`POST /api/runs/{run}/epochs/{n}/changes`): the API writes a request, and the
worker, the log's only writer, takes it between its moments, logs it at the
moment of its own clock it takes effect from, and acts on it. An epoch that has
ended takes no change: the route refuses it and points to a fork (P17.8's
settled item 12).

The replay (P17.6) shows a stored epoch at a position, which is the viewer's
place over it and not its clock: a position stands at or before the epoch's
frontier, its last commit, while the worker computes past it. Until now a
target or a level set in a replay's panels was always a fork from the moment
shown, also while the epoch was being computed, so that the only way to steer a
running epoch was the route itself (P17.8, "not delivered"). P22 takes the
viewer's own play away (P22.2, P22.3), and its steering with it, so the replay
must steer.

The questions were which epochs a replay steers rather than forks, at which
moment a change takes, and how the replay learns what became of it.

## Options weighed

- **Steer by the epoch's status, at the epoch's own clock** (chosen). An epoch
  the position says is queued or running is asked for the change, whatever
  moment the replay shows; the change takes from where the worker is, as the
  route already does.
- **Steer only at the frontier, fork before it.** A replay that follows the
  newest day would steer, and one moved back would fork from the moment shown.
  But even at the frontier the worker is past it, by up to a day, so the change
  still does not take at the moment shown, and the same control would steer or
  fork with nothing on the page but the position to tell which.
- **A change at the moment shown, of a running epoch.** The clock of an epoch
  never steps back (decision 0040), and the records past that moment have been
  delivered; changing them is what a fork is.

## Decision

- **A replay steers the epoch it shows while the epoch takes changes:** while
  its position says it is `queued` or `running`, a target or a level set in its
  panels is asked of it through its changes, and nothing forks. Once the
  position says it has ended (`finished`, `failed` or `interrupted`), a change
  is a fork from the moment shown, as before. A layout rearranged is a fork
  either way (P17.8's settled item 11).
- **The simulator's answer decides.** The status the page holds may be a second
  old: an epoch that ended before the change was asked is refused by the route,
  and one that ended before its worker took a request leaves it waiting, never
  taken. Either is said in words, beside the panels, and is not made a fork in
  its place; the next change, the page knowing the epoch has ended, forks.
- **A change takes at the epoch's own clock,** as its worker takes it: a target
  from the next minute, a level from the moment it is taken, as P17.8's route
  gives them. The panels say so before the change is made ("from the run's next
  minute"), and the replay says where the epoch is computing, not the moment it
  shows.
- **The replay reads back what became of it** from the epoch's changes
  (`GET …/changes`), until the worker has logged the request, at the moment it
  takes effect, which the page then names, or refused it, which the page says in
  the worker's words. What the panels show at a moment is the plan the epoch was
  worked out under, read from its position (P17.8), so a change appears there
  once the replay reaches its moment, which a commit past it allows.

## Consequences

- One steering path for the viewer's panels (`plan/useSteering.ts`), given how
  actions reach the run: a playback's plan, or an epoch's changes. The replay
  replaces the viewer's own play as the place a run is steered from, which
  P22.3 needs.
- A person who has moved a running epoch's replay back and wants a change from
  that moment forks it from the header, and makes the change in the fork, where
  it too takes at the fork's own clock. A fork with a change at its instant is
  offered only once the epoch has ended.
- A change waits for the worker: a paced worker looks every 50 ms, a free one
  once a day of its own, and the replay reads the changes every second.
- The answers of `…/changes` are published as schemas for the viewer to read
  (`change_asked.schema.json`, `epoch_changes.schema.json`).
- Worth revisiting if the replay is given a way to change a running epoch at a
  past moment, which would be a fork made with its changes, or if a change other
  than a level or a target (a plant's work) is offered in a replay.
