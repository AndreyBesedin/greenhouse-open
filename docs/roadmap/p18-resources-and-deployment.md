# P18: Resources counted and limited, and a run that can move

**Status:** accepted, in progress (P18.1 to P18.4 are done): the design below, with decision
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

**The list after P18.2.** The same method and machine, on one reference run computed
by a worker with its report. "Before" is commit `bf8758ae`, with no report in the
copies, read in the same hour as the others; "after" is commit `4567d44c`; "from before
reports" is that commit's code on the copies with no report. Load 4 to 50, so these are
upper bounds too; each cell is the range of three reads. Without its folder listing
made cheaper (`os.listdir` and no `Path` for each entry), 1,002 runs took 1.5 to 1.6 s.

| Runs in the store | Before | After | Epochs from before reports, after |
| --- | --- | --- | --- |
| 12 | 0.5 to 0.8 s | 0.005 to 0.006 s | |
| 102 | 3.3 to 5.3 s | 0.046 s | |
| 1,002 | 31 to 31.5 s | **0.47 to 0.55 s** | 34 to 46 s |

**A list of 1,000 runs takes less than 1 s, on this machine, for epochs that have a
report: the criterion is met.** `GET /api/runs` at 1,002 runs, the sorting and the JSON
of its 414 kB included, took 0.54 to 0.61 s at load 40. An epoch costs its manifest,
its report and a listing of three folders, whatever its length, and the three
listings are most of it.

**A store of epochs from before reports gains once a command has run on it.** Nothing
but a walk knows such an epoch's size, so it is walked, as it was, on each list, and a
read writes nothing. An epoch resumed from then on has a report; one told `interrupted`
as a server starts gets one too; one that ended before stays as it is until
`python -m greenhouse_sim.usage_reports <the store's folder>` gives it one.

| 1,002 epochs from before reports | Load 13 to 30 | Load 21 to 100 |
| --- | --- | --- |
| The list, before the command | 61 to 72 s | 69 to 107 s |
| The command | 58 s | 79 s |
| The list, after it | **0.42 to 0.45 s** | 0.49 to 0.54 s |
| The command again, which writes nothing | 0.3 s | 0.4 s |

The same method, except that each copy's 120 commits are files of its own and not hard
links, since a commit names its checkpoint under its run's folder and a copy is
otherwise found damaged. The list answers the same before and after, each field of each
of the 1,002 epochs compared, and no other file's inode, size or time of writing moved.

**A report's cost and its figures.** The same run reported 120 days computed, 120
commits, 20,647,025 bytes kept, 1,357 s of CPU and a peak of 328 MB, against the 20.6 MB
and 331 MB (`ps`, every 5 s) measured above; in 44 minutes of wall time at load 20 to
130. A report walks the epoch's sizes: 22 ms at 601 objects, the last commit's,
so about 1.3 s across the run's 1,357 s of CPU, or 0.1%.

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
`interrupted`); the memory of one more `Simulator` in a process. A worker past a memory
limit, and `RLIMIT_AS` on macOS, are in "What P18.3 limits" below.

## Steps

