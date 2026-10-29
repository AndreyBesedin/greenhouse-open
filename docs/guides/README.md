# Recipes for contributors

How to add what contributors most often add, in the order it is done: the
files each step touches, what is generated, and the tests that show it
works. Each recipe follows the most recent addition of its kind, named by
its commit. `tests/test_publishable.py` checks that every file a recipe
names exists, so a recipe that a change leaves behind fails before it
misleads anyone.

| To add | Recipe |
| --- | --- |
| A scenario, from a manifest | [add-a-scenario.md](add-a-scenario.md) |
| Another layout of a scenario | [add-a-layout.md](add-a-layout.md) |
| A weather: a preset, a recorded file or a kind | [add-a-weather.md](add-a-weather.md) |
| A device: a kind of climate equipment | [add-a-device.md](add-a-device.md) |
| A kind of sensor | [add-a-sensor-kind.md](add-a-sensor-kind.md) |
| An air model | [add-an-air-model.md](add-an-air-model.md) |
| A plant model | [add-a-plant-model.md](add-a-plant-model.md) |
| A viewer panel, with its loader | [add-a-viewer-panel.md](add-a-viewer-panel.md) |
| An API route, with its service | [add-an-api-route.md](add-an-api-route.md) |

The rules behind them are in [the engineering conventions](../engineering.md)
and [the decisions](../decisions/README.md); what to run before a commit,
and which files are generated, in [AGENTS.md](../../AGENTS.md).

## First: which path to extend

There is one simulator, **the run**
([decision 0035](../decisions/0035-one-simulator-the-run-every-part-on-a-ladder-of-fidelity.md)).
It is made of parts: the weather, the house's air, the light, the crop, the
sensors and the devices. Each part is a ladder of implementations, from the
simplest to the richest, and a scenario takes one rung of each. A new
model is a rung of one part.

Not every part has its contract yet. The weather has one
(`WeatherSource`), and so do the patterns of the air (`AirflowModel`), but
the house's air and the crop are classes the run builds itself. How a
scenario names its rungs is also still to be decided (`AUDIT.1` and
`AUDIT.2` in the [repository audit](../audits/2026-10-13-repository-audit.md)).
The air and plant recipes say what that means for a new model.

Beyond the simulator: records that producers and consumers share go in
`greenhouse_protocol`, datasets in `greenhouse_adapters`, and the viewer
(`greenhouse_sim/web`) only shows what the simulator serves.

## How a run's moments are worked out

- **The clock** (`greenhouse_sim/greenhouse_sim/core/clock.py`) counts
  seconds from the run's start, which is its start date's midnight at its
  site. A moment belongs to the day it lies in, or, at a midnight, to the
  day that midnight ends.
- **At a moment, the processes take turns**
  (`greenhouse_sim/greenhouse_sim/domain/processes.py`): commands, then the
  air, then the plants, then the sensors, then the cameras. An
  observation at a moment sees what changed at it.
- **Commands** (`greenhouse_sim/greenhouse_sim/climate/commands.py`) set a
  device or an opening at their moment, and a daily one at its time of
  each day. A command for a moment overrides the day's.
- **The air** is worked in stretches of at most a minute, each ending at a
  minute or at a command. The same moment always has the same air,
  whichever moments were asked for before.
- **The plants** each live a day at each midnight, from that day's air and
  their own light. The crop's work (a harvest round, then a lowering
  round) follows, at the start of the days it falls on.
- **Sensors and cameras** sample every `cadence_s` from the run's start.
- **The timeline** (`greenhouse_sim/greenhouse_sim/core/timeline.py`,
  `GET /api/scenarios/{id}/timeline`) lists every event in a window, in
  this order, and the viewer draws it.
- **The same seed gives the same draws**
  (`greenhouse_sim/greenhouse_sim/core/rng.py`). A run's identity is a
  digest of everything it is made of, so a change to a scenario, a layout
  or a weather makes another run. The kept files that record runs (the
  replay in `greenhouse_sim/tests/fixtures/`, the opening days in
  `greenhouse_sim/greenhouse_sim/scenarios/openings/`) are written again
  only by a change that means to change them, and its commit says why.
