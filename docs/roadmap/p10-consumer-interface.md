# P10: A consumer's interface to a running simulation

**Status:** in progress: P10.1, P10.2 and P10.4 in review; P10.3 not started.
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
| P10.1 | The consumer interface in the protocol: routes, payloads, cursor and epoch rules, conformance checks, and a recorded exchange as the fixture ([#233](https://github.com/AndreyBesedin/greenhouse-open/issues/233)) | In review |
| P10.2 | One coherent run for the viewer and the consumer: a measured spike of a unified live rich run against precomputed playback, and the choice ([#234](https://github.com/AndreyBesedin/greenhouse-open/issues/234); decision 0041: a precomputed rich run played back against one clock) | In review |
| P10.3 | Seasonally varying weather, a thermostat with hysteresis on the heater, and modeled heating energy as observations ([#235](https://github.com/AndreyBesedin/greenhouse-open/issues/235)) | Not started |
| P10.4 | The simulator serves the consumer interface from a running scenario, read-only, bound to loopback ([#236](https://github.com/AndreyBesedin/greenhouse-open/issues/236)) | In review |

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
