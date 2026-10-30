# P16: A run's crop at its model's step

**Status:** accepted: the design below, with decision
[0064](../decisions/0064-a-runs-crop-steps-at-its-models-step-not-the-runs-day.md),
which this document's pull request records. Part of the
[simulator roadmap](README.md).

## Goal

A model of the run's crop steps at the step it declares, a day or a
whole divisor of one, rather than at the run's day. The run keeps its
states by that step, shows the crop at an instant as the steps ended by then
have it, and carries crop work out at its step's boundaries. The models the
run has keep a day's step, and nothing of theirs moves.

## Where the day is built in

- **The models:** `CropRung.live_day` (decision 0024) and
  `AreaRung.live_day`, whose day is given hour by hour (`DayCourse`,
  decision 0062).
- **The run's crop:** `core/crop_days.CropDays` keeps states by day; its
  growths (`PlantGrowth`, `AreaGrowth`) work a day out (`lived`,
  `next_day`).
- **The drivers:** `services/crop.py` gives a plant the house's air through
  its day (`mean_between(day * DAY_S, (day + 1) * DAY_S)`), and
  `core/drivers.house_hours` gives a scope its day's 24 hours.
- **The crop at a moment:** `days_ended(time_s)` in `services/crop.py`
  (the scene, a plant), `services/checkpoints.py`, `services/run_state.py`
  and the walk's truth (`ground_truth.py`).
- **Crop work:** `runs.crop_moment_refusal` and the gateway's `why_not`
  refuse a crop action at any instant but a day's start.

## Design

### A model's step

- A crop model declares its step, `step_s`, a whole divisor of a day. A
  step that is not one is refused when the model is registered.
- `CropDays` keeps a crop's states by step, from the run's start: the first
  step's, the latest worked out's, and a few last asked for, as it keeps
  days today. It lives the others again from what the crop experienced on
  each step. A day is a view of its steps: day `d` is step
  `d × steps_per_day`.
- A growth works a step out (`lived`, `next_step`): for a model of a day's
  step, exactly as it works a day out today.

### Drivers per step

- `AreaRung` declares its step and lives one (`live_step(state, course)`),
  given its step's course: its profile's hours from the step's start
  (`StepCourse`, which `DayCourse` becomes).
- A profile declares its resolution: `house_hours`, an hour. A model whose
  step is shorter than its profile's resolution is refused, naming both. A
  finer profile is a profile of its own (decision 0062).
- A model grown plant by plant keeps a day's step and its day's
  `LocalEnvironment` (decision 0024).

### The crop at an instant

- `core/clock.steps_ended(time_s, step_s)`: the steps a crop has lived by a
  moment, as `days_ended` is for a day's step.
- The scene, a plant's panel, the light, a checkpoint, the run's state and
  the walk's truth read the crop at the steps ended by their moment. For a
  model of a day's step, that is the day's start, as today.
- The crop's states depend on its grid alone, never on the moments asked
  about: a test asks at many moments, in any order and any number of times,
  and compares each with a run nobody asked about.

### Crop work at a step's boundary

- `runs.crop_moment_refusal` and the gateway's `why_not` and `earliest` ask
  the model's step: a crop action is carried out at a boundary after the
  first, and refused between two, naming the step.
- A crop's planned actions are kept by step (`crop_days` in
  `services/runs.py`), carried out after that step's crop work, in the
  plan's order.

### Checkpoints and the experiment runner

- A checkpoint, at a day's start, keeps a crop's state and what it
  experienced on each step before. Its format moves when a crop of a
  shorter step is first kept, and still reads those of a day's step.
- P15's experiment runner works the crop to each barrier step by step, as a
  playback works it to each day it publishes. Neither waits for the other.

## What does not change

- The run's clock: its days are 86,400 s from its start's midnight
  (decision 0028).
- The contract of a model grown plant by plant: a day at a time (decision
  0024).
- The crop walk's daily moment, and what it measures of a crop of a day's
  step.
- The action format and the gateway's contract (decision 0046): only the
  instants at which a crop action is carried out move, with the model's
  step.
- No packaged scenario's run id, replay digest or kept opening day moves,
  and every checkpoint written before P16 is read as before.

## Steps

| Step | Scope | Pull request | Status |
| --- | --- | --- | --- |
| P16.1 | A crop's step: `CropDays` keeps a crop's states by step, a whole divisor of a day, its days a view of them; growths work a step out; the crop registration declares the step, a day for every model today; `core/clock.steps_ended`. No behaviour changes. | `refactor(sim): a run's crop keeps its states by its model's step (0064)` | Planned |
| P16.2 | A model grown by area at its own step: `AreaRung.step_s` and `live_step`, `StepCourse`; a profile's resolution, and the refusals; a test canopy of an hourly step; the checkpoint format for a crop of a shorter step. | `feat(sim): a crop grown by area steps at its model's step (0064)` | Planned |
| P16.3 | The crop at an instant: the scene, a plant, the light, the checkpoint, the run's state and the walk's truth read the steps ended by their moment; the test that asking never changes the crop. | `feat(sim): a run's crop at an instant, as its steps have it (0064)` | Planned |
| P16.4 | Crop work at a step's boundary: the plan's check, the gateway's `why_not` and `earliest`, and planned actions kept by step, from the model's step; refusals naming it. | `feat(sim): crop work at a boundary of its model's step (0064)` | Planned |
| P16.5 | The plant model guide says how a model declares its step; the QA scenario below, run and recorded. | `docs: a crop model's step, and P16's QA` | Planned |

## Acceptance criteria

- No packaged scenario's run id, replay digest or kept opening day changes,
  and checkpoints written before P16 are read as before.
- A test canopy of an hourly step, and one of a day's step whose day adds up
  the same hours, agree at every midnight.
- A crop asked for at any moments, in any order and any number of times, is
  at each the state after the steps ended by then, and its last day's state
  is a run's nobody asked about.
- A model whose step does not divide a day, or is shorter than its
  profile's resolution, is refused, saying why.
- A crop action between two of its model's step boundaries is refused,
  naming the step. One at a boundary after the first is carried out after
  that step's crop work, in the plan's order, and replayed the same.
- A checkpoint of a crop of an hourly step, taken at a day's start, resumes
  to the states of a run that never stopped.

## Final QA scenario

On the reference greenhouse, whose organ crop keeps a day's step, through
the viewer and the local API:
1. Its run id, its replay's day digests and its kept opening day are those
   before P16.
2. At 13:00 on its day 30, the crop drawn and a plant's panel are the crop
   at that day's start.
3. A harvest planned for 09:00 is refused, naming the organ model's step; at
   the next day's start, it is carried out, and its outcome is in the
   outcome log.

In the process, with the test canopy of `greenhouse_sim/tests/test_area_crop.py`
(`Canopy`) given an hourly step, grown on the reference greenhouse's rows as
that test grows it:
4. Its canopy asked for at 09:00, 09:30, 10:00, 09:00 again and 10:00 again
   is, each time, its state after 9, 9, 10, 9 and 10 of the day's hours.
   Its state at the day's end is that of a run nobody asked about.
5. A checkpoint at the next day's start is taken, and the run resumed from
   it gives the same states.
