# 0065: A run is a scenario at a seed, kept in a store and played from it

**Status:** Accepted
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
    Its identity is `run_id`.
  - An **epoch** is one execution of a run from its start (decision
    0040), with results of its own. In a person's list a *stored run* is a
    run's epoch: its seed, its epoch, its status.
  - A **playback** is a position over one epoch's stored results.
- **The seed is a run's input.** `RunRequest` gains a seed; none means the
  scenario's own. A run at the scenario's own seed keeps the `run_id` it has
  today, and the seed enters the digest only when it differs, so no run id,
  replay digest or kept opening day moves.
- **A run is executed into a store.** An epoch is executed by a worker,
  which writes it to a run store on disk and is the only writer. The API
  never computes an epoch itself; it reads the store. A store keeps, for
  each epoch:
  - its **manifest:** the run request, its seed, the installation's digest,
    the models' and the code's versions, its store mode and its status;
  - its **days,** appended once each, whole or not at all: the records
    (observations, events, outcomes), and the states at the day's start from
    which the scene is drawn and a run resumes (`kept_states`). The store
    keeps each model's state as that model declares it, and assumes nothing
    of its shape: a crop grown by plant keeps plants, one grown by area keeps
    its scopes and what it lived in each of its model's steps (decisions 0062
    and 0064), with no plant identifiers and more than one course a day;
  - its **intervention log:** every change made to it while it ran, each
    with its moment, as the gateway's plans and receipts have it.
- **Store modes.** `full` keeps every day, so that any moment up to the
  frontier can be played. `present` keeps only the latest day's state and
  records and the intervention log: the epoch can be watched at its present,
  followed and resumed, but not replayed. A run is stored in the mode it was
  asked for.
- **Status.** An epoch is `queued`, `running`, `finished`, `failed` (with
  its reason) or `interrupted`: found at startup in `running` with no worker
  alive. A run that is `interrupted` **resumes** from the state at the start
  of its last whole day with its intervention log applied again. Runs are
  deterministic, so a resumed epoch is the epoch that was never interrupted,
  and a test holds its digests equal.
- **Workers and many runs.** A worker executes one epoch at a time. A
  scheduler starts workers up to a configured number and queues the rest, so
  that many runs of a scenario at different seeds (as when policies are
  trained) can be asked for at once. A worker is a thread when a caller
  steps the run itself (the experiment runner, tests) and a process when
  runs must not compete for one interpreter, as the viewer's day step and a
  playback do today (decision 0041). The store is the only channel between a
  worker and the API.
- **An epoch has a frontier and a driver.** Its frontier is how far it is
  computed (`computed_until_s`). Its driver decides how it advances: *free*,
  as fast as it can be computed; *paced*, by a clock at a number of real
  seconds a simulated day, for a consumer on the wall clock; or *stepped*,
  by an experiment's barriers (P15). The consumer interface reads an epoch
  as it does now, records delivered by its run time and never after, and
  decision 0040's rules hold: records extend and are never rewritten, and the
  run's time never steps back.
- **A playback is a position, not a clock.** A playback sits at or before one
  epoch's frontier. It plays at a pace, pauses, seeks to any moment up to
  the frontier, or follows the frontier as it advances. Many playbacks may
  read one epoch; none changes it, and a seek is never a new epoch. A
  viewer that scrubs leaves what a consumer reads where it was. A run too
  slow to watch at its pace can still be played over what has been computed.
- **Changes during a run are the epoch's own.** A target, a level or a plan
  given to an epoch while it runs acts from its moment on, in the same
  epoch (decision 0043 holds), and is written to its intervention log, so
  that replaying the epoch shows it. A position in the past changes nothing.
  To act from there, a person or a program **forks**: a new run from a
  stored state, with the interventions so far (checkpoints and branches,
  P09.5). A layout rearranged (#271, decision 0049) is a fork; the run it
  came from stays in the store and is still served.
- **A place to choose.** The viewer's first page lists the scenarios, with a
  search, and from one of them the stored runs of that scenario, a way to
  launch another (its seed, its store mode, its pace), and the setup builder
  for a new scenario. A run opens at an address of its own, naming its run
  and epoch.
- **Superseded in decision 0041:** one playback a scenario; one clock that
  the viewer and a consumer share; a restart as the only way back; runs
  that are not kept. Its run's determinism, its day-by-day working out ahead
  of what is played, its consumer cadence and its records' compression stand.
  Decision 0049's "the run played before is no longer served" is superseded
  too.

## Consequences

- **Smaller than it sounds:** the scene is already drawn by moment, the
  worker already computes ahead of the clock, and branches from a state
  exist. New are the store, the seed, the scheduler, the frontier and
  playback as a position, and the pages.
- **The local API gains runs as things it lists, opens, launches and
  deletes;** its per-scenario playback routes remain until the viewer and
  the consumer interface read stored runs, then go (by a decision of their
  own if a downstream application reads them).
- **Disk use becomes a concern.** A `full` epoch keeps its models' states for every day, and a crop's size varies with its model's steps.
  The sizes are measured on the reference scenario before the format is
  fixed (P17.1), and a store says where it keeps its files and how a run is
  deleted.
- **The policy port and the experiment runner are unchanged in contract.**
  An experiment's `step_to` becomes the stepped driver of an epoch in a
  store; a port reads the epoch through `PlayedRun` as before.
- **Drafts become a dependency.** A run of a builder's draft names the draft's
  installation by digest, so that it can be opened and resumed after the
  draft has changed or the simulator has restarted.
- **Worth revisiting** if process workers cost more than the competition for
  one interpreter they remove, or if a `full` epoch's states are too large to
  keep, when a coarser keeping with a recomputation between states would
  take their place.
