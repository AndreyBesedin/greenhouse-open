# 0065: A run is a scenario at a seed, kept in a store and played from it

**Status:** Proposed
**Date:** 2026-10-31

## Context

A `Playback` (decision 0041) is at once a run's worker, its clock and what
every viewer and consumer of it reads. As built:

- **One playback a scenario.** The simulator holds one playback for each
  scenario (`Playbacks.get(scenario_id)`). A viewer that starts it over with
  another layout replaces it, and the run played before is no longer served
  (#271).
- **A clock that only moves forward.** The worker computes days ahead of
  the clock, but the only way back is a restart, a new epoch for everyone
  who follows the run.
- **Nothing kept.** A day's records are compressed bytes in memory, and
  checkpoints are in the API's memory. The only file on disk is each run's
  last epoch number. A restart of the API loses every run, and a run
  interrupted cannot be resumed.
- **The seed belongs to the scenario.** `ScenarioConfig.random_seed` seeds
  its weather, sensor noise and plants. A run request (`RunRequest`) cannot
  carry another, so two runs of a scenario differing only by seed cannot
  exist, and a batch of them (to train or evaluate policies) cannot be
  asked for.
- **A change made while a run plays is not part of its identity.** A target
  or a plan given to a playing run changes it in place, in the same run and
  epoch (decision 0043). The playback's state lists those changes, but
  nothing names two differently steered runs apart.
- **The viewer has no place to choose.** Its address `/` is the whole
  viewer, with the setup builder at an address of its own; there is no page
  from which a person builds a scenario, launches a run or opens one that
  has been run.

What already holds, and is kept: the viewer draws any moment of a run on
demand (air, crop, sensors and equipment are functions of the moment, with
the days before kept as states, P09.5), so seeking a scene needs no new
computation model; a run is deterministic from its inputs; `run_id` names
what a run is made of (`fields.air_through_a_run`); epochs and the consumer
interface's rules (decision 0040); checkpoints and branches from a day
(P09.5); and the policy port, which reads a run through a small interface
(`PlayedRun`, P15.3).


## Decision

- **Words.**
  - A **scenario** is everything that is run: the greenhouse and its
    installation, layout, weather source, site, period, crop models and
    their versions, and a default seed.
  - A **run** is a scenario at a seed, with the layout and weather it is
    asked for, as `RunRequest` names it today and with the seed added.
  - An **epoch** is one execution of a run from its start (decision
    0040), with results of its own. In a person's list a *stored run* is a
    run's epoch: its seed, its epoch, its status.
  - A **playback** is a position over one epoch's stored results.
- **The seed is a run's input.** `RunRequest` gains a seed; none means the
  scenario's own. A run at the scenario's own seed keeps the `run_id` it has
  today, and the seed enters the digest only when it differs, so no run id,
  replay digest or kept opening day moves.
- **Four things are told apart,** because two epochs of one run can differ:
  - the **initial inputs,** immutable: the run request, its seed, the
    installation's digest, the models' and the code's versions. `run_id`
    names them;
  - the **epoch's identity:** its run and its number, and for a fork its
    parent;
  - the **intervention log,** ordered: each entry has a sequence number, the
    simulated instant it takes effect, who gave it, and what it is, as the
    gateway's plans and receipts have it;
  - the **realized trajectory:** a digest over the epoch's records, states
    and intervention log up to its frontier, extended at each commit and
    checked on reading. It is what tells two epochs of one run apart.
- **A run is executed into a store.** An epoch is executed by a worker,
  which writes it to a run store and is the only writer. The API never
  computes an epoch itself; it reads the store. The store is an interface
  over named objects (put one whole, get, list, delete), so that a local
  folder under the state folder, shared by every checkout on the machine,
  and an S3-compatible object store are interchangeable backends. The first
  is built first; the second is chosen or not after P17.1's measurements.
- **The store is divided by simulated instants, not by days.** Records are
  kept in segments, and models' states in checkpoints, each at an instant.
  A segment's length and the checkpoint interval are settings, 24 hours of
  simulated time (86,400 s) by default; a day here is that span, not the
  light period. Seeking works to an instant: the nearest checkpoint at or
  before it is restored and the run works forward.
- **A checkpoint is a contract with each model,** not a step boundary all
  models share. At a requested instant a model exports a state sufficient to
  restart it, its solver's or internal state included, or declares the
  instants it cannot be checkpointed at and why. The store keeps each model's
  state as the model declares it and assumes nothing of its shape: a crop
  grown by plant keeps plants, one grown by area keeps its scopes and what it
  lived in each of its model's steps (decisions 0062 and 0064), with no plant
  identifiers and more than one course a day. A checkpoint's cadence never
  dictates a model's integration cadence.
- **One commit advances the frontier.** A commit names the segment, the
  checkpoint if there is one, the position reached in the intervention log
  and the trajectory digest so far. A reader sees what the last commit
  names, and anything written after it is ignored and written again.
  An intervention is logged, with its sequence number, before it is acted on,
  and is applied once a commit names it. After a crash, entries past the last
  commit are applied again by their sequence numbers, none lost and none
  twice; the gateway refuses a repeated identity. How a commit is made
  physical (files renamed into place, a database) is left to the
  measurements of P17.1.
- **Store modes.** `full` keeps every segment and checkpoint, so that any
  moment up to the frontier can be played. `present` keeps what its promise
  needs: enough segments and checkpoints to show the epoch at its present
  and the observation window it supports, and to resume it if it promises
  that. How many that takes is a storage policy fixed by P17.1. A run is
  stored in the mode it was asked for, `full` by default.
- **Status.** An epoch is `queued`, `running`, `finished`, `failed` (with its
  reason) or `interrupted`: found at startup in `running` with no worker
  alive. An `interrupted` epoch can **resume** from its last committed
  checkpoint with the log applied again; runs are deterministic, so a
  resumed epoch is the epoch that was never interrupted, and a test holds
  the trajectory digests equal. Resuming is a capability delivered after the
  first (below); the commit and the log are specified now so that it can be.
- **Workers and many runs.** A worker executes one epoch through one
  interface, `execute(epoch, store, driver)`. A scheduler runs workers up to
  a configured number and queues the rest, so that many runs at different
  seeds (as when policies are trained) can be asked for at once. Whether a
  worker is a thread or a process is chosen by measurement (P17.1, P17.4) and
  is not fixed here; the store is the only channel between a worker and the
  API, so either serves.
- **An epoch has a frontier and a driver.** Its frontier is how far it is
  computed. Its driver decides how it advances: *free*, as fast as it can be
  computed; *paced*, by a clock at a number of real seconds a simulated
  day, for a consumer on the wall clock; or *stepped*, by an experiment's
  barriers (P15). The consumer interface reads an epoch as it does now,
  records delivered by its run time and never after, and decision 0040's
  rules hold: records extend and are never rewritten, and the run's time
  never steps back.
- **A playback is a position, not a clock.** A playback sits at or before one
  epoch's frontier. It plays at a pace, pauses, seeks to any moment up to the
  frontier, or follows the frontier as it advances. Many playbacks may read
  one epoch; none changes it, and a seek is never a new epoch. A viewer that
  scrubs leaves what a consumer reads where it was. A run too slow to watch
  at its pace can still be played over what has been computed.
- **Changes during a run are the epoch's own.** A target, a level or a plan
  given to an epoch while it runs acts from its instant on, in the same
  epoch (decision 0043 holds), and is written to its intervention log, so
  that replaying the epoch shows it. A position in the past changes nothing.
- **A fork is not a fresh run.** To act from a past instant, a person or a
  program forks. A fork records its parent epoch, the exact instant, the
  state it inherits (named by the parent's checkpoint and trajectory
  digest), the interventions it inherits, and the inputs it changes from
  then on. It does not compute what lies before the instant. A layout
  rearranged (#271, decision 0049) is a fork; the epoch it came from stays in
  the store and is still served.
- **Delivered in order, the contracts fixed now.** The commit, the
  checkpoint contract, the identities and the intervention log are defined
  here so that later capabilities do not change what is stored. The
  capabilities arrive as: (a) completed runs persisted, and a seed that
  varies; (b) a playback that seeks; (c) concurrent execution, and a
  frontier that is followed while a run computes; (d) interventions and
  forks; (e) deterministic recovery of an interrupted run, when the cost of
  restoring models' states is known. Each is a step of P17 and none is
  required for the one before.
- **A place to choose.** The viewer's first page lists the scenarios, with a
  search, and from one of them the stored runs of that scenario, a way to
  launch another (its seed, its store mode, its pace), and the setup builder
  for a new scenario, which ends in *save and start a run* or *save and go
  back*. A run opens at an address of its own, naming its run
  and epoch.
- **What it supersedes in decisions 0041 and 0049, once accepted:** one
  playback a scenario; one clock that the viewer and a consumer share; a
  restart as the only way back; runs that are not kept; and 0049's "the run
  played before is no longer served". The records of the earlier decisions
  are marked then, not before. Their run's determinism, working out ahead of
  what is played, consumer cadence and records' compression stand.

## Consequences

- **Smaller than it sounds:** the scene is already drawn by moment, the
  worker already computes ahead of the clock, and branches from a state
  exist. New are the store, the seed, the scheduler, the frontier, the
  commit and playback as a position, and the pages.
- **The local API gains runs as things it lists, opens, launches and
  deletes;** its per-scenario playback routes remain until the viewer and
  the consumer interface read stored runs, then go (by a decision of their
  own if a downstream application reads them).
- **Disk use becomes a concern.** A `full` epoch keeps its models' states at
  every checkpoint, and a crop's size varies with its model's steps. The
  sizes are measured before the format is fixed (P17.1); a store says where it
  keeps its files and how a run is deleted.
- **The policy port and the experiment runner are unchanged in contract.**
  An experiment's `step_to` becomes the stepped driver of an epoch in a
  store; a port reads the epoch through `PlayedRun` as before.
- **Drafts become a dependency.** A run of a builder's draft names the draft's
  installation by digest, so that it can be opened and resumed after the
  draft has changed or the simulator has restarted.
- **What stays open** is in [P17](../roadmap/p17-runs-and-playbacks.md): the
  physical commit and format, the default segment length, the worker
  technology, retention, the store's place and a repeated launch.
- **Worth revisiting** if a `full` epoch's states are too large to keep, when
  a coarser keeping with a recomputation between checkpoints would take
  their place.
