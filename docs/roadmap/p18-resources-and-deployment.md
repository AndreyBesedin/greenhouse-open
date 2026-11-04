# P18: Resources counted and limited, and a run that can move

**Status:** accepted, in progress (P18.1 and P18.2 are done): the design below, with decision
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
| Claims and leases | Written without an atomic create: the folder store leaves a window of two calls between checking an owner and writing |
| Authentication | None on the local API, which binds loopback (0009); bearer tokens on the policy's port (0061) |
| Parties | None: one simulator, one store |

### Work still done in the API's process (rule 5's debt)

- A live playback, for `/view`: computing days ahead in a thread.
- A position's scene: a seek restores the nearest checkpoint and works the day on,
  1.0 to 1.5 s a day (P17.1), in the API's simulator.
- The scenarios' opening days, loaded when the server starts.

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

**A store of epochs from before reports does not gain:** nothing but a walk knows such
an epoch's size, so it is walked, as it was, on each list, and shows `cpu_s` and
`peak_memory_bytes` as none. It is not rewritten by a read. An epoch resumed from then
on has a report; one told `interrupted` as a server starts gets one too; one that
ended before stays as it is until it is deleted. A store with 1,000 of them still
takes half a minute to list.

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
`interrupted`); a worker past a memory limit; the memory of one more `Simulator` in
a process; `RLIMIT_AS` on macOS, which P18.3 must check before relying on it.

## Steps

| Step | What | Pull request | Status |
| --- | --- | --- | --- |
| P18.1 | An epoch is self-contained: the scenario and its recording written into the store when it is queued; a worker takes a store's address and an epoch; built and uploaded scenarios run and resume in workers with their own weather and site. No run id moves. | `feat(sim): an epoch carries what it needs to run` | Done: an epoch of a scenario that is not packaged names, in its manifest, its portable file under `scenarios/<digest>.json`, with its recording inside and checked to read back as the same configuration; its pace is in the manifest too, so that `work` takes a folder's path, a run and an epoch. A simulator started on the store registers these files as it does the uploaded ones. An epoch from before this, of a packaged scenario, resumes as it did; of another, it is given its file if this simulator knows the scenario as the run it is, and is refused in words if not. A run of a draft named as a registered scenario, as a draft opened from a file is, stays under its site and weather unless it asks for others. Not delivered: a packaged scenario is not written, since every simulator has it; a worker's simulator has the default authorisation and no crew; a file stays when the last epoch naming it is deleted |
| P18.2 | Counted: the usage object at each commit, outside every digest; a failed epoch's reason; the list reads them, and its cost is measured again against the table above. | `feat(sim): an epoch says what it used and why it failed` | Done: `usage.json` beside the manifest, written after each commit and as the epoch ends, and `reason` in the manifest, both in the answer of `GET /api/runs`; see "What P18.2 counts" below. Not delivered: the viewer shows neither (P18.5); a list does not see a file lost from inside a day's folder, only opening the epoch does; an epoch kept before this costs a list what it always did |
| P18.3 | Limited: `Limits` from a file and the server's options; refusals for waiting runs and free disk; epochs ended by bytes, memory or time, keeping what they committed; workers at a lower priority. | `feat(sim): a simulator's runs have limits` | Planned |
| P18.4 | The store's *create unless it exists*, for a folder; leases and claims use it, which closes the window above; the queue rebuilt from `queued` manifests after a restart, so that a waiting run survives one. | `feat(sim): a claim on an epoch needs no lock` | Planned |
| P18.5 | The viewer: what a run used and why it failed in the runs dialog; workers busy, runs waiting and free disk on the landing page; a refusal in words. | `feat(viewer): what the runs use, and why one was refused` | Planned |
| P18.6 | The QA scenario below, run and recorded. | `test: runs within their limits` | Planned |

P18.1 comes first, because the viewer's moving to workers needs it. P18.2 to P18.4
can follow in any order.

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
position is refused in words where a read would have answered 500. Resuming is not
refused: it goes on from the last commit and leaves the epoch as damaged as it was.

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
