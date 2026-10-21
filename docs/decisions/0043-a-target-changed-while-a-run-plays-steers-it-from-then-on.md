# 0043: A target changed while a run plays steers it from then on

**Status:** Accepted
**Date:** 2026-10-21

## Context

The QA of 2026-10-21 ([#274](https://github.com/AndreyBesedin/greenhouse-open/issues/274))
asked for the house's air temperature target to be set while the reference
greenhouse's run plays: from the viewer, and from a platform that reads
the run as a consumer (decision 0040). Its thermostat holds the air at the
manifest's setpoints, 18 °C by day and 16 °C by night (decision 0042), and
nothing could change them.

P11 proposed targets as a run's inputs, set before it starts: changed,
they make another run. P11.1 made a scenario's thermostat the heating loop
of its climate controller (`climate.control`). Asked how a change should
act while the view follows the run played back (decision 0041), the user
chose **from the moment it is set**, as a climate computer's setpoint is
changed, rather than starting the run over. Asked how a platform should set
one, the user chose **through the simulator's API**, as the viewer does,
with no change to the consumer interface, which a consumer reads and never
writes.

A consumer keys what it stores by run, epoch and record id, and the
interface's rules are that records extend and are never rewritten, and the
clock never steps back (decision 0040). A run's identity is a digest of
what it is made of (`fields.air_through_a_run`).

## Decision

- **A target change is a run's input at a moment.** A run may change its
  heating setpoint by day or by night (`heating_day`, `heating_night`)
  from a moment on, on the minute, where the house's air is worked from:
  `&targets=3600:heating_day:24` on every route that makes or keeps a run,
  read with the run (`RunRequest.targets`). Changes keep their order, and
  the latest to each target holds. They are part of the run's schedule
  (`climate.commands`), so that a run under other changes is another run,
  the same as the first until the first change one makes and the other
  does not, as with commands. The thermostat heats to the targets in force
  (`climate.thermostat`), switching exactly as before.
- **Checked as commands are:** a target the scenario's controller does not
  have, a scenario with no heating loop, a setpoint outside 0 to 40 °C, a
  moment off the minute or outside the run, is refused with the reason.
- **A run that changes no target keeps its identity** from before this
  decision. A run that does is another run, with an identity of its own.
- **Checkpoints keep the changes before their day,** in checkpoint format 3.
  A format 2 checkpoint, whose run changed no target, is read as one.
- **A playback's run is steered while it plays.** `POST
  /api/scenarios/{id}/playback/targets?targets=heating_day:24` changes the
  targets of the run the scenario's playback plays, from its clock's next
  minute on. Anyone who can reach the API may, as for every other route:
  it answers only on its machine and has no users (decision 0009).
- **The same run and epoch.** The playback's run id names its epoch's run as
  started, and the changes its epoch made are part of its state
  (`PlaybackState.targets`), each its moment, target and value. Its records
  from the change on come from the run with the change, named by the same
  run id. Records before the change are the same in both runs, so nothing
  delivered is rewritten. Its clock waits at the change's minute until the
  day it falls in is worked out again under it. A restart is a new epoch of
  the scenario's own run, without the changes.
- **A viewer following the run learns of a change from the playback's
  state,** and passes its changes as `&targets=` when it asks for the run's
  moments, as it passes the layout, so that it draws the run played.
  A platform that sets a target reads the same state.
- **Targets are not records.** The consumer interface carries no new type:
  a consumer sees a change's effect in the air's readings and in the heat
  the heaters give, and the platform that made the change knows it.

## Consequences

- The viewer's Targets panel and a platform need nothing more than the
  routes above: one sets a target while following, the other when it
  decides to, and both read the targets in force from the playback's state
  or the equipment route (`thermostat.day_c`, `night_c`).
- Within an epoch, a run id no longer names one deterministic run by
  itself: a steered epoch is its run id and its target changes. A consumer
  that replays an epoch must read those changes from the playback's state.
- Venting and humidity targets (P11.2–P11.5) become target changes in the
  same way, once their loops run.
- Worth revisiting if a consumer needs the changes as records, which would
  be a protocol change, or if more than one party sets targets on one run
  and the API needs to say who did.
