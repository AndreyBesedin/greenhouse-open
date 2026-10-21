# P10: A consumer's interface to a running simulation

**Status:** done: P10.1 to P10.4, and its QA scenario, run on 2026-10-20
([below](#qa-scenario-run-on-2026-10-20)).
Part of the [simulator roadmap](README.md).

## Goal

Let a program outside the simulator follow a run as it advances, reading
what its sensors report and what happens in it, through an interface that
belongs to the protocol rather than to the simulator, so that the same
program later reads a real greenhouse. The simulator stays what it is: a
tool that runs on its own, shows people its world, and now also serves a
consumer the observed side of it.

## Dependencies

P06 (the observation log in delivery order), P09 (the reference scenario
and its run). The protocol's records and conformance checks.

## Direction

- **The interface is the protocol's** (decision 0040). The simulator
  implements it; a client depends on `greenhouse_protocol` alone.
- **Observed records only.** The consumer's routes are a surface apart from
  the viewer's API, and reach no truth, no model state, no scene and no QA
  data (decision 0036).
- **One run, one world.** What the viewer shows and what a consumer reads
  come from the same run, seed and clock. If a unified live rich run is
  not practical in time, a deterministic precomputed rich run played back
  to both is the coherent alternative.
- **A season that changes.** Weather that varies with the date and the
  day, a heater on a simple explicit rule, and modeled energy published
  as modeled, with units and assumptions written down.

## Steps

| Step | What | Status |
| --- | --- | --- |
| P10.1 | The consumer interface in the protocol: routes, payloads, cursor and epoch rules, conformance checks, and a recorded exchange as the fixture ([#233](https://github.com/AndreyBesedin/greenhouse-open/issues/233)) | Done |
| P10.2 | One coherent run for the viewer and the consumer: a measured spike of a unified live rich run against precomputed playback, and the choice ([#234](https://github.com/AndreyBesedin/greenhouse-open/issues/234); decision 0041: a precomputed rich run played back against one clock) | Done |
| P10.3 | Seasonally varying weather, a thermostat with hysteresis on the heater, and modeled heating energy as observations ([#235](https://github.com/AndreyBesedin/greenhouse-open/issues/235); decision 0042) | Done |
| P10.4 | The simulator serves the consumer interface from a running scenario, read-only, bound to loopback ([#236](https://github.com/AndreyBesedin/greenhouse-open/issues/236)) | Done |

## Acceptance

- A client built against the recorded exchange reads a running scenario
  through P10.4 without a change.
- A consumer's records and the viewer's frames name the same run, epoch
  and simulated instant.
- Nothing a consumer can reach is true rather than observed: the
  dependency test keeps `ground_truth` and the sensors' truth out of the
  consumer's module, and a test reads every consumer route and finds only
  the protocol's records.
- The QA scenario: the reference greenhouse running in the viewer in one
  window, and a consumer following it in another, through 80 days.

## QA scenario, run on 2026-10-20

The reference greenhouse was played back from its start at `main` 3045700
(`uv run api --play reference_greenhouse --hold --play-seconds-per-day 8`).
The viewer followed it in a browser
(`?scenario=reference_greenhouse&field=climate&follow=1`), and a script
consumer polled `/consumer/v1` every 2 s, through 80 days:

- **One run, one epoch, on both sides throughout:**
  `reference_greenhouse-climate-76516b75`, epoch 2. The viewer showed no
  "another run" alert, no moment that failed and no page error.
- **What the consumer read:** 310,611 observations in 418 polls. Every one
  named the run, and none was delivered after the clock's `simulated_now`.
  They cover every sensor's type, the crop's walk (2,560 each of fruit
  counts, ripe mass and height) and 1,920 hourly heating increments. There
  were no events: the first harvest is on day 91.
- **The view trails the clock while it draws the air,** whose 3D field takes
  seconds a moment
  ([#198](https://github.com/AndreyBesedin/greenhouse-open/issues/198)).
  With the climate field drawn:
  - at 8 s a day, the moment drawn was 45 h behind the clock at the
    median, and 105 h at most;
  - at 30 s a day, 14 h behind, 18 h at most.

  Without the field, at the default 10 s a day, the scene stayed on the
  clock's day, 1.5 days behind at most. A view shown beside a consumer
  plays at 30 s a day or more with the air drawn, or follows without it.
