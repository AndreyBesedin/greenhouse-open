# 0074: The viewer starts no playback; a playback is a consumer's

**Status:** Proposed
**Date:** 2026-11-08

## Context

A playback (decision 0041) is a scenario's run computed in the API's process
against one clock, which the viewer and a consumer once shared. Decision 0065
made it an epoch in the run store, committed a day at a time as its clock
passes, and said its per-scenario routes "remain until the viewer and the
consumer interface read stored runs, then go (by a decision of their own if a
downstream application reads them)". P22 gives a person one place to watch a
run, the replay (P22.2), which steers a running epoch (P22.1, decision 0073).
What is left of the viewer's own play is this decision's to settle.

What a playback is made of, and who uses it:

- **The local API's routes** (`api/routes/playback.py`, `services/playback.py`):
  `GET /api/scenarios/{id}/playback`, its state as `playback.schema.json`
  publishes it, and `POST …/playback/start` (`seconds_per_day`, `layout`,
  `seed`, `hold`), `/play`, `/pause`, `/restart` (with a `layout`, a run
  rearranged), `/pace` and `/targets`, deprecated in 0.5.0 as an alias for one
  release (P13.7). The server's `--play`, `--hold` and
  `--play-seconds-per-day` start one with the API.
- **The surfaces that read only playbacks:** the consumer interface
  (`/consumer/v1`, decision 0040) and the gateway (`/actuation/v1`, decision
  0046), through `Simulator.playbacks`. A worker's epoch is not one of their
  runs (P17.4 and P17.7, "not yet").
- **The policy's port** (P15, decision 0061) reads a `PlayedRun`: in the
  process, a playback served to no one whose clock an experiment's runner
  steps (`experiment.py`); over the network, a playback in a simulator of
  the port's own server (`api/policy_server.py`), not the local API's. No
  route of the local API reaches either.
- **The `Playback` class itself** is also the work a worker does
  (`services/workers.py`): every epoch, whoever computes it, is a playback's
  work. That is not in question here.
- **The viewer's own play:** a scenario followed (`&follow=1`, or `?live=`,
  decision 0059) as its playback plays, from the scenario list's *Follow*
  (`SourceChooser`, `ScenarioList`). It is `PlaybackPanel`, `useFollow`,
  `scene/playback.ts` and its generated contracts, `useFollowFraming`, the
  plan given through the gateway (`useGiveToPlayback`, `plan/plan.ts`), a
  plant's work (`PlantActions` beside the panel), a layout's moves starting
  the playback over (`useMoveSession`, `MovePanel`) and the timeline's plan
  lane, read from the consumer interface and the gateway (`timeline/planLane.ts`).
