# P18: Resources counted and limited, and a run that can move

**Status:** accepted, in progress (P18.1 is done): the design below, with decision
[0067](../decisions/0067-a-runs-resources-are-counted-and-limited-and-all-it-needs-is-in-the-store.md).
Part of the
[simulator roadmap](README.md).

## Goal

A run says what it uses, cannot take a machine down with it, and needs nothing
but the store. On one machine this means a batch of runs that stays within the
disk and memory there are, and a viewer that stays responsive beside it. It also
keeps a shared server, and a service for many parties, possible later, without
building either now.

## Where it stands before P18

Read from the code at commit `28701e05`.

| Concern | Today |
| --- | --- |
| Workers at once | `DEFAULT_WORKERS = 2`, a `Simulator` argument; the server has no option for it |
| Queue | A `deque` in the scheduler's memory, with no length; `queued` manifests are told `interrupted` after a restart |
| Budgets | None: memory, time and disk are unbounded |
| What a run used | `size_bytes` only, by asking the size of every object on each list |
| Why a run failed | Logged; `EpochManifest` has no reason, though 0065 gives `failed` one |
| A worker's scenarios | `Simulator()`, packaged only, so a built or uploaded scenario cannot run in a worker or resume |
| The store a worker uses | A folder only: `scheduler.of` refuses any other |
| Claims and leases | Written without an atomic create: the folder store leaves a window of two calls between checking an owner and writing. A lease names its holder, and a thread writes only its own, so that what remains of a lease is a thread stopped between reading it and writing it while the epoch ended and a new holder took it |
| Authentication | None on the local API, which binds loopback (0009); bearer tokens on the policy's port (0061) |
| Parties | None: one simulator, one store |

### Work still done in the API's process (rule 5's debt)

- A live playback, for `/view`: computing days ahead in a thread.
- A position's scene: a seek restores the nearest checkpoint and works the day on,
  1.0 to 1.5 s a day (P17.1), in the API's simulator.
- The same run all off, which the house's chart draws beside a run and its sensors
  and probes read beside theirs: no checkpoint holds it, so the first far moment
  asked of it works it from its start, about 95 s of a core for Day 87 of
  `tomgro_house` on an idle machine. It is kept after that, 341 B a step, 59 MB for 120 days, at most
  `KEPT_RUNS` of them. The chart does not wait for it, and it stops when the page
  leaves it, what it worked out kept.

## Measurements

**Method.** One machine (Apple M2, 8 cores, 8 GB), Python 3.14, commit `28701e05`.
Two whole runs at once, each in a worker through the scheduler, one seed each, the
store on the machine's disk. Other work shared the machine (load 6 to 22), so **the
times are upper bounds**; the sizes are exact. Memory is `ps` every 5 s, so a
shorter peak can be missed.

| | Reference greenhouse (32 plants) | `tomgro_house` (by area) |
| --- | --- | --- |
| Simulated | 120 days | 120 days |
| Wall time, under that load | 20 min | 16 min |
| Kept | 20.6 MB | 7.8 MB |
| of which checkpoints | 17.4 MB (84%) | 4.8 MB (61%) |
| of which records | 3.2 MB | 3.0 MB |
| Objects | 601 | 601 |
| A worker's peak memory | 331 MB | 299 MB |
| A worker's memory on the way | 94 to 320 MB, rising and falling | 139 to 295 MB |

**The list as a store grows.** `stored_runs`, which `GET /api/runs` calls: copies of
the reference run as hard links, three reads each, files in the operating system's
cache. Each epoch is 120 commits read and parsed and 601 sizes asked for.

| Runs in the store | One list |
| --- | --- |
| 12 | 0.3 s |
| 102 | 2.5 to 3.3 s |
| 1,002 | 26 to 29 s |

**What follows, by arithmetic and not measured:**

- A thousand seeds of the reference greenhouse: about 21 GB, and about 190 hours of
  one core at P17.1's 5.6 s a day, or a day on all 8 cores of this machine if memory
  and the viewer allow it.
- At 331 MB a worker, memory allows about twenty workers on 8 GB, so cores limit
  this machine first. A larger crop reverses that: P17.1 puts a checkpoint of
  10,000 plants at 650 MB of JSON by day 120, and its worker's memory has not been
  measured.
