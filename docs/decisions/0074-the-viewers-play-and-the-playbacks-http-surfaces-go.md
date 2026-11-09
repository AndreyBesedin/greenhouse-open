# 0074: The viewer's own play goes, and the playbacks' HTTP surfaces with it

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
This decision settles what becomes of the viewer's own play, and of the
playbacks it leaves behind.

What a playback is made of, and who uses it:

- **The local API's routes** (`api/routes/playback.py`, `services/playback.py`):
  - `GET /api/scenarios/{id}/playback`, its state as `playback.schema.json`
    publishes it;
  - `POST …/playback/start` (`seconds_per_day`, `layout`, `seed`, `hold`),
    `/play`, `/pause`, `/restart` (with a `layout`, a run rearranged) and
    `/pace`;
  - `/targets`, deprecated in 0.5.0 as an alias for one release (P13.7).

  The server's `--play`, `--hold` and `--play-seconds-per-day` start a
  playback with the API.
- **The surfaces that read only playbacks:** the consumer interface
  (`/consumer/v1`, `api/consumer.py`, decision 0040) and the gateway's routes
  (`/actuation/v1`, `api/actuation.py` and `services/actuation.py`, decision
  0046), through the simulator's playbacks (`Simulator.playbacks`). A
  worker's epoch is not one of their runs (P17.4 and P17.7, "not yet").
- **The policy's port** (P15, decision 0061) reads a `PlayedRun`:
  - in the process, a playback served to no one, whose clock an
    experiment's runner steps (`experiment.py`);
  - over the network, a playback in a simulator of the port's own server
    (`api/policy_server.py`), not the local API's.

  No route of the local API reaches either.
- **The `Playback` class itself** is also the work a worker does
  (`services/workers.py`): every epoch, whoever computes it, is a playback's
  work.
- **The viewer's own play:** a scenario followed (`&follow=1`, or `?live=`,
  decision 0059) as its playback plays, from the scenario list's *Follow*
  (`SourceChooser`, `ScenarioList`). It is made of:
  - `PlaybackPanel`, `useFollow`, `scene/playback.ts` and its generated
    contracts, and `useFollowFraming`;
  - the plan given through the gateway (`useGiveToPlayback`, `plan/plan.ts`);
  - a plant's work (`PlantActions` beside the panel);
  - a layout's moves starting the playback over (`useMoveSession`,
    `MovePanel`);
  - the timeline's plan lane, read from the consumer interface and the
    gateway (`timeline/planLane.ts`).
- **The browser specs that use it:**
  - `follow.spec.ts`, whole;
  - `plan-qa.spec.ts` (P13.10's QA), which drives the playback's routes, the
    gateway and the consumer interface;
  - a test or a step each of `moving.spec.ts` (#271), `selection.spec.ts`,
    `info-panel.spec.ts`, `panels.spec.ts` (#304), `renderer-smoke.spec.ts`
    and `p09-final-qa.spec.ts` (its 0.5.0 step).
- **The Python tests** of the routes, the consumer interface, the gateway and
  the port drive playbacks in the process: `test_consumer_api.py` and
  `test_actuation_api.py` whole, and the HTTP parts of `test_playback.py`,
  `test_plan_final_qa.py`, `test_failed_playback.py` and others. Examples 01
  and 02 play a run in the process through the simulator's playbacks, and
  example 05 starts the port's server.

Once the viewer's play goes, nothing in the repository uses the playbacks'
HTTP surfaces. A policy's evaluation steps its run's clock, in the process or
through the policy's port, which a playback reached over HTTP cannot do: its
clock moves by real time at its pace, with no step
([the policy evaluation memo](../research/policy-evaluation-contract.md),
"A clock an experiment can step").

## Options weighed

- **The viewer's play goes, and the playbacks' HTTP surfaces with it**
  (chosen). The routes, `/consumer/v1`, `/actuation/v1` and the options that
  start a playback with the API go, and with them the simulator's book of the
  playbacks it plays. `Playback`, the in-process services the policy's port
  is built on, and the port's own server stay.
- **The viewer's play goes, and the playbacks stay, a consumer's.** The
  routes, `--play`, the consumer interface and the gateway would stay as they
  are until they read a stored epoch. But they would have no user: no
  example, test of a use or part of the viewer reads them, and a policy's
  evaluation needs a clock they cannot step. A second way to compute a run
  would stay in the API's process, outside the scheduler's limits (P18.3).
- **The consumer interface and the gateway reading stored epochs.** It is
  decision 0065's end, but a project and not a step: a stored epoch is
  committed a day at a time, so a consumer on the wall clock would read a
  day's records at once; the gateway answers a receipt at once, where an
  epoch's worker answers a plan only through the store, and only when it
  refuses one; and a run has several epochs, of which the interface would
  have to say which is its run. A live interface over worker runs is
  designed afresh, if one is wanted.

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
- **The playbacks' HTTP surfaces go:**
  - `/api/scenarios/{id}/playback` and every command of it, the deprecated
    `targets` alias among them, and its published answer,
    `playback.schema.json`, with the viewer's contracts generated from it;
  - the consumer interface's routes, `/consumer/v1` (`api/consumer.py`), and
    what of `services.consumer` only they read: the runs it lists and its
    reads by a run's identifier;
  - the gateway's routes, `/actuation/v1` (`api/actuation.py`,
    `services/actuation.py`);
  - the server's `--play`, `--hold` and `--play-seconds-per-day`;
  - the simulator's book of the playbacks it plays (`Playbacks`,
    `Simulator.playbacks`), and what reads it: the playback a stored epoch's
    position waits behind, the epochs a playback holds, and a stop or an
    authorisation that reaches an epoch through its playback.
- **What stays:**
  - `Playback`, which every worker runs, and which an experiment's runner
    and the port's server make for themselves;
  - the in-process services the policy's port and its server are built on:
    the consumer interface's cursors and batches (`services.consumer`), the
    gateway (`services.gateway`), `services.policy_port` and
    `services.policy_requests`;
  - the policy's port, in the process and over the network
    (`api/policy_server.py`), as it is;
  - the protocol's `consumer` and `gateway` contracts and the consumer
    fixture. They describe what a producer implements, a live reading of a
    worker's run or a real greenhouse, which the simulator no longer serves
    over HTTP. No protocol record or contract changes, and the protocol's
    README no longer says the simulator serves `/consumer/v1`.
- **The viewer's own climate play stays** (`ClimateTime`, at
  `/view?scenario=`): it starts no playback, draws moments on demand and
  keeps nothing. Whether `/view` keeps a play of its own once P22.4 takes
  *Open in the viewer* away is P22.4's.

