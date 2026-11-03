# 0067: A run's resources are counted and limited, and all it needs is in the store

**Status:** Accepted
**Date:** 2026-11-03

## Context

Decision 0065 runs epochs in workers, up to a number, and keeps them in a
store. Nothing else about their cost is watched. A simulator runs two workers
(`DEFAULT_WORKERS`), which its server cannot change; the queue has no length; a
worker has no budget of memory, time or disk; nothing says what a run used; and
an epoch that fails says so without saying why, though 0065 gives it a reason.

[P18](../roadmap/p18-resources-and-deployment.md) measured what a run costs on
one machine: a 120-day run of the reference greenhouse keeps 20.6 MB in 601
objects, 84% of it checkpoints, in a worker that peaks at about 330 MB. A
thousand seeds of it, as training a policy asks for, is about 21 GB and 190
hours of a core. A store of 1,000 such runs takes 28 s to list, on every request.

The simulator runs on one person's machine today. Two other ways of deploying
it are foreseeable, and the design should not rule them out:

1. **One machine, one person.** The API on loopback, a store in a folder. This
   is what exists.
2. **One server, one team.** People who do not run it themselves share its
   workers and its store.
3. **A service, many parties.** Parties who do not know each other, whose data
   the service holds, each of whom must not see or starve another.

Building for the third now would be guessing, and would slow the first. Doing
nothing would let choices made for the first harden: the scheduler already
refuses any store but a folder, and a worker can run only packaged scenarios.

## Decision

**Build the first; keep five rules, so that the others remain possible.** Each
rule costs little now and is expensive to add later.

1. **An epoch is self-contained.** All that a worker needs is in the store: the
   manifest, the scenario in its portable form (P17.11), and the recording it
   names. A worker is given a store's address and an epoch, and nothing else, so
   that it can run any scenario on any machine that reaches the store. This
   replaces the worker's building a simulator of packaged scenarios.
2. **What must outlive a process is in the store.** The store is the only channel
   between processes (0065), and now the only durable state of a run. What a
   process holds in memory can be rebuilt or lost. The store's interface gains
   one operation, *create this object unless it exists*, which a folder and an
   object store both give atomically, so that a worker's claim on an epoch needs
   no lock across processes.
3. **A party is an instance, not a column.** A party is a namespace in the store,
   with a `Simulator` (0048), its limits and its credentials. No manifest has an
   owner, and no service takes one. Whoever authenticates a request chooses the
   simulator that answers it, in front of `respond`, as routes already take one.
   A query cannot forget a filter it does not have, equal run ids of two parties
   cannot meet, and removing a party is removing a prefix.
4. **What a party sends is data.** A scenario file is declarative, its models come
   from the registry (0054), and a policy runs in its own process behind a port
   (0061). Nothing sent is executed by the simulator. An extension that would
   break this needs a record of its own, with its sandbox.
5. **Expensive work belongs to workers, under a budget.** The API answers; it does
   not compute. Work it still does, listed in P18, is named as a debt, and no new
   work is added to it.

**Resources are handled in three layers, of which two are built now.**

- **Counted, always.** A worker writes what its epoch used to an object beside the
  manifest at each commit: bytes kept, CPU seconds, peak memory, days computed. It
  is outside every digest, since a machine changes it and a trajectory must not.
  The list reads it, and stops walking every object and commit of every epoch.
- **Limited, by `Limits`,** given to a simulator as its authorisation is (0052),
  from a file or the server's options, with defaults for one machine:

  | Limit | Refused or ended | Default on one machine |
  | --- | --- | --- |
  | Workers at once | Waits | 2 |
  | Runs waiting | Refused when asked for | 200 |
  | Free disk before a run begins | Refused when asked for | 2 GB |
  | Bytes of one epoch | Ended at its commit | None |
  | Bytes of the store | Refused when asked for | None |
  | Memory of one worker | Ended | Half the machine's memory, shared between the workers |
  | CPU or wall time of one epoch | Ended | None |

  An epoch ended by a limit is `failed`, with the limit as its reason, and keeps
  what it committed: it can be read, and resumed once the limit is raised. Every
  failure has a reason now, and the viewer shows it. Workers run at a lower
  priority than the API, so that the viewer stays responsive on the same machine.
- **Shared fairly, later.** Which party's run goes next, and a limit across
  parties, belong to the third deployment and are not built. `Limits` per
  simulator is the seam for it.

**Not built now, and where each plugs in:**

| Later | Seam |
| --- | --- |
| Accounts, tokens, a login | In front of `respond`: rule 3 |
| An object-store backend | `ObjectStore`, with rule 2's operation |
| Workers on other machines, a queue | Rule 1, and epochs claimed from the store |
| A catalogue of runs for a large store | Derived from the usage objects (0066 allows it) |
| Retention, thinner old checkpoints | The store's modes (0065) and the checkpoint interval |
| Containers per worker | The scheduler's launch; its limits stay `Limits` |

## Consequences

- A run of a built or uploaded scenario runs in a worker and resumes, with its own
  weather and site. No run id may move: a worker's run must have the id it was
  queued under, and a test holds it.
- A request can now be refused for capacity, and the viewer has to say so. A long
  batch on one machine meets the 200 waiting runs unless it raises them.
- The usage object is a second writer's object per epoch, and may lag a crash by a
  commit. It is a report, not a record: nothing that decides a trajectory reads it.
- One simulator per party costs memory per party in a process. Its cost has not
  been measured, and would decide how many parties a process holds.
- The API stays one process with state in memory (positions, cursors, live
  playbacks). Several replicas would need positions moved to the client or the
  store. Nothing here prevents it, and nothing here does it.
- Rule 3 would be wrong for parties sharing runs with each other: sharing then
  means a copy, or a link across namespaces. Revisit this if sharing becomes
  central.
