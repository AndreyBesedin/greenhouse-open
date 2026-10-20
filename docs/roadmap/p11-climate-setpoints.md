# P11: Climate setpoints

**Status:** proposed, for review. Nothing is built yet. The open questions
are at the end.
Part of the [simulator roadmap](README.md).

## Goal

Let a person say what climate they want, and have the run's equipment work
towards it, as a greenhouse's climate computer does, rather than by the
clock. The targets are the air's temperature by day and by night, the
temperature above which the house vents, by day and by night too, and its
humidity. A run's targets are its inputs, as its commands are: changed,
they make another run.

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

- **One controller, several loops.** Each loop reads one quantity of the
  house's air and runs its devices in steps, with hysteresis. There is no
  continuous controller (a PID) in this project.
- **The rules are exploratory heuristics,** and are labelled so in their
  docstrings and the manifests' notes. They follow the usual structure of
  a climate computer's heating and venting, with a dead band between them,
  but no source has yet been checked against each rule's specifics. P11.1
  cites a greenhouse-control source for each rule it keeps, or keeps the
  heuristic label. The acceptance below checks that the controller keeps
  its rules, not that the rules are a real greenhouse's.
- **Time always moves on.** Every edge a loop switches at is a value of
  the air, with a band of positive width between switching on and off, so
  the air must cross the band between two switches of one loop. A loop
  that depends on another (the fans on the vents, the humidity's vent on
  the heater) reads the other's state, which has its own band, never the
  air at the other's edge.
- **One output per device.** A device that two loops run takes the larger
  of their requests: the vents stand at the higher of the venting loop's
  stage and the humidity loop's. A loop that clears never closes what the
  other still asks for. The fans follow the vents' combined stage.
- **Steps keep the air exact.** The house's air is worked exactly between
  the moments its devices change. A loop whose output changes in steps
  keeps that: each step is a moment the house finds exactly, as it finds
  the thermostat's switch today. A vent opened in proportion to the air
  would change at every instant, and the house could no longer work its
  air exactly between changes.
- **The whole house decides; the grid follows,** for every loop, as
  decision 0042 has it for the heater.
- **A command wins,** as it does over the thermostat today. A command to a
  device takes it out of every loop's hands from that moment, its combined
  output included, so the Equipment panel's switches and a person's
  schedule still work as overrides. The fans follow a commanded vent's
  level as they would its stage.
- **Targets are inputs.** A scenario's manifest gives its targets. The API
  and the viewer can ask for others, and a run's identity covers them, as
  it covers its commands, on every route that makes or keeps a run.
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
| Venting | air temperature | the roof vents, in stages | Each stage opens when the air passes the venting setpoint plus its offset, and closes when it falls back below by the band. A setpoint by day and one by night, at the heating loop's times; each stays above that period's heating setpoint by at least a dead band, so the house never heats and vents for temperature at once. |
| Circulation | the vents' combined stage | the fans | On while the vents stand open beyond a stage. |
| Dehumidifying | relative humidity | the dehumidifier, and the vents' first stage | The dehumidifier: on above the humidity target by half its band, off below it by as much. The vents' first stage, for humidity, only while the dehumidifying loop is on, the heater is off (the heating loop's state, with its band), and the outside air is drier than the house's: its humidity ratio lower by a margin, with a band of its own. Otherwise venting cannot dry the house, and the vents stay as the venting loop has them. |

Each loop's state (its stage, or whether it is on) is part of the house's
air, as `heating` is today, so that the run carries it on and a checkpoint
keeps it.

## Steps

| Step | What | Status |
| --- | --- | --- |
| P11.1 | **The controller as data:** `climate/control.py` holds the loops, their targets, bands and stages, and checks them (the dead band between heating and venting, stages in order, times of day on the minute). A manifest's `thermostat` becomes its `control`, in the manifest's next format, with a migration of the one before. | Proposed |
| P11.2 | **The house decides every loop exactly:** the next switch is the earliest moment any loop's edge is reached. The house's course through a stretch gains its humidity, so that a relative humidity's edge is found too. The grid follows each device a loop runs. Checkpoints keep each loop's state, in checkpoint format 3; a format 2 checkpoint, whose run has the heating loop alone, is read with the other loops off. **With the heating loop alone, a run is today's run, to the last digit.** | Proposed |
| P11.3 | **Targets as a run's input:** a `&targets=` parameter on every route that makes or keeps a run, wherever `&daily=` is read today: the climate's, the crop's, the timeline's, the observations', the playback's and a checkpoint's. It is read once and checked (refused with the reason, as commands are), it is part of the run's identity, and a checkpoint keeps it, so that it is restored as the same run. The audit's run request (W11) would make this one change in one place. The equipment route says which loop runs each device, its state and its target at the moment. | Proposed |
| P11.4 | **The viewer:** a Targets panel (heating and venting, each by day and by night, and humidity) that keeps its values in the address, and passes them on every run's request. The Equipment panel names the loop that runs each device. The timeline shows the loops' switches in the air's lane. | Proposed |
| P11.5 | **The reference greenhouse by its targets, not the clock:** its daily vent and fan commands give way to venting and humidity targets in its manifest. Its run changes, so its opening day, replay, reference views and screenshots are written again, and the changelog says that its identity changes. This waits until after the 20–22 October demo, since consumers follow its current run. | Proposed |
| P11.6 | **The QA scenario** (below), run and recorded. | Proposed |

## Acceptance

- With only the heating loop, the reference greenhouse's run is the run it
  is today: its replay digests and opening day do not move (P11.2).
- A loop switches at the moment its edge is reached, never at the next
  minute. While a device has the capacity to hold the air, the air stays
  within the loop's band, plus a tolerance the tests state.
- Time always moves on: driven through each loop's band and back, no two
  switches of one loop fall at one moment.
- Two loops on one device: the vents stand at the higher of their
  requests, and one loop clearing leaves the other's request standing.
- Changing a target makes another run, and the same targets give the same
  run, on every route that makes or keeps one: a checkpoint saved under
  targets is restored under them.
- A checkpoint saved before P11.2 is still read.
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
4. **A different venting target by day:** set from the Targets panel, it
   makes another run, and the vents open at the new temperature; the crop
   and the timeline beside it are that run's too.
5. **A humid night:** the dehumidifier runs above the humidity target.
   The vents stay shut while the heater runs, and while the air outside is
   no drier than the house's.
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
4. **Humidity:** the dehumidifier and a vent crack are proposed, the crack
   only while the heater is off and the air outside is drier. Heating to
   dry the air, as some growers do, is left out.
5. **Targets through a run:** a heating and a venting setpoint by day and
   by night, at the same times, and one humidity target, are proposed. A
   schedule of targets, as daily commands are, would come later.
6. **The address:** the syntax of `&targets=` is for P11.3.
7. **When the reference greenhouse switches over:** after the demo is
   proposed, since its run is the one consumers follow.

CO₂ and light targets come after this project, as the roadmap records:
each needs equipment the simulator does not have yet.

## Review

The first draft's review (Codex, on #266) asked for the changes made above:
hysteresis on every condition a loop reads, so that time always moves on;
one rule for a device two loops run; one venting schedule throughout;
targets on every route that makes or keeps a run, checkpoints included;
humidity venting only when the outside air can dry the house; the format 2
checkpoints still read; and the rules labelled as heuristics until a source
backs each.
