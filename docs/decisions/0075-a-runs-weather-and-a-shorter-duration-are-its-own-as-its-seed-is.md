# 0075: A run's weather and a shorter duration are its own, as its seed is

**Status:** Accepted
**Date:** 2026-11-08

## Context

P22.4 has a person start a run from a form that gives its duration and its
weather, besides its seed and its pace. Until now a run asked for
(`POST /api/scenarios/{id}/runs`) took only a seed, a layout and a pace: its
weather and its days were its scenario's (`scenario.schema.json`'s `weather` and
`duration_days`). P22's open questions asked whether a duration and a weather
make another scenario or stay a run's, as its seed is.

What is there already:

- **The seed is a run's.** It changes the run's identity and nothing of the
  scenario: it rides the weather's name (`default#7`, `SEED_MARK`), which is
  how every service that honours the weather honours it.
- **The weather is a run's in the by-moment services.** A `RunRequest` names a
  weather, its scenario's own when none, which the climate field, the
  sensors, the crop and the weather panel all take, and a scenario's summary
  lists the weathers it can be run under (`weathers`: its own, the presets,
  the recorded ones). A climate run's identity holds the weather's name, but
  that of a run whose air is its own airflow, a packaged layout that places no
  equipment, did not: its sensors read that airflow under any weather. Its
  crop grows in its climate run all the same, which the weather changes: a
  day of `tomato_compartment` under `cold_spring_day` has the same 1,280
  observations as under its own, and another checkpoint. Only the worker's run
  (`Playback`) and the epoch's manifest had no weather.
- **The duration is the epoch's already.** An epoch's manifest says how long
  its run lasts (`duration_s`), its progress is a part of it, a fork keeps it,
  and a replay's timeline ends there. The worker read its scenario's days
  instead, and the by-moment services check a moment against the scenario's
  days (`checked_moment`).
- **A scenario of one's own is the builder's.** A draft's run step sets its
  start, its days, its weather and its seed, and saving it makes a scenario
  under an identifier of its own (`CopyScenario`, P12.2).

## Options weighed

- **The weather and a shorter duration are the run's** (chosen). A weather is
  one of those the scenario lists, and changes the run's identity, as a seed
  does. Fewer days than the scenario's are the scenario's run cut short:
  causal, its days are those of the whole run, so they keep its identity, and
  an epoch of fewer days is an epoch of the same run that ends sooner. A
  longer season, another house or another crop is a scenario of its own,
  made in the builder.
- **Both make another scenario.** The route would write the scenario with its
  weather and its days changed, under an identifier derived from them, and
  start a run of that. A worker, a fork and a resume would need nothing new,
  since a built scenario already carries its file. But each derived scenario
  is listed beside the one it came from, its plants and sensors are named
  after another identifier, its runs are not the scenario's in the runs
  dialog, and a run of 10 days of the reference greenhouse would not be the
  first 10 days of its run, which it is.
- **The duration is the run's, longer too.** A longer run needs the
  by-moment services, which the replay draws its scene from, to be told the
  run's days for every moment past the scenario's, a recorded weather to last
  as long, and a crop that has its season to grow on past it. It is a
  scenario's change, which the builder already makes.

## Decision

- **A run is started under a weather and for a duration of its own:**
  `POST /api/scenarios/{id}/runs?weather=cold_spring_day&duration_days=10`,
  beside `seed`, `layout` and `seconds_per_day`. Each is optional, and its
  scenario's own when it is not given.
- **The weather** is one the scenario lists in its summary, by name alone;
  `default` names its own. A name with an override's or a seed's mark
  (`@`, `~`, `#`) is refused (400), a name the simulator does not have is not
  found (404). A weather other than its own makes another run, as a seed does,
  also of a scenario whose air is its own airflow, since its crop grows under
  it: else one run id would name two trajectories in the store. A run under
  its own, named or not, is the run it always was.
- **The duration** is whole days, from 1 to the scenario's own; more or fewer
  is refused (400), saying that a longer run is a scenario of its own. A run of
  fewer days is the same run, ended sooner: its identity, its first days'
  digests and its checkpoints are those of the whole run's.
- **The epoch keeps both,** so that its worker, a resume and a fork run as it
  was started: its manifest's `weather` (none for its own, as every epoch
  before) and its `duration_s`, where the worker ends it. A fork goes on under
  its parent's weather and to its parent's end. The runs listed
  (`stored_run.schema.json`) and a position over one (`position.schema.json`)
  say its `weather`, and the replay draws the scene under it.
- **The rest of a scenario is the builder's.** The form names the scenario's
  crop, and offers to make a new scenario from it, in the builder, for a
  longer season, another crop or another house.

## Consequences

- **Additive:** the route gains two parameters, and the manifest, a run
  listed and a position gain `weather`. No run id, digest or golden of a run
  under its own weather moves, and what 0.7.0 wrote is read as before.
  No `greenhouse_protocol` record changes, so the protocol's range is as the
  release sets it.
- **What moves:** the id of a run asked for under another weather of a
  scenario whose air is its own airflow (`tomato_compartment`, `airflow_box`,
  `sensor_lab` and such), which the viewer's by-moment views can ask for:
  its records name it as their source by another id, which the release's
  changelog says. A checkpoint is matched by what its run agrees with, not by
  its id, and no stored epoch had a weather before, so neither moves.
- **Easier:** a run's inputs are said in one place, its start, and repeated
  by asking the same again: the same seed, weather and days are the same run.
- **Harder:** an epoch under another weather than its scenario's says so only
  in its manifest, as one at another seed does: a reader of the store takes
  the weather from there, not from the scenario's file.
- **The by-moment services** still check a moment against the scenario's days,
  which the run's never exceed; a run's start date stays its scenario's.
- **Worth revisiting** if a longer run than its scenario's is wanted without a
  scenario of its own: then the by-moment services take a run's days, as they
  take its weather.

## Open for its review

1. **Whether a longer run than its scenario's** should be a run's too, rather
   than a scenario of its own made in the builder.
2. **Whether a run whose air is its own airflow** should rather stay one run
   under any weather, as it was, its epochs under another weather refused.
3. **Whether the weather's QA overrides** (its clouds and its wind's
   direction) should be a run's as well; they are refused for now.
