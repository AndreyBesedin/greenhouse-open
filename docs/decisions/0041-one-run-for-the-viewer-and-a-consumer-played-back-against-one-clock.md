# 0041: One run for the viewer and a consumer, played back against one clock

**Status:** Accepted
**Date:** 2026-10-20

## Context

A consumer that reads a running simulation (P10, decision 0040 in
[#240](https://github.com/AndreyBesedin/greenhouse-open/pull/240), which
this record follows) and a person
watching it in the viewer must see the same run. As they stood, they would
not.

- **The viewer's live mode** (`services/live.py`) steps `SimulationEngine`,
  the simple daily models, and streams its scene.
- **The viewer's scenario mode** draws the rich run of the reference
  greenhouse. It shows the house's air through a climate run, the crop organ
  by organ, and the sensors' observation log, each worked out for whatever
  moment is asked for.

Records served from the first while the second is shown would describe
another world.

The rich run already has one identity and one clock. Its climate run names
it (`air_through_a_run`: `<scenario>-climate-<digest>` of its layout,
equipment, openings, commands, weather and daily commands), and its moments
are seconds from its start. Its observation log carries that identity as
each record's source, and the QA developer panel (`run_state`) reports it
with the run's instant. What it lacks is a clock that advances, and records
served only up to it.

Measured on the reference greenhouse, by its own schedule and weather, seed
42 (a laptop, one process):

| What | Cost |
| --- | --- |
| The house's air, a day | 1–3 s |
| The observation log, a day, 13 point sensors at 60 s (18.6k records, 7.4 MB of JSON) | 53–67 s; 9–13 s once a moment's air is worked out once for every sensor (#242) |
| The same log at a consumer's cadence of 300 s, from a playback (3,729 records) | 6 s a day, the air included, 47 kB compressed |
| The viewer's own day step: the 3D air, the crop and its scene | about 9 s (P09.8, #228) |

Two ways to put the clock in:

- **A unified live rich runner:** one thread steps the rich run in real
  time and publishes each moment, which the viewer and the consumer read.
  At 60 s per day of log, as it stood, no pace a demo can watch keeps up.
- **Playback of a precomputed rich run:** the run's records are worked out
  ahead, day by day, and a clock plays over what is worked out. The viewer
  draws the run at the clock's moment as it draws any moment, and the
  consumer reads the records delivered by then.

With the log at 6 s a day, the two differ in one thing only: whether the
clock may pass the records. A playback that works ahead of its clock on a
thread of its own is a live runner that never shows what is not worked out.

## Decision

- **A scenario's own run is played back against one clock**
  (`greenhouse_sim.services.playback`). A `Playback` works the run's days
  out on a thread of its own, from its start, ahead of a clock that plays
  at a pace, 10 real seconds a simulated day by default. The clock never
  passes the last day worked out: it waits there.
- **The run is the scenario's own:** its layout, weather and daily
  commands, nothing changed, which is what the viewer draws when nothing is
  changed. Its identity is the climate run's, as above. A command given in
  the viewer makes another run, which the playback does not follow.
- **One clock, said the same way to both.** A playback's state is its run's
  identity, its epoch, the instant its clock has reached (`simulated_now`)
  and that instant as seconds into the run (`time_s`, the viewer's `t`),
  its day, whether it plays and at what pace, and how far ahead its records
  are worked out. These are the fields of the consumer interface's
  `RunDescriptor` (decision 0040). The viewer asks for the run at `time_s`;
  a consumer reads what was delivered by `simulated_now`.
- **A restart is a new epoch of the same run** from its start, as decision
  0040 has it: the run is deterministic, so its records are the same again,
  and they are not worked out twice. A run played to its end stops there.
- **A consumer reads the point sensors at its own cadence**, 300 s by
  default: each sensor's own sample at that minute, noise and dropouts
  included, kept from its minute-by-minute samples (`observe`'s
  `every_s`). So the consumer and the viewer's sensor panel never disagree
  about what a sensor said. Camera frames are not records a consumer reads.
  A late reading is served in the day it arrived in.
- **A day's records are kept compressed** (gzip of their JSON), and read
  back a few days at a time, as asked for.
- **The API plays it**, as interface only: `GET
  /api/scenarios/{id}/playback`, and `POST .../playback/start`, `play`,
  `pause`, `restart` and `pace`. The consumer's routes (P10.4) read the same
  playback; the viewer follows its clock.
- **The simple live mode stays** for the scenarios it serves, but is not
  the reference greenhouse's live run.

## Consequences

- One run, one seed, one clock: a record a consumer reads and the frame
  the viewer draws at the same instant name the same run
  (`tests/test_playback.py`), and each reading is the one the viewer's
  sensor log has then.
- A season of 100 days is worked out in about 10 minutes, 4.7 MB kept, so
  it fits in memory. A playback started some minutes before it is watched
  plays at any pace. The viewer's own day step (about 9 s) runs beside it,
  on the same interpreter: a pace under 10 s a day may wait on both.
- The playback's records are the sensors' and the crop's
  (`services/crop_log`, P10.4): a walk through the crop at noon each day,
  and each harvest round as an event per plant picked, kept in a log of
  their own beside the observations. The heater's modeled energy is a
  record of the same run that a later step adds (P10.3).
- A restart of the API keeps only each run's last epoch, so a producer
  started again is a new epoch to its consumers (P10.4). Its records are
  not kept: a playback works its run out again. Writing them to disk is
  worth doing if a demo cannot wait those minutes.
- Worth revisiting if a run's day ever costs more than its pace, when a
  playback worked out entirely before it plays is the same design with its
  clock started last.
