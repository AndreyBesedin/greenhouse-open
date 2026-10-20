# P11: Climate setpoints

**Status:** proposed, for review. Nothing is built yet. The open questions
are at the end.
Part of the [simulator roadmap](README.md).

## Goal

Let a person say what climate they want, and have the run's equipment work
towards it, as a greenhouse's climate computer does, rather than by the
clock. The targets are the air's temperature by day and by night, the
temperature above which the house vents, and its humidity. A run's targets
are its inputs, as its commands are: changed, they make another run.

## Where it starts from

- **The heater already runs to a setpoint** (P10.3,
  [decision 0042](../decisions/0042-a-season-a-thermostat-and-the-heat-it-gives-as-a-modelled-record.md)).
  The reference greenhouse heats to 18 °C from 07:00 and to 16 °C from
  19:00, in a band of 1 °C. The heater switches the moment the house's air
  reaches the band's edge, found from the house's exact solution through
  each stretch (`WholeHouse._switching_s` in
  `greenhouse_sim/greenhouse_sim/climate/house.py`), not at the next
  minute.
- **Everything else runs by the clock** (P09.4): the reference greenhouse's
  manifest turns its fans on at 08:00, opens its roof vents halfway at
  09:00 and fully at 11:00, half shuts them at 18:00, and shuts them and
  stops the fans at 20:00, whatever the weather. On a cold day the vents
  open at 09:00 while the heater is heating, and let its heat out. On a
  bright June morning they open fully only at 11:00, and the air passes
  30 °C first (the roadmap's entry for this project).
- **The whole house decides; the grid follows** (decision 0042). The
  thermostat reads the house's mean air, the air its sensors sample. A
  grid run takes the heater's level at each of its moments from the house
  (`ClimateRun.governed_by`). A command to the heater takes it out of the
  thermostat's hands from that moment.

## Dependencies

P05 (equipment, doors and vents), P07 (the weather), P09 (the reference
scenario, daily commands, run identity, checkpoints), P10.3 (the
thermostat).

## Direction

- **One controller, several loops.** Each loop is a rule a grower would
  recognise: it reads one quantity of the house's air, and runs its
  devices in steps, with hysteresis. There is no continuous controller (a
  PID) in this project.
- **Steps keep the air exact.** The house's air is worked exactly between
  the moments its devices change. A loop whose output changes in steps
  keeps that: each step is a moment the house finds exactly, as it finds
  the thermostat's switch today. A vent opened in proportion to the air
  would change at every instant, and the house could no longer work its
  air exactly between changes.
- **The whole house decides; the grid follows,** for every loop, as
  decision 0042 has it for the heater.
- **A command wins,** as it does over the thermostat today. A command to a
  device takes it out of its loop's hands from that moment, so the
  Equipment panel's switches and a person's schedule still work as
  overrides.
- **Targets are inputs.** A scenario's manifest gives its targets. The API
  and the viewer can ask for others, and a run's identity covers them, as
  it covers its commands.
- **The loops read the house's true air,** as the thermostat does. Control
  on what the sensors read, with their noise and faults, is more like a
  real greenhouse, and is left as a question below.
- **No new records for consumers.** The heat records of P10.3 stay as they
  are. Setting targets from outside the simulator waits for an actuation
  interface, which P10 left out.

## The loops

| Loop | Reads | Runs | Rule |
| --- | --- | --- | --- |
| Heating | air temperature | the heater | On below the heating setpoint by half its band, off above it by as much; a setpoint by day and one by night. Decision 0042's thermostat, unchanged. |
| Venting | air temperature | the roof vents, in stages | Each stage opens when the air passes the venting setpoint plus its offset, and closes when it falls back below by the band. The venting setpoint stays above the heating setpoint by at least a dead band, so the house never heats and vents for temperature at once. |
| Circulation | the venting loop's stage | the fans | On while the vents stand open beyond a stage. |
| Dehumidifying | relative humidity | the dehumidifier, and the vents' first stage | On above the humidity target by half its band, off below it by as much. The vents open to their first stage for humidity only while the air is warmer than the heating setpoint. |

Each loop's state (its stage, or whether it is on) is part of the house's
air, as `heating` is today, so that the run carries it on and a checkpoint
keeps it.

## Steps

| Step | What | Status |
| --- | --- | --- |
| P11.1 | **The controller as data:** `climate/control.py` holds the loops, their targets, bands and stages, and checks them (the dead band between heating and venting, stages in order, times of day on the minute). A manifest's `thermostat` becomes its `control`, in the manifest's next format, with a migration of the one before. | Proposed |
| P11.2 | **The house decides every loop exactly:** the next switch is the earliest moment any loop's edge is reached. The house's course through a stretch gains its humidity, so that a relative humidity's edge is found too. The grid follows each device a loop runs. Checkpoints keep each loop's state (checkpoint format 3). **With the heating loop alone, a run is today's run, to the last digit.** | Proposed |
| P11.3 | **Targets as a run's input:** a `&targets=` parameter on every climate route, read once and checked (refused with the reason, as commands are), in the run's identity. The equipment route says which loop runs each device, its state and its target at the moment. | Proposed |
| P11.4 | **The viewer:** a Targets panel (heating by day and by night, venting, humidity) that keeps its values in the address. The Equipment panel names the loop that runs each device. The timeline shows the loops' switches in the air's lane. | Proposed |
| P11.5 | **The reference greenhouse by its targets, not the clock:** its daily vent and fan commands give way to venting and humidity targets in its manifest. Its run changes, so its opening day, replay, reference views and screenshots are written again, and the changelog says that its identity changes. This waits until after the 20–22 October demo, since consumers follow its current run. | Proposed |
| P11.6 | **The QA scenario** (below), run and recorded. | Proposed |

## Acceptance

- With only the heating loop, the reference greenhouse's run is the run it
  is today: its replay digests and opening day do not move (P11.2).
- A loop switches at the moment its edge is reached, never at the next
  minute. While a device has the capacity to hold the air, the air stays
  within the loop's band, plus a tolerance the tests state.
- Changing a target makes another run, and the same targets give the same
  run.
- On the reference greenhouse, measured and recorded in the QA scenario:
  - on a cold March day, the vents stay shut while the heater heats;
  - on a bright June morning, the air stays below the venting setpoint
    plus its stages' offsets plus the band, where today's clock let it
    pass 30 °C.

## QA scenario

In the viewer, on the reference greenhouse, after P11.5:

1. **A March night:** the heater cycles within its band, and the vents
   stay shut.
2. **A sunny March noon:** the vents open stage by stage as the air
   passes the venting setpoint, the fans run with them, and both close
   as the air cools.
3. **A June morning:** the vents open as soon as the sun warms the house,
   and the air never passes 30 °C.
4. **A different venting target:** set from the Targets panel, it makes
   another run, and the vents open at the new temperature.
5. **A humid night:** the dehumidifier runs above the humidity target,
   and the vents stay shut while the air is cooler than the heating
   setpoint.
6. **A consumer** following the run sees less heat on a cold sunny day
   than the clock's schedule gave, in the hourly heat records of P10.3.

## Open questions

1. **Staged vents or proportional ones?** Stages are proposed, because they
   keep the air exact (above). How many stages, and at what offsets, is
   for P11.1.
2. **The house's true air or its sensors' readings?** The true air is
   proposed for this project. Control on readings would let a drifting
   sensor mislead the climate, as it does in a real greenhouse, and could
   come later.
3. **Fans with the vents, or on a temperature of their own?** With the
   vents is proposed: in the reference greenhouse they move the air within
   the house, which the whole house does not resolve.
4. **Humidity:** the dehumidifier and a vent crack are proposed. Heating
   to dry the air, as some growers do, is left out.
5. **Targets through a run:** a heating and a venting setpoint by day and
   by night, and one humidity target, are proposed. A schedule of targets,
   as daily commands are, would come later.
6. **The address:** the syntax of `&targets=` is for P11.3.
7. **When the reference greenhouse switches over:** after the demo is
   proposed, since its run is the one consumers follow.

CO₂ and light targets come after this project, as the roadmap records:
each needs equipment the simulator does not have yet.