- **The browser specs that use it:** `follow.spec.ts` whole; `plan-qa.spec.ts`
  (P13.10's QA), which drives the playback's routes, the gateway and the
  consumer interface; a test or a step each of `moving.spec.ts` (#271),
  `selection.spec.ts`, `info-panel.spec.ts`, `panels.spec.ts` (#304),
  `renderer-smoke.spec.ts` and `p09-final-qa.spec.ts` (its 0.5.0 step).
- **The Python tests** of the routes, the consumer interface, the gateway and
  the port drive playbacks in the process; one holds the `targets` alias
  (`test_actuation_api.py`). Examples 01 and 02 play a run in the process,
  and example 05 starts the port's server.

## Options weighed

- **The viewer's play goes; the playbacks stay, a consumer's** (chosen). The
  viewer no longer starts, follows or steers a playback. The routes, `--play`,
  the consumer interface, the gateway and the port stay as they are, for a
  consumer, until those surfaces read a stored epoch. What is gone is only
  the viewer's.
- **The playbacks go too, the consumer interface and the gateway reading
  stored epochs.** It is decision 0065's end, and the place of a playback in
  the API's process, outside the scheduler's limits (P18.3), would go with it.
  But it is a project, not a step: a stored epoch is committed a day at a
  time, so a consumer on the wall clock would read a day's records at once;
  the gateway answers a receipt at once, where an epoch's worker answers a
  plan only through the store, and only when it refuses one; and a run has
  several epochs, of which the interface would have to say which is its run.
- **The playbacks go, and the consumer interface and the gateway with them,**
  leaving the port's own server as the only run read live. It breaks every
  consumer of the local API to remove code that costs little to keep.

## Decision

- **No control of the viewer starts, follows or steers a playback.** What
  each of its uses becomes:
  - **watching a run as it computes:** its replay, following the newest day
    (P22.2). The scenario list's *Follow* goes. `?live=<id>` and a scenario's
    `&follow=1` are read no more, and lead nowhere: a page opens as if its
    address did not have them. A replay's own `&follow=1` (P22.2) stays;
  - **play, pause and pace:** the replay's transport. *Start over*, a new epoch
    from the run's start, is a new run at the same seed, from the scenario's
    dialog;
  - **a level or a target set:** the replay's steering of a running epoch
    (decision 0073), and a fork once it has ended;
  - **moves applied:** a fork in the moved layout, from the replay (P17.8);
  - **a plant's work** (a leaf removed, a fruit or a truss harvested, the
    stem lowered): offered in the replay for the selected organ's plant, as
    a plan of the viewer's own, its action as soon as the run can carry it
    out, as the viewer's play gave it. While the epoch takes changes the plan
    is asked of it through its changes, and once it has ended it is a fork's
    change from the moment shown; both take a plan already (`PlanGiven`). The
    replay cannot read a plan's revision in force from the store, so each
    action is a plan of its own, at its first revision, named by the
    request. What became of it is said as for a level or a target (decision
    0073), and in the plan lane;
  - **the plan lane:** drawn in the replay, from the outcomes its epoch
    delivered by the moment shown (`GET /api/positions/{id}/outcomes`), in
    place of the consumer interface's and the gateway's;
  - **framing that follows the latest scene, and "Draw the run played back":**
    nothing. A replay opens framed, and draws its epoch's run alone.
- **The playbacks stay, a consumer's.** `--play`, `--hold`,
  `--play-seconds-per-day`, `/api/scenarios/{id}/playback` and its commands,
  `/consumer/v1` and `/actuation/v1` are unchanged, and their words say a
  consumer's run, not the viewer's. A playback keeps its epoch in the store,
  so that a person watches a consumer's run in its replay, which waits at
  the playback's clock, and steers it from there, the playback taking the
  epoch's changes between its moments as a worker does.
- **The `targets` alias goes:** `POST /api/scenarios/{id}/playback/targets`,
  deprecated in 0.5.0 for one release. A consumer gives the plan `targets`
  its next revision through the gateway, as the alias did; a person sets a
  target in the replay.
- **The policy's port stays as it is,** in the process and over the network:
  it is not the viewer's, and the viewer's going changes none of its inputs.
  Reading a stored epoch is left with the consumer interface's.
- **`playback.schema.json` stays published,** as the answer of a route that
  stays, and leaves the viewer's generated contracts
  (`src/scene/generated/playback*.ts`), which nothing reads then.
- **The viewer's own climate play stays** (`ClimateTime`, at
  `/view?scenario=`): it starts no playback, draws moments on demand and
  keeps nothing. Whether `/view` keeps a play of its own once P22.4 takes
  *Open in the viewer* away is P22.4's.

## Consequences

- **Not delivered:**
  - the consumer interface, the gateway and the policy's port reading a
    worker's epoch, or one kept from before a restart (future work, as
    P17 left it), and with it the playbacks' going;
  - limits on a playback in the API's process (P18.3's item);
  - a plant's work taken back in a replay, as the plant lab takes it back:
    a plan given is cancelled through the epoch's changes, which take that
    too, but the replay offers no control for it;
  - the plan lane's actions still to come, which the gateway listed and the
    store does not keep;
  - a replay that starts its run over: a new run at the seed, or a fork at
    its start.
- **What breaks,** for the release's changelog: the `targets` alias; the
  viewer's `?live=<id>` and a scenario's `&follow=1`, which open the page as
  if they were not there, and no longer a run followed. No `greenhouse_protocol` record or contract
  changes, so the protocol's range is as the release sets it, and no
  published schema is removed. As for the live mode (decision 0059), each
  pull request that breaks marks it (`!` and a `BREAKING CHANGE:` footer)
  and gives its changelog entry, which says what to use instead.
- **Easier:** one way for a person to watch and steer a run, and about two
  thousand lines of the viewer and its tests gone. The viewer reads no
  playback, so the playbacks' later going touches the server alone.
- **Harder:** two ways to compute a run stay in the server, the scheduler's
  workers and a playback in the API's process, the second with no limits.
- **Supersedes** decision 0059's "a `?live=<id>` address opens that
  scenario's run instead", since the address is read no more, and what was left of decision 0041's run for the viewer and a
  consumer against one clock: a consumer's playback is watched in a replay,
  a position over its epoch, not followed. Decision 0073's "worth
  revisiting", a change other than a level or a target offered in a replay,
  is met by a plant's work, under the same rules.
- **Worth revisiting** when the consumer interface and the gateway read a
  stored epoch: then the playbacks, their routes and `--play` go, by a
  decision that says how a consumer starts the run it reads.

## Open for its review

1. **Whether the playbacks stay** for consumers, as proposed, or go in P22
   with the consumer interface and the gateway reading stored epochs, which
   would make P22.3 a project of its own. This may yet be revisited.
