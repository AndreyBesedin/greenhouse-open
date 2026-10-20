# 0042: A season, a thermostat, and the heat it gives as a modelled record

**Status:** Accepted
**Date:** 2026-10-20

## Context

The reference greenhouse ran 120 days from 1 March under one synthetic day,
the cold spring day, every day, with its heater, vents and fans on a fixed
daily schedule (P09.4). Its sun followed the season and nothing else did:
a consumer reading its outside temperature saw the same curve every day,
and its heater ran the same hours in a March frost as on a June night.
P10.3 ([#235](https://github.com/AndreyBesedin/greenhouse-open/issues/235))
asks for three things of the run that the viewer and a consumer share
(decision 0041):

- **Weather that follows the date** and changes from day to day,
  deterministic for a seed, over at least 80 days.
- **A heater on a simple explicit rule,** a setpoint with hysteresis, whose
  duty follows the weather.
- **The heat it gives as a record,** published as modelled, with its units
  and assumptions written down.

The run's air has two models (`climate.day`): the whole house, one
well-mixed volume worked minute by minute from the start, which the
sensors sample; and grid runs, cell by cell, which the viewer draws and
which start from the whole house's air an hour before the moment shown.
Both take their equipment's levels from the run's schedule. A heater that
depends on the air cannot be a schedule worked out in advance.

## Decision

- **A seasonal weather kind** (`weather.seasonal`). Each day's usual
  coldest and warmest temperatures follow the year along a half cosine
  from their values on its coldest day (20 January by default) to those
  half a year later. Each day's actual ones are shifted by a spell: an
  autoregressive series drawn from the seed and the date, whose next day
  keeps `persistence` of the day before's shift. A day's cloud cover is
  drawn from the seed and the date too. The day's shape, humidity and wind
  are a synthetic day's, and through the evening the air cools from the
  day's warmest to the next day's coldest, so nothing jumps at midnight.
  A date's weather is the same whenever a run starts.
- **A thermostat runs a heater** (`climate.thermostat`), named in the
  scenario's manifest: a setpoint by day and one by night, at times of a
  run's day on the minute, and a band. It switches the heater full on when
  the house's mean air falls below the setpoint by half the band, and off
  when it rises above it by as much. It switches the moment the air
  reaches the edge (`climate.house`), worked out from the house's exact
  solution through each stretch, not at the next minute: the house's air
  holds little heat, and a heater sized to the house warms it by degrees a
  minute, so a once-a-minute decision overshoots its band by more than the
  band.
- **The whole house decides; the grid follows.** The thermostat reads the
  air the sensors sample, and a grid run takes the heater's level at each
  of its moments from the house (`ClimateRun.governed_by`). A command to
  the heater, from the start or later, takes it out of the thermostat's
  hands from that moment. A run with everything off sets the heater off
  from the start (`off_levels`).
- **The heat is counted where it is given.** The house keeps, as it keeps
  the water its equipment removes, the heat its heaters have given so far:
  their rated power at the levels they run at, for as long. A checkpoint
  keeps it, and whether the thermostat was heating.
- **One record a day,** `HEATING_ENERGY_INCREMENT_MJ_M2` at the day's end
  (`services.heat_log`): the heat given over the run's day, in MJ per
  square metre of floor. Its source is the simulation and the run, and it
  names no sensor. It is heat input to the air, not the fuel or
  electricity a heater draws, which its efficiency would set, and it leaves
  out the sun's. A consumer sums the increments, as it would a meter's.
- **The viewer is told what it cannot work out:** a run's equipment at a
  moment, the thermostat's heater as the run has it, and its setpoint then
  (`GET /api/scenarios/{id}/climate/equipment`). The scene draws the heater
  so, and the Equipment panel says the thermostat runs it.
- **A run's identity covers what it is made of:** its scenario's whole
  configuration, layout included, beside its key. A manifest or a layout
  changed makes another run, not the same identity for another world.
- **The reference greenhouse** takes the season (0.5 to 5.5 °C on its
  coldest day, 13 to 22.5 °C half a year later, spells of 2.5 °C keeping
  0.7 a day, clouds 55 % give or take 40), and a thermostat at 18 °C from
  7 h and 16 °C from 19 h, with a band of 1 °C, in place of its heater's
  daily commands. Its vents and fans keep their clock. Its heater is now
  30 kW: the 15 kW one held the house 10 °C above the outside at most, so
  through a real March it would run all day and night and the thermostat
  would never switch it.

## Consequences

- The reference run is another run, with another identity. Its first day
  with red fruit, where the viewer opens it, moves from day 80 to day 86,
  a colder March than the cold spring day slowing its crop, and its kept
  opening day, its replay digests and the viewer's tests of its numbers
  are written again.
- Its heater runs most of a March day and seldom a June one. Measured on
  the reference run:

  | Days | Outside, coldest to warmest | Heater on | Heat, MJ/m² a day |
  | --- | --- | --- | --- |
  | 0 to 2, early March | 3 to 10 °C | 0.54 to 0.71 of the day | 12.2 to 16.2 |
  | 8, a frost | −1 to 5 °C | 0.89 | 19.5 |
  | 100, early June | 9 to 18 °C | 0.09 | 2.0 |
  | 110 to 112, mid-June | 10 to 22 °C | 0.04 to 0.07 | 0.8 to 1.6 |

- The vents keep their clock, so on a cold day they let out heat the
  heater makes up, and on a bright June morning the house passes 30 °C
  before they open fully. A thermostat on the vents is the next step, and
  would cut the heat a March day takes.
- The house's air is all the heat the model keeps: no soil, frame or crop
  holds any, so the thermostat's cycles are short, a minute or two. The
  grid run takes the heater's level at the start of each of its minutes,
  so within a minute its air may lag a switch.
- A thermostat's switching is a moment of the run, not a command: the
  run's command log does not list it, and QA mode reads the heater's level
  from the run.