| Step | What | Pull request | Status |
| --- | --- | --- | --- |
| P18.1 | An epoch is self-contained: the scenario and its recording written into the store when it is queued; a worker takes a store's address and an epoch; built and uploaded scenarios run and resume in workers with their own weather and site. No run id moves. | `feat(sim): an epoch carries what it needs to run` | Done: an epoch of a scenario that is not packaged names, in its manifest, its portable file under `scenarios/<digest>.json`, with its recording inside and checked to read back as the same configuration; its pace is in the manifest too, so that `work` takes a folder's path, a run and an epoch. A simulator started on the store registers these files as it does the uploaded ones. An epoch from before this, of a packaged scenario, resumes as it did; of another, it is given its file if this simulator knows the scenario as the run it is, and is refused in words if not. A run of a draft named as a registered scenario, as a draft opened from a file is, stays under its site and weather unless it asks for others. Not delivered: a packaged scenario is not written, since every simulator has it; a worker's simulator has the default authorisation and no crew; a file stays when the last epoch naming it is deleted |
| P18.2 | Counted: the usage object at each commit, outside every digest; a failed epoch's reason; the list reads them, and its cost is measured again against the table above. | `feat(sim): an epoch says what it used and why it failed` | Done: `usage.json` beside the manifest, written after each commit and as the epoch ends, and `reason` in the manifest, both in the answer of `GET /api/runs`; see "What P18.2 counts" below. An epoch kept before this is given its report once, by `python -m greenhouse_sim.usage_reports <folder>`. Not delivered: the viewer shows neither (P18.5); a list does not see a file lost from inside a day's folder, only opening the epoch or asking it to resume does, and each refuses in words; until that command has run, an epoch kept before this costs a list what it always did |
| P18.3 | Limited: `Limits` from a file and the server's options; refusals for waiting runs and free disk; epochs ended by bytes, memory or time, keeping what they committed; workers at a lower priority. | `feat(sim): a simulator's runs have limits` | Done, in two pull requests: see "What P18.3 limits" below. Not delivered: a playback in the API's process has no limits; a worker's look at its memory is a thread, which a long call that holds the interpreter delays; the viewer shows neither a refusal nor a limit (P18.5) |
| P18.4 | The store's *create unless it exists*, for a folder; leases and claims use it, which closes the window above; the queue rebuilt from `queued` manifests after a restart, so that a waiting run survives one. | `feat(sim): a claim on an epoch needs no lock`; `feat(sim): a run waiting survives a restart` | Done, in two pull requests. **Claims:** `ObjectStore.create` makes an object unless one exists, and of any callers at once tells exactly one that it did: a promise of the store's interface, which a store of objects gives as a conditional write and a folder as a hard link of a whole file. A worker claims an epoch before it does anything to it, by creating `leases/{number}.json`, the number after a newest claim that is not fresh, so that of all who read one claim one makes the next, and a number already passed is refused to one who comes late. A holder writes only its own number, and letting go creates the next, so that a thread stopped between reading and writing takes nothing from a later holder: that closes the window above. Telling an epoch `interrupted` is a claim too, so that it and a worker taking the epoch up are told apart. A worker that finds its epoch another's, or no longer waiting, exits saying so and nothing is told of the epoch. A crash costs 30 s: its claim expires, and the next number is free. An epoch's `lease.json` from before claims is believed until it expires. Measured, at load 11 to 26 on the machine above: 8 processes racing, each of 2,000 `create` rounds had one winner and each of 200 claimed epochs one holder; a `create` takes 0.47 ms against a `put`'s 0.21 ms, a claim and its letting go 2.9 ms. Not delivered: a holder stalled past 30 s, as on a machine asleep, whose epoch is taken over is not stopped, and its writes still reach the store; a folder must be on a file system with hard links, and any other refuses its epochs with the file system's error (not run on one); the two small objects a working of an epoch leaves stay until it is deleted, and count in its size; epochs are still given their numbers by whoever starts them, one at a time. **The queue:** a scheduler stamps a manifest as it puts an epoch in line (`queued_at`, which no digest holds), and a simulator starting on a folder makes the queue again from those it finds, in that order (`scheduler.restore`), so that a run waiting survives a restart, a server closed included, which leaves what waits waiting; what a worker was computing is told `interrupted` if it is ended, as before. Its pace and its scenario's file are read from the store by its worker, as ever. An epoch whose worker lives, by its claim, whether `queued` or `running`, is left to it and counts against the limit on workers until its claim is no longer believed, when it is told `interrupted` if it had not ended. Of two workers given one epoch, as when a killed server's worker has not yet claimed it, one leaves, and the run is counted the same way. An epoch whose scenario this simulator cannot run, its file gone or its name unknown and no file kept, is told `interrupted`, and a request to carry it on says why. An epoch with no stamp, from before this or one that a process of its own was to take up, is found by `interrupted` as it was. One deleted from the store while it waits is passed over; the route still refuses to delete one that waits. A stop asked of one that waits takes it out of the queue, and one asked of a run counted so writes the request its worker reads; a request left in the store of one found waiting ends its worker at its first look. Measured: finding the queue over 1,000 epochs that ended takes 0.09 s. Not delivered: a worker a killed server had started and that has not yet claimed its epoch is not counted, so that the limit can be passed by it for the seconds until it claims or leaves; each server on one store keeps its own limit; a deleted epoch stays in `Scheduler.waiting` until its turn; the order is that of the machine's clock |
| P18.5 | The viewer: what a run used and why it failed in the runs dialog; workers busy, runs waiting and free disk on the landing page; a refusal in words. | `feat(viewer): what the runs use, and why one was refused` | Planned |
| P18.6 | The QA scenario below, run and recorded. | `test: runs within their limits` | Planned |

P18.1 comes first, because the viewer's moving to workers needs it. P18.2 to P18.4
can follow in any order.

From P13, for its open steps to weigh: a playback's gateway bounds each plan, at 1,000
occurrences, but not how many plans a run holds, and no route serves its limits
([P13.7](p13-actions.md#settled-in-p137)); and under load a followed run's view fell up
to 9 hours behind a paused clock ([P13's final QA](p13-actions.md#recorded-at-88f35bae)).

### What P18.2 counts

`usage.json`, beside the manifest, is written after each commit and as the epoch
ends. It is in no digest, and nothing that decides a trajectory reads it.

| Figure | What it says | Across a resume | In a fork |
| --- | --- | --- | --- |
| `bytes_kept` | The epoch's objects, the report aside and the scenario's shared file not included | Worked out afresh from what it holds | Its own, the state it inherits included |
| `days_computed` | From where it begins to its last commit | Worked out afresh: a day counts once, and a day worked out and never committed not at all | From the state it inherits, none of its parent's |
| `cpu_s` | Seconds of a core of its workers' processes, each as far as it last reported | Added up, work a crash then lost included, since the machine gave it | Its own workers' only |
| `peak_memory_bytes` | The most memory one of its workers held | The highest of them | Its own workers' only |

`cpu_s` and `peak_memory_bytes` are none if no process of its own ever worked the
epoch: a playback in the API's process, or a caller's `execute`, shares a process
with other work. An epoch that was resumed from before reports counts only the
workers since. Peak memory is `/proc/self/status` on Linux, since `ru_maxrss`
outlives an `exec` there and a worker would be told the peak of the server that
started it; elsewhere `ru_maxrss`, in bytes on macOS and KiB on the others.

**A failed epoch's reason** is `reason` in its manifest, which any client that lists
it reads. It is a service's own message, which is written for a client; or one
sentence for the kind of failure (out of memory, a full disk, the store unreadable
with its error's code, an object missing), or for any other the name of the
exception's class. An exception's text, which can hold a path or a value, and its
traceback stay in the worker's log. A worker killed outright has no chance to write
one: the scheduler seeing it gone, or its lease expiring, says `interrupted`, with no
reason.

**A list's `damaged`** changes. The list used to compare every object's name against
every commit, which is what it can no longer afford. It now compares how many
commits, day folders and checkpoints the epoch's folders hold with what its report
counted, and walks only an epoch that disagrees. A commit, a checkpoint or a whole
day lost is still seen. A single file lost from inside a day's folder is not, until
someone opens the epoch: `GET /api/runs/{run}/epochs/{n}` says so, and opening a
position is refused in words where a read would have answered 500. Asking it to resume
is refused in words as well, with a 409 and nothing changed in the store, since its
last commit alone would have let it go on and it would have stayed damaged. That check
lists the epoch's objects: 23 ms on the reference run's 601 at load 16, read commits
aside, and it is made once as a resume is asked for and once as its worker takes it up.

**Reports for epochs kept before them** (`python -m greenhouse_sim.usage_reports
<folder>`) adds `usage.json` to each epoch that lacks one, written as the store writes
every object, and touches no other object, so that no run id, digest or position moves.

- It leaves alone an epoch with a report, and one queued, running or with a lease. So it
  may run beside a server, and running it twice changes nothing. An epoch `running` that
  no one works gets its report as a server starts and finds it interrupted.
- `cpu_s` and `peak_memory_bytes` are none in what it writes, which the list and the
  routes answer as `null`: no worker measured them, and none is not zero. A worker that
  resumes the epoch counts its own from there. The viewer does not read them yet (P18.5).
- An epoch it cannot read fails alone, with the reason printed, and the rest go on. So
  does one whose report cannot be read, which is not written over, and one with an object
  missing that its commits name: a report would let a list count its folders and stop
  saying it is damaged, whereas with none a list goes on walking that one.
- It prints how many it wrote and skipped and each failure, and its exit code is 1 if
  any failed. It does not read objects for their digests (`verify`).

### What P18.3 limits

`Limits` is given to a `Simulator` as its authorisation is: the server takes `--limits
<file>`, JSON with any of the limits below, and an option for each that takes the place
of what the file says of it, `none` for no limit. A file or an option that is not limits
stops the server from starting, saying why.

| In the file | Option | Default | Past it |
| --- | --- | --- | --- |
| `workers` | `--workers` | 2 | The run waits |
| `waiting_runs` | `--waiting-runs` | 200 | A run asked for is refused |
| `free_disk_bytes` | `--free-disk-bytes` | 2 GB | A run asked for is refused |
| `store_bytes` | `--store-bytes` | None | A run asked for is refused |
| `epoch_bytes` | `--epoch-bytes` | None | The epoch ends at the commit past them |
| `worker_memory_bytes` | `--worker-memory-bytes` | Half the machine's, shared between the workers | The epoch ends |
| `epoch_cpu_s` | `--epoch-cpu-s` | None | The epoch ends |
| `epoch_wall_s` | `--epoch-wall-s` | None | The epoch ends |

**A refusal** is a 409 from every route that asks for a worker (a run, a resume, a fork),
written by the scheduler before anything of the run is, and it says which limit and the
figures, as "the disk of the run store has 1.2 GB free, and a run begins only with 2.0 GB
free: free some space, or lower that limit".

- A run a free worker takes at once does not wait, so that it is not refused for waiting.
  So with two workers free and room for 200, 202 are let in, and 98 of 300 are refused.
- What waits as a server starts keeps waiting if the limit has been lowered since; only
  what is asked for after that is refused. Workers a server before it left, more than its
  limit, leave no worker free and are not counted as waiting.
- A resume is asked about room first, before it finds the epoch interrupted or gives one
  from before P18.1 its scenario's file, so that a refusal writes nothing. One that could not
  be carried on anyway, asked for while there is no room, is told of the room.
- `free_bytes` is a store's operation, of which a store with no disk of its own says none,
  and then no run is refused for it. A folder not made yet says what its nearest parent's
  disk has free.
- `store_bytes` adds up the epochs' reports, which may lag a worker by a commit, the walk of
  an epoch with none, and what no epoch holds, such as the scenarios' files. It is read only
  when that limit is set.

**A worker runs at niceness 10** above whoever started it, from its first line, so that on
a machine it fills the API and a viewer are given a core first.

**What a refusal costs**, on the machine above at load 2 to 5, each the median of many: 9 us
for the checks asked of every run, of which 8 us is the folder's free space. With a limit on
the store's bytes, one more read of each epoch's report: 6.9 ms over 102 epochs, 64 ms over
1,002, under the lock runs are asked for under, so 300 runs asked for at once over 1,002
epochs spend 19 s on it. No commit, list or day of a worker is any different.

**An epoch ended by a limit** is `failed`, and its reason names the limit and the figures:
"it kept 21.0 MB, past the limit of 20.0 MB on what one run may keep: what it committed can
be read, and it can be carried on once that limit is raised". What it committed stands. It
can be read, forked, and carried on: alone of failures, as an `interrupted` epoch can, by
`past_limit` in its manifest. Its digests up to there, and all of them once it has been
carried on or forked, are those of a run never ended, since no digest holds a limit.

- What a worker keeps to, its `Budget`, is `budget.json` beside the manifest, written as the
  epoch is put in line, since a worker is given a store's address and an epoch and nothing else.
  Asked to resume, or found waiting by a server that has started, it is given the limits of
  now, which is how a limit is raised. An object of its own, so that a new server writes no
  claim and nothing over what a worker says of the epoch, and it counts in the epoch's bytes.
- Bytes are looked at in each commit, in the commit's report, and end it there: the commit
  stands. The commit of its last day ends nothing, since all its days are kept and it has
  finished.
- Memory and time are looked at by a thread of the worker's own, as it takes the epoch up and
  every 0.25 s after, which ends the process where it stands, between commits or in one. A
  commit is written last, so that this leaves what a crash does. Reading its objects, a resume
  throws away what a commit does not name.
- Bytes, CPU and wall time are the epoch's whole across its resumes: a resume is refused with a
  409 while what it has already used is past the limit, since it would end at once. Memory is
  each worker's, and a resume is let in: the next may hold less. `wall_s`, in its report beside
  `cpu_s`, counts from each worker's start, its pace too, and a machine asleep does not count.

**Memory, on each platform.** `RLIMIT_AS` cannot be relied on, and the limit is not built on it.
On macOS 27 on an M2 `setrlimit(RLIMIT_AS, ...)` is refused with `EINVAL` below what a process
has mapped: Python alone maps 488 GB, so 300 MB, 2 GB and 4 GB are all refused, and 600 GB is
taken and limits nothing. `RLIMIT_DATA` is refused the same way, and `RLIMIT_RSS` is the same
limit as `RLIMIT_AS` there. `ulimit -v`, `-m` and `-d` fail with it. On Linux `RLIMIT_AS` would be
taken, but it counts what is mapped and not what is held, and this has not been run. So a
worker looks at its own high-water mark on both, the figure its report gives: `VmHWM` on Linux
and `ru_maxrss` on macOS. That a peak is read means that nothing held between two looks is
missed; that a look is after the fact means that a worker can get past the limit before it is
ended:

| How a worker takes memory, limit 500 MB unless said | Held when it was ended, of two runs |
| --- | --- |
| 10 MB, as fast as it can | 603, 702 MB |
| 1.5 GB in one call | 742, 862 MB |
| 10 MB every 10 ms, limit 300 MB | 427, 427 MB |

The Linux path runs on CI only, not on this machine. A process ended so leaves any temporary
folder a commit had open, as a crash does.

**What it costs**, on the machine above at load 2 to 4. A run of 120 days of the one-plant box
through a real worker, in turn:

| | Wall time | CPU | Peak |
| --- | --- | --- | --- |
| No look at memory or time | 12.4, 12.5, 12.5 s | 13.0, 13.1, 13.2 s | 185 to 190 MB |
| With the look | 12.4, 12.5, 12.7 s | 12.9, 13.2, 13.5 s | 190 MB |
| At niceness 0, at this load, with cores free | 12.4, 12.6 s | 12.8, 13.3 s | |
| At niceness 10 | 12.4, 12.5 s | 13.1, 13.2 s | |

So neither is told from the noise between two runs. A look is 2.5 us, 10 us a second. A commit
is 32 ms with a budget and with none, the median of 100 on one store, since its bytes are in
the report it writes anyway. A list of 1,002 epochs takes 179 to 180 ms with `past_limit` in
each manifest and without it, and reads no budget. A worker reads its budget once. What the
priority buys on a machine it fills has not been measured: P18.6 records it.

Not delivered: a playback in the API's process has no budget and opens an epoch with none of
these checks, and its `--play` is not refused; each server on one store keeps its own count of
what waits; a look is a thread, so that a long call holding the interpreter delays it, and
the leases' thread with it.

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