## Consequences

- **Not delivered:**
  - a consumer interface and a gateway over stored epochs, live or after a
    restart, for a consumer that reads a run as it computes (future work,
    designed afresh if one is wanted);
  - a plant's work taken back in a replay, as the plant lab takes it back:
    a plan given is cancelled through the epoch's changes, which take that
    too, but the replay offers no control for it;
  - the plan lane's actions still to come, which the gateway listed and the
    store does not keep;
  - a replay that starts its run over: a new run at the seed, or a fork at
    its start.
- **What breaks,** for the release's changelog, a breaking change of
  `greenhouse-sim` and of the viewer:
  - `/api/scenarios/{id}/playback` and its commands, `/consumer/v1`,
    `/actuation/v1`, and the server's `--play`, `--hold` and
    `--play-seconds-per-day`. A run is asked of a worker
    (`POST /api/scenarios/{id}/runs`), its records read by a cursor through
    its epoch (`GET /api/runs/{run}/epochs/{n}/observations|events|outcomes`),
    and steered through its changes; a policy reaches a run through its port;
  - the published `playback.schema.json`;
  - the in-process functions that read the simulator's playbacks
    (`playback.start`, `playback.command` and their like, and the consumer
    reads by a run's identifier);
  - the viewer's `?live=<id>` and a scenario's `&follow=1`, which open the
    page as if they were not there, and no longer a run followed.

  No `greenhouse_protocol` record or contract changes, so the protocol's
  range is as the release sets it. As for the live mode (decision 0059), each
  pull request that breaks marks it (`!` and a `BREAKING CHANGE:` footer) and
  gives its changelog entry, which says what to use instead.
- **Easier:** one way for a person to watch and steer a run, and one way to
  compute one, the scheduler's workers, all within its limits; P18.3's item,
  a playback in the API's process with no limits, goes with the playbacks.
  Some thousands of lines of the viewer, the API and their tests go.
- **Harder:** a downstream application that read a run live over
  `/consumer/v1`, or gave one plans over `/actuation/v1`, has no such surface
  until one is designed over worker runs; it reads an epoch's records by its
  cursor, after they are committed, a day at a time.
- **Supersedes:**
  - decision 0040's "the simulator is the first [producer]": the consumer
    interface stays the protocol's, and the simulator serves it no more;
  - what was left of decision 0041: a run played back against one clock
    for the viewer and a consumer;
  - decision 0059's "a `?live=<id>` address opens that scenario's run
    instead", since the address is read no more;
  - decision 0065's per-scenario playback routes remaining until the
    consumer interface reads stored runs: they go before it does.

  Decision 0073's "worth revisiting", a change other than a level or a target
  offered in a replay, is met by a plant's work, under the same rules.
- **Worth revisiting** if a consumer needs to read a run live, as it
  computes: then a consumer interface over a worker's epoch, and a gateway
  answering through the store, by a decision of their own.
