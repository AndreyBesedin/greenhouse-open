# 0058: A climate controller switches each loop at its edge, from the house's air

**Status:** Proposed
**Date:** 2026-10-27

## Context

P11 gives a run a climate controller: loops that run its heater, vents,
fans and dehumidifier towards targets, in place of the clock's daily
commands ([P11](../roadmap/p11-climate-setpoints.md)). Its heating loop is
decision 0042's thermostat: the whole house's air switches the heater the
moment it reaches the band's edge, found from the air's exact course, and
the grid follows. P11.1 made the controller data, its loops checked
against each other, and left four questions open, with proposals: staged
vents or proportional ones; the house's true air or its sensors'
readings; fans with the vents or on a temperature of their own; and how
humidity is fought. P11.2 builds the house that decides every loop, and
answers them.

## Decision

- **One controller, several loops, each in steps, with hysteresis.** Each
  loop reads one quantity of the house's air and switches its devices
  between steps; every edge it switches at is a value of the air, with a
  band of positive width between switching on and off, so the air must
  cross a band between two switches of one loop, and time always moves on.
  There is no continuous controller.
- **The vents in stages.** A venting loop opens each stage when the air
  passes the venting setpoint plus the stage's offset, and closes it when
  the air falls back below that by its band; how many stages stand open is
  the loop's state. Stages keep the air exact: each is a moment the house
  finds, as it finds the thermostat's switch. A vent opened in proportion
  to the air would change at every instant.
- **Every switch at its edge.** Through a stretch, the house finds the
  first moment any loop's edge is reached, from the air's exact course, and
  switches that loop there. A temperature's edge, and the outside air's
  being drier enough, are found in closed form, each following one
  exponential; a relative humidity's edge, where the air's humidity ratio
  meets what air at its temperature then holds at that humidity, is
  bracketed and halved to a nanosecond. Two loops at one moment switch one
  after the other, the thermostat first.
- **The house's true air.** The loops read the whole house's air, as the
  thermostat does, not what its sensors read. Control by readings, with
  their noise and faults, is left for later.
- **The fans with the vents.** A circulation loop runs its fans while the
  vents stand open as far as its stage opens them, or further; a vent a
  command holds counts at its level.
- **Humidity by the dehumidifier, and a crack of the vents.** A
  dehumidifying loop runs its dehumidifier above its target by half its
  band and stops it below by as much. It opens the vents' first stage too,
  only while it runs its dehumidifier, the heater is off (the heating
  loop's state), and the air outside is drier than the house's: its
  humidity ratio lower by a margin, until it is lower by less than the
  margin less a band of its own. Heating to dry the air is left out.
- **One output per device.** A device two loops run stands at the higher of
  their requests: the vents at the venting loop's stage or the crack,
  whichever is open further.
- **A command wins.** A command to a device takes it out of every loop's
  hands from its moment; the fans follow a held vent's level.
- **The whole house decides; the grid follows,** for every device, as
  decision 0042 has it for the heater. A whole-house run reads the same
  decisions, with no grid run stepped.
- **The loops' state is the house's air's.** Whether the heater runs, how
  many stages stand open, whether the dehumidifier runs and whether the air
  outside counts as drier are fields of the house's air at a moment, beside
  its temperature and water, not the controller model's state (decision
  0055): a checkpoint keeps the house's air at two moments, its day's start
  and an hour before, and each carries how the loops stood then.
  Checkpoints are written in format 9; format 8, whose runs ran their
  heaters alone, is read with every other loop off.

The rules stay exploratory heuristics, labelled so in their docstrings,
until a source is checked against each.

## Consequences

- With the heating loop alone, a run is the run it was, to the last digit:
  replays, opening days and run identities do not move.
- A scenario's control may run every loop. The reference greenhouse still
  runs its vents and fans by the clock, until P11.5 gives it targets.
- The loops' targets other than heating's are their scenario's: changing
  them from a run's request (P11.3) and from the viewer (P11.4) come next.
- A relative humidity's edge costs a search through each stretch while a
  dehumidifying loop runs; a temperature's stays a closed form.
