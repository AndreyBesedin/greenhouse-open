# 0072: An epoch keeps its authorisation in its log

**Status:** Accepted
**Date:** 2026-11-06

## Context

Decision 0052 makes the authorisation an input of the run: the server is
given it as a file, every playback's gateway enforces it, and a change of it
made while runs play (`Simulator.authorise`) holds from each playback's
moment, recorded beside each plan (`PlanState.authorisation`). Decision 0065
keeps an epoch in a store, its changes in its intervention log, written
before they are acted on and applied again, each at its moment, when the
epoch is carried on or forked; the store is the only channel between a
worker and the API.

The two did not meet. A change of authorisation was in no epoch's log and
nowhere in the store, and a worker's process builds its own simulator
(`scheduler.work`), whose authorisation is the local operator's:

- **An epoch whose rights were withdrawn while it ran could not be carried
  on.** Found writing the test of P13's criterion 8: the heater set for noon,
  the right to set levels withdrawn at 6 h, the action refused at noon and
  the first day kept. Carried on from its checkpoint, the log was applied
  again under one authorisation, and gave other outcomes than those kept:
  the epoch stopped with a conflict.
- **A worker decided every action under the local operator's rights,**
  whatever the server was given. On 0.7.0, a server whose file withholds
  levels started a run that a worker computed, and a level asked of it
  through the store was executed. The API's route checks what the local
  operator asks against the server's file as it is asked, so that through
  the local API the gap was narrower: a change of the authorisation made
  while a worker computed an epoch never reached it, and a fork, carried on
  by a worker, went on under the local operator's rights.

The trajectory digest covers the log: each commit names the entries given
before its span ended (`EpochStore.commit`, `_log_bytes`), and `_extend`
takes them in. An entry written into every epoch's log would give every
epoch a digest other than the one 0.7.0 gives the same run.

## Options weighed

- **Each change logged, as the log's other entries are** (chosen). The
  rights an epoch begins under and each change of them are entries of its
  log, at their moments. The log already travels with a resume and a fork,
  and is applied in order with the changes it orders; nothing else of the
  store changes.
- **The authorisation in the manifest.** It would give the rights an epoch
  begins under, but not their changes, which would still need the log. The
  manifest is read with no field it does not know (`extra="forbid"`), so
  that 0.7.0 could no longer list a store holding one; and it is written
  again at each status, by more than one writer.
- **A worker reading the server's file.** The worker would be given the
  file's path and read the rights in force when it reads, not those the
  epoch had: a resume after the file changed would decide kept actions
  again under others, and stop as before. A change made by
  `Simulator.authorise` is in no file, a worker on another machine reaches
  none, and decision 0067 has a worker need nothing but the store.

## Decision

- **A change of authorisation is an entry of the epoch's log**
  (`interventions.AuthorisationChanged`, of kind `authorisation`): the
  whole `AuthorisationConfig`, given by the local operator, at the moment of
  the epoch's clock it is made at. A playback logs it as it applies it
  (`Playback.authorise`), before it acts, as it logs any change, unless its
  run has ended.
- **The rights an epoch begins under are its log's first entry,** at its
  start, unless they are the local operator's. It is written by whoever
  starts the epoch, before its manifest, under the simulator's lock of its
  authorisation: an epoch queued for a worker (`workers.queued`), one a
  playback opens, and one a restart opens. **A log with no such first entry
  began under the local operator's rights,** so that an epoch begun under
  them keeps the log, and the digest, that 0.7.0 gives it.
- **Applied again like any entry.** A worker's playback builds its gateway
  under the rights its epoch's log begins with, and applies each change at
  its moment (`Playback._apply`, `resume_at`), as it applies a plan given.
  A worker, a resume after a restart and a fork decide every action under
  the rights in force at its moment.
- **A fork goes on from its instant under the rights of the simulator that
  forks it.** It inherits the entries given by its instant, the rights in
  force there among them, so that what it works again from its checkpoint
  is decided as its parent decided it. If the forking simulator's
  authorisation is not those rights, it is the fork's own entry at the
  instant, after those it inherits and before the changes it is asked to
  make, which are checked under it as they are asked. A fork made by the
  simulator that withdrew the rights goes on under the withdrawn rights. A
  playback rearranged into another layout begins under the simulator's
  rights, as any new playback does.
- **A change reaches the epochs workers compute through the store.**
  `Simulator.authorise` tells its playbacks, as before, and asks every other
  epoch of its store that is queued, running or can be carried on: a
  request (`requests/{id}.json`), which the epoch's worker takes between its
  moments, as it takes a change or a stop, and logs at its clock's moment
  then. The changes are asked under the simulator's lock, one after another,
  and a worker takes the requests in the order of their names, which are the
  order they were asked in by the store's clock: a change asked before an
  authorisation is decided under the rights before it, one asked after under
  those after. Once logged, the log's order is the order they act in. The
  API's route takes no such request (`Asked` is as it was; `Requested` adds
  the kind): the authorisation stays the server's input (0052).
- **An epoch kept before this** has no such entry, and began under the local
  operator's rights. That is what every worker of 0.7.0 carried an epoch on
  under, its simulator being the local operator's; an epoch 0.7.0 played in
  a server's process under a file of its own, whose outcomes those rights do
  not give again, is refused as it was.
- **0.7.0 cannot read a log with the new kind.** It refuses the entry when
  it applies the log, so that it can neither carry on nor fork such an
  epoch; it still lists the epoch and reads its records, which are as they
  were.

How it stands to 0052 and 0065: it extends 0052's recorded change to the
epochs workers compute, and adds a kind to 0065's intervention log, whose
worker stays its only writer once it has begun. It supersedes neither.

## Consequences

- No run id, replay digest, golden file or pin moves, and the manifest,
  commit and checkpoint formats are as they were (`run-store-1`). An epoch
  begun under the local operator's rights and given no change of them has
  the trajectory digest 0.7.0 gives it. One begun under a file, or given a
  change of rights, has entries 0.7.0's log did not, and so a digest of its
  own, as two epochs given different changes have.
- A change of authorisation reads each manifest of the store once, to find
  the epochs to ask. `GET /api/runs/{run}/epochs/{n}/changes` lists the
  entry with the whole configuration, on the local API (decision 0009).
- A change reaches a worker's epoch at the moment its worker takes it, not
  at the moment it was made, as any change asked through the store does.
- An epoch carried on keeps the rights its log says, whatever the authorisation
  of the simulator that carries it on: the server's route checks what it is
  asked against its own, and its next change reaches the epoch. A fork made by
  a simulator of other rights than its parent's takes them from its instant.
- Worth revisiting if the authorisation is given a route of its own, or a
  store is shared by servers of different authorisations, when which server's
  change reaches which epoch is a question of its own.