- Keeping a checkpoint every 7 days instead of every day would take the reference
  run from 20.6 MB to about 5.7 MB, and a seek from at most one day's work to at most
  seven, about 9 s. Not chosen here; the figure is why retention has a seam.

**Not measured:** a full disk (from the code, a worker's write fails, the epoch is
told `failed`, and if that write fails too its lease expires and it is told
`interrupted`); a worker past a memory limit; the memory of one more `Simulator` in
a process; `RLIMIT_AS` on macOS, which P18.3 must check before relying on it.

## Steps

| Step | What | Pull request | Status |
| --- | --- | --- | --- |
| P18.1 | An epoch is self-contained: the scenario and its recording written into the store when it is queued; a worker takes a store's address and an epoch; built and uploaded scenarios run and resume in workers with their own weather and site. No run id moves. | `feat(sim): an epoch carries what it needs to run` | Done: an epoch of a scenario that is not packaged names, in its manifest, its portable file under `scenarios/<digest>.json`, with its recording inside and checked to read back as the same configuration; its pace is in the manifest too, so that `work` takes a folder's path, a run and an epoch. A simulator started on the store registers these files as it does the uploaded ones. An epoch from before this, of a packaged scenario, resumes as it did; of another, it is given its file if this simulator knows the scenario as the run it is, and is refused in words if not. A run of a draft named as a registered scenario, as a draft opened from a file is, stays under its site and weather unless it asks for others. Not delivered: a packaged scenario is not written, since every simulator has it; a worker's simulator has the default authorisation and no crew; a file stays when the last epoch naming it is deleted |
| P18.2 | Counted: the usage object at each commit, outside every digest; a failed epoch's reason; the list reads them, and its cost is measured again against the table above. | `feat(sim): an epoch says what it used and why it failed` | Planned |
| P18.3 | Limited: `Limits` from a file and the server's options; refusals for waiting runs and free disk; epochs ended by bytes, memory or time, keeping what they committed; workers at a lower priority. | `feat(sim): a simulator's runs have limits` | Planned |
| P18.4 | The store's *create unless it exists*, for a folder; leases and claims use it, which closes the window above; the queue rebuilt from `queued` manifests after a restart, so that a waiting run survives one. | `feat(sim): a claim on an epoch needs no lock` | Planned |
| P18.5 | The viewer: what a run used and why it failed in the runs dialog; workers busy, runs waiting and free disk on the landing page; a refusal in words. | `feat(viewer): what the runs use, and why one was refused` | Planned |
| P18.6 | The QA scenario below, run and recorded. | `test: runs within their limits` | Planned |

P18.1 comes first, because the viewer's moving to workers needs it. P18.2 to P18.4
can follow in any order.

## Acceptance criteria

- A scenario built in the builder and one uploaded from a file each run in a worker,
  are killed, and resume, ending with the digests of an uninterrupted run and the id
  they were queued under. Their own weather and site are honoured.
- Every id, digest and golden file of an existing run is unchanged.
- A run past each limit ends or is refused as the table in 0067 says, with the limit
  in its reason, and what it committed can be read.
- A list of 1,000 runs takes less than 1 s on the machine above.

## Final QA scenario

On one machine, with no change but the limits file: ask for 300 runs of a short
scenario with room for 200, and see 100 refused in words. Run them with a viewer
replaying one, and record that the viewer's frame rate and the API's answers hold.
Fill the disk to the floor, and see the next run refused. Give a worker a memory
limit it passes, and see its epoch `failed` with the reason, readable, then resumed
after raising the limit. Restart the server mid-batch, and see the waiting runs still
waiting and the running ones `interrupted`, resumable.

## Out of scope

Everything in 0067's *Not built now*: accounts, an object-store backend, workers on
other machines, a catalogue, retention, fairness between parties.

## Open questions

1. **The defaults.** 200 waiting runs and a 2 GB floor are judgements, not
   measurements. A training batch would raise the first; a small disk, the second.
2. **An epoch's budget in days or in time.** Time is what a machine feels, but a limit
   in time makes an epoch's end depend on the machine. It ends the run and does not
   change its records, so this design takes time; a limit in days is a smaller,
   reproducible alternative.
