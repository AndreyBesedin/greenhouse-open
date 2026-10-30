# 0064: A run's crop steps at its model's step, not the run's day

**Status:** Accepted
**Date:** 2026-10-30

## Context

A run's clock is seconds from its start, its start date's midnight at its
site (decision 0028, P09.2), and its climate advances by steps of its own.
Its crop does not: every model of it lives a day at a time.

- **The models:** a model grown plant by plant lives a plant's day
  (`CropRung.live_day`, decision 0024); a model grown by area lives a
  scope's day, given it hour by hour (`AreaRung.live_day`, `DayCourse`,
  decision 0062).
- **The run** keeps a crop's states by day (`core/crop_days.CropDays`), and
  the crop at a moment is the one that has lived the days ended by then
  (`core/clock.days_ended`): the viewer, a plant's panel and the walk's
  truth all read it so.
- **Crop work** is carried out at a day's start only
  (`runs.crop_moment_refusal`, the gateway's `why_not`). Decision 0046
  recorded it as the simulated executor's limit, and crop work within the
  day as a project of its own.

Since decision 0062, a model grown by area is given its day hour by hour,
so it can integrate within the day. What the day still prevents:

- a crop's state between midnights: a model whose state moves within the
  day is seen as it was at the day's start;
- crop work at any other instant, which a policy deciding at its own
  cadence (P15) may plan;
- a model integrating at its own step, such as a dynamic model like
  Vanthoor's (decision 0060), whose state the run should keep and show
  hour by hour.

What weighs on the choice: a run's id, its replay's day digests, its kept
opening day and its checkpoints must not move for the models it has; and
the crop at an instant must be the same whoever asks for it, whenever and
however often.

## Decision

1. **A model declares its step,** a whole divisor of a day: a day, an hour,
   a quarter of an hour. The run advances each of the model's instances
   step by step from the run's start, on that grid alone, never on the
   instants anyone asks about. Within a step, a model integrates as it
   needs; how, and with what tolerances, is part of its version.
2. **Between its steps, a crop is as at its last.** At an instant, a crop
   has lived the steps ended by then, as it has lived the days ended by
   then today. A model whose state must move between its steps takes a
   shorter step. So the crop at an instant is the same whoever asks for it,
   whenever and however often.
3. **Crop work at a boundary of the model's step:** a crop action is
   carried out at a boundary of its model's step after the first, after
   that step's own crop work, in the plan's order. The run's plan check and
   the gateway ask the model's step, not the day. Decision 0046's limit,
   crop work at a day's start only, becomes the case of the models whose
   step is a day.
4. **Drivers per step, through decision 0062's profiles:** the run gives an
   instance its step's course, at the resolution its model declares and its
   profile gives: an hour, from `house_hours`, today. A model whose step is
   shorter than its profile's resolution is refused, naming both.
5. **A crop grown plant by plant keeps a day's step,** as decision 0024's
   contract has it. A shorter step for it is a change to that contract, and
   a decision of its own.
6. **Every crop meets the day:** since a step divides a day, each model's
   grid passes every midnight. Checkpoints, taken at a day's start, the
   replay's day digests, the kept opening day and the crop walk's daily
   moment keep their days.
7. **The crop is worked to an instant step by step:** a playback's day, or a
   barrier of P15's experiment runner. It reads the air's course, one way
   (decision 0062). When a model gives the air its fluxes, crop and climate
   meet at the crop's steps' boundaries, through the climate decision that
   takes them.

## Consequences

- **Today's models declare a day:** the organ and simple crops, and the
  models grown by area so far, Reduced-State TOMGRO among them (#416). No
  run id, replay digest, kept opening day or checkpoint of theirs moves.
- **A model of a shorter step** costs a step's work per step: an hourly
  model, 24 a day. A run keeps a few of its steps' states, as it keeps a
  few days' today, and lives the others again from what it experienced.
- **A checkpoint** keeps a crop's state at a day's start and what it
  experienced on each step before it. Its format moves when a model of a
  shorter step is first kept, and still reads those of a day's step.
- **The run's clock does not change:** its days are 86,400 s from its
  start's midnight, so through a daylight-saving change they keep the start
  date's offset from UTC. Schedules in the site's civil time, with days of
  23 and 25 hours, would move the climate's schedules and run ids, and are
  a decision of their own if a scenario needs them.
- **What a crop's state is between its steps** is the state at its last.
  Interpolating it, or integrating it to the instant without keeping it, is
  a capability a model may declare later, if a model needs it.
- **Worth revisiting** if a model needs a step that does not divide a day,
  or if crop work within a plant's day is needed of a model grown plant by
  plant.
- [P16](../roadmap/p16-crop-at-its-models-step.md) carries it out.
