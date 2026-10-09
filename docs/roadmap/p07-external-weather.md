# P07: External weather and greenhouse boundary coupling

**Status:** in progress: P07.1 to P07.6 done, P07.7 next. Part of the
[simulator roadmap](README.md).

## Goal

Drive the greenhouse from an explicit outside atmosphere, and make the air
inside respond to the outside's temperature, humidity and wind, through the
glass, through leaks and through its openings.

## Dependencies

P01 (the envelope and its openings) and P04 (environment fields). P05's
climate run is what the outside acts on, and its equipment shows control
fighting the weather. P06's sensors report what results.

## Direction

- **Weather is an explicit boundary state.** The outside is a time series
  on the run's clock, not constants in a scenario's configuration. Whatever
  the house exchanges with the outside, it exchanges with the weather at
  that moment.
- **Offline first.** Weather comes from deterministic synthetic profiles or
  from recorded files in the repository's formats. Any later provider of
  live or forecast weather plugs in behind the same interface. No weather
  service is needed to run or test the simulator.
- **One boundary, whatever model steps the air.** Conduction through the
  glass, infiltration and exchange through openings are computed once, as
  fluxes between the outside and the air against the envelope. Any climate
  model, P05's grid or a coarser one, takes them the same way.
- **Each boundary calculation is testable on its own,** with a known answer:
  no flux without a difference, and the sign reversing with it.

## Design

Today the outside is fixed for a whole run (`ClimateSettings`): one
temperature, humidity and CO₂. The house already exchanges with it in two
ways (P05):

- **through the glass:** each air cell against a wall or the roof exchanges
  U A (T_out − T) with the outside, U about 6 W/m²K for single glass;
- **through open doors and vents:** each opening exchanges the air against
  it with the outside's, at a fixed speed through its aperture, as much in
  as out. A draught is drawn there, out when the air inside is warmer than
  the outside's and in when it is cooler, as the stack effect would have it.

A climate run lasts at most an hour. P07 makes the outside change, adds the
wind, and needs runs of a day.

### 1. The site and the weather state

- **A site** places the world on the Earth: latitude, longitude, elevation,
  time zone, and the compass bearing of the world's x axis. Each scenario
  has one. Weather needs the bearing to turn a wind from the north-west into
  a wind across the house, and the time zone for its day; P08 needs all of
  it for the sun. A decision record fixes the convention.
- **The weather state** at a moment:
  - air temperature, relative humidity and CO₂;
  - wind speed and the direction it blows from, in degrees clockwise from
    north;
  - barometric pressure, by default the standard atmosphere's at the site's
    elevation;
  - global radiation and cloud cover, carried for P08 and unused until
    then.
- **A weather source** gives the state at any moment of a run, interpolating
  linearly in time between its records. Wind is interpolated as a vector,
  so that a wind turning from 350° to 10° turns through north, not through
  south. A scenario's source is one of:
  - **constant:** one state for the whole run. Today's fixed outside becomes
    this, with no wind;
  - **synthetic:** a deterministic daily profile (section 2);
  - **recorded:** a file (section 7).

### 2. Synthetic weather

A day of weather from a handful of numbers, the same every time:

- **temperature:** a smooth daily cycle between a minimum near dawn and a
  maximum mid-afternoon, local time;
- **humidity:** the air's water held constant through the day, so that its
  relative humidity falls as it warms and rises as it cools, as it mostly
  does outdoors;
- **wind:** a daily cycle of speed, calm at night and strongest in the
  afternoon, and a direction that veers steadily through the day; gusts
  seeded by the scenario's seed;
- **presets** by name, such as a cold spring day, a hot dry summer day and
  a windy autumn day, each a set of these numbers.

### 3. Conduction through the glass

- **A changing outside temperature** in P05's exchange, U A (T_out(t) − T).
- **Wind cools the glass.** U combines the glass with the air films on
  either side, 1/U = 1/h_in + R_glass + 1/h_out. The outside film's
  coefficient rises with wind speed, h_out = 5.8 + 4.1 v W/m²K, a common
  engineering correlation. Single glass's tabulated 6 W/m²K is its U in a
  moderate wind, about 4 m/s. In still air it is nearer 3.5 W/m²K, and in a
  gale nearer 7. A scenario's configured U is read as its U at 4 m/s, and
  the films set it at every other wind.
- **This moves P05's numbers:** its runs have no wind, so their glass
  passes less heat, and its heater's QA temperatures are recorded again.
- **Surface temperatures:** each glazed surface's temperature lies between
  the air on either side, in proportion to the films' resistances. The
  climate run publishes each wall's and roof slope's mean, so the viewer
  can colour the envelope by it.
- **Tests:** no difference passes no heat; reversing the difference
  reverses the flux; a closed house in constant weather settles where
  equipment's heat equals what the glass passes.

### 4. Infiltration, water and CO₂

- **A shut house leaks.** Infiltration exchanges a share of the house's
  air with the outside every hour. That share grows with wind speed,
  ACH = a + b v, with a around 0.25 an hour and b around 0.1 an hour per
  m/s, typical of a well-kept glasshouse. The exchange is spread over the
  air against the envelope. It brings the outside's heat, water and CO₂
  with it.
- **Through openings** too, the exchange brings the outside's water and CO₂
  at that moment (as P05's does with fixed values).
- **Tests:** dry outside air dries the house only through a path that
  exchanges air; with infiltration and openings shut off, the house's water
  changes only by equipment and condensation, as in P05.

### 5. Wind and stack pressure at the openings

Each open door or vent passes air according to the pressure across it.

- **Wind pressure:** the wind's dynamic pressure, ½ ρ v², times a pressure
  coefficient for the surface the opening lies on. The coefficient depends
  on the angle between the wind and the surface's outward normal: positive
  facing the wind, negative to the lee and along the roof. Values come from
  standard tables for low-rise buildings.
- **Stack pressure:** the difference in density between the air inside and
  out, over the height between an opening and the house's neutral plane.
- **Flows:** each opening passes Q = C_d A √(2 |Δp| / ρ) with the sign of
  its pressure difference, C_d about 0.6. The house's own pressure is the
  one at which as much air leaves as enters, found by bisection.
- **One opening alone** has no through-flow. It exchanges by the stack
  effect over its height and by the wind's turbulence, by standard
  single-sided formulas, as much in as out.
- **Inside the house,** the flow between windward and leeward openings is
  carried by the climate run's flow. P05's projection, which makes the
  flow conserve mass with nothing crossing the grid's faces, takes the
  openings' flows as fluxes through their faces, summing to zero. The
  arrows then run from the inflow openings to the outflow ones.
- **This replaces P05's fixed exchange speed.** P05's QA numbers that
  depend on it (the roof vent's draught and cooling) move, and are recorded
  again.
- **Tests:** in a symmetric house with an opening in each side wall,
  reversing the wind reverses which opening takes air in; with no wind and
  no temperature difference, nothing flows; the house's air is conserved.

### 6. Day-long runs

A weather day needs a run of 24 hours, but a climate run is an hour.
Measured on the climate box, an hour takes 1.5 s with a heater and an open
vent, and 7 s with the heater and the fan, whose jet's speed sets a short
time step. A day would take one to three minutes, and a larger house longer
in proportion to its cells.

The plan's fidelity ladder applied:

- **A whole-house climate model** (level 1): the house's air as one
  well-mixed volume, with the same boundary fluxes, the same equipment
  sources, condensation and CO₂. A step of a minute, so that a day runs in
  well under a second. It gives the house's temperature, humidity and CO₂
  through any length of run.
- **The field when it is looked at:** to show the air in space at a
  moment, the grid run (level 2) starts from the whole-house state an hour
  earlier and steps to the moment, under the same weather and equipment.
  An hour is enough for a small house's air to take its shape. Each hour's
  run is cached, so scrubbing within it is free.
- **Tests:** in constant weather, the whole-house model's mean temperature,
  humidity and CO₂ follow the grid run's mean over an hour, within a stated
  tolerance; both conserve energy and water to the same budget.

*Alternatives:*
- **The grid run, a day long:** one model, but minutes per day computed,
  and long browser tests. Feasible for the climate box only.
- **A coarser grid for long runs** (1 m cells): about sixteen times faster,
  and still one model, but coarse enough to lose the equipment's local
  effects, and still slow for the compartment.

### 7. Recorded weather

- **The format:** a CSV with a timestamp column (ISO 8601, with a time zone)
  and one column per quantity, named after the protocol's outside
  observation types (`outside_air_temperature_c`,
  `outside_relative_humidity_pct`, `outside_wind_speed_m_s`, …), so that
  the same names mean the same thing in a record and in a file. Units are
  those the names state. The protocol gains the types it lacks: the wind's
  direction, the barometric pressure and cloud cover.
- **Validation:** unknown columns, a timestamp without a time zone, times
  out of order, and values out of their physical range are refused, naming
  the row.
- **Missing values:** a gap of up to an hour is interpolated across; a
  longer one is unknown, and a run that reaches into it is refused rather
  than invented. A file without wind direction has wind without direction:
  it adds to infiltration and to single-sided exchange, but drives no
  through-flow. The recorded WUR greenhouse data
  (`greenhouse_adapters`) is such a case, as its wind direction is not
  ingested.
- **Provenance:** a run records its weather source, a recorded file by its
  content's hash, and its identity changes with it.

### 8. A weather station

The outside is observed as the inside is: a weather station is a sensor
outside the house that reads the weather, at its cadence, with its
imperfections, and reports `outside_*` observations (P06). Policies see the
station's readings, never the weather source itself.

### 9. Viewer

- **A weather panel:** the outside's temperature, humidity, wind (speed,
  and a compass needle for its direction) and pressure at the moment drawn.
- **The wind in the scene:** a large arrow outside the house, along the
  wind, scaled by its speed.
- **The envelope by temperature:** walls and roof slopes coloured by their
  surface temperature, with the existing "Colour by".
- **The openings by flow:** each open door or vent marked as taking air in
  or letting it out, with its flow in m³/s.
- **A day's timeline:** the run's time slider spans the day, in steps of a
  few minutes, with play at an accelerated rate. A chart under it shows the
  outside's temperature, humidity and wind speed through the day.
- **Two runs compared:** the sensors' and probes' charts gain the run
  without equipment beside the run with it, as the probes' charts do now.

### 10. Scenarios

- **Every scenario gets a site,** by default near the recorded WUR
  greenhouse data's, in the Netherlands, and keeps its outside as constant
  weather, so that nothing changes until a scenario asks for a weather
  source, or P07.4 and P07.6 change the boundary.
- **The climate box** gains a side vent on its left wall, closed until
  opened, so that a wind across the house has a vent on either side. Its
  default weather stays constant.
- **The weather day,** the final QA's, is the climate box under a synthetic
  cold spring day: a night near 4 °C, an afternoon near 16 °C, and a wind
  rising and veering from the south-west to the north-west.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P07.1 | `feat(weather): define the site, the weather state and its sources` | Done |
| P07.2 | `feat(weather): add synthetic day and night weather presets` | Done |
| P07.3 | `feat(climate): run a whole day` | Done |
| P07.4 | `feat(boundary): couple the glazing to the changing outside` | Done |
| P07.5 | `feat(boundary): add infiltration and the outside's water and CO₂` | Done |
| P07.6 | `feat(wind): drive the openings by wind and stack pressure` | Done |
| P07.7 | `feat(weather): import recorded weather` | Planned |
| P07.8 | `test(weather): compare a controlled and an uncontrolled day` | Planned |

### P07.1: The site, the weather state and its sources

The site on each scenario, its decision record, the weather state, a
constant source and a time-series source with interpolation, and the
weather panel and wind arrow. Every scenario's outside becomes constant
weather, so no run changes. Visible result: the weather panel and the wind
arrow. Tests: a known series interpolates as expected, wind included across
north; constant weather reproduces every existing run exactly.

#### As implemented

- **The site** (`world.site`, [decision 0028](../decisions/0028-the-world-has-a-site-and-its-x-axis-a-compass-bearing.md)):
  latitude, longitude, elevation, an IANA time zone, and the bearing of
  the world's x axis, by default east (x east, y north, z up). Every
  scenario has the default site, near Bleiswijk, at sea level.
  - **Bearings** are degrees clockwise from north. A site turns a bearing
    into a direction in the world's axes, and back.
  - **The standard atmosphere** at the site's elevation gives the pressure
    when a weather leaves it out.
- **The run's clock** starts at its scenario's start date's midnight at its
  site, published in UTC: for the scenarios' 1 January, 23:00 UTC the day
  before. P06's runs started at midnight UTC; their air is the same, and
  only their observations' instants, and so camera frames' identifiers,
  move.
- **The weather state** (`weather.state`): the outside air's temperature,
  relative humidity and CO₂, the wind's speed and the direction it blows
  from, the barometric pressure, the global radiation and the cloud cover.
  - **Its names are the protocol's** outside observation types without
    their `outside_` prefix (`air_temperature_c`, `wind_speed_m_s`, …).
    Wind direction, pressure and cloud cover have no protocol type yet;
    they get one with the weather station (P07.2) and recorded weather
    (P07.7).
- **Sources** (`weather.sources`):
  - **constant:** `ConstantWeather`, a scenario's `weather`;
  - **a series:** `WeatherSeries`, linear in time between its records, the
    wind as a vector. A record's moment gives the record exactly; a moment
    before the first or after the last is refused. Two opposite winds of
    the same speed meet in a calm, which keeps the earlier direction.
  - A run reads its weather on its own clock (`RunWeather`).
- **Each scenario's outside is constant weather:** the climate box's cold,
  damp night (8 °C, 90%, calm), and the others' default (10 °C, 80%,
  calm). The tomato compartment has the prevailing wind of the Dutch
  coast, a 4 m/s south-westerly, so that its scene shows one. Nothing uses
  the wind yet, and it has no climate run.
- **The climate run takes the weather** at the middle of each stretch it
  advances, at most a minute long, in place of P05's fixed outside. Under
  constant weather every run is what it was; a test runs the climate box
  under a series that warms through the hour, and its air follows. This is
  the first part of P07.4, the changing outside temperature.
  `ClimateSettings` keeps the starting air, the glazing, the mixing and
  the vents' exchange speed.
- **The API:** `GET /api/scenarios/{id}/weather?t=600` serves the site, the
  moment, the weather then, and the wind's velocity in the world's axes.
- **The viewer:**
  - **a weather panel** for each scenario, at the moment drawn: the
    moment in the site's own time, the air's temperature, humidity and
    CO₂, the wind by its speed and compass point, a compass whose needle
    points the way it blows, the pressure, and the site;
  - **the wind's arrow** outside the house: along the wind, a metre long
    for each metre a second, ending a metre short of the house's corners
    on the side it comes from, at half its height, and labelled. None in a
    calm.

### P07.2: Synthetic day and night weather

The synthetic profile, its presets, the weather station sensor, and the
day's weather chart. Visible result: scrubbing a day changes the panel, the
wind arrow and the station's readings. Tests: a preset's temperature is at
its minimum and maximum at the stated hours; its air's water is constant;
the same seed gives the same gusts.

#### As implemented

P07.2 lands in two pull requests: the synthetic days first, the weather
station after them.

- **A synthetic day** (`weather.synthetic`, `SyntheticWeather`): its
  coldest and warmest temperatures and their hours on the site's clock,
  its humidity at the coldest, its calmest and windiest winds, the
  direction the wind blows from at midnight and how far it veers by the
  next, its gusts' size, its CO₂, cloud cover and pressure.
  - **Temperature** follows a half cosine from the coldest hour up to the
    warmest, and another down to the next day's coldest. On the days the
    clocks change, the hours are still the clock's.
  - **The air's water** is the coldest moment's all day, and its relative
    humidity follows the temperature.
  - **The wind** rises and falls with the temperature, between its calmest
    and windiest. It veers steadily, and starts each day again from its
    midnight direction.
  - **Gusts and lulls** scale its speed by a share drawn once a minute,
    seeded by the scenario's seed and the minute, and interpolated
    between. The same seed gives the same gusts.
  - Radiation stays nothing until the sun (P08).
- **Presets** (`weather.presets`): `cold_spring_day` (4 to 16 °C, 95% at
  dawn, a wind from 1.5 to 6 m/s veering from the south-west to the
  north-west), `hot_dry_summer_day` (17 to 31 °C, a light easterly) and
  `windy_autumn_day` (9 to 13 °C, 7 to 13 m/s, gusty).
- **A scenario's weather** is constant or synthetic. Any scenario can be
  run under a preset by name, in place of its own, as with its layouts:
  `&weather=cold_spring_day` on its climate field, probes, observations,
  truth and weather. A weather there is not is not found. Each scenario
  lists the weathers it can be run under (`weathers`, its own first,
  named `default`). The climate runs kept are told apart by their weather.
- **The day:** `GET /api/scenarios/{id}/weather/day` gives the weather every
  ten minutes through the runs' first day.
- **The viewer:** the Weather panel, opened, chooses the weather to run
  under, kept in the address, and charts the day's temperature, humidity
  and wind speed, each from its least to its most, with the moment drawn
  marked across them. Choosing another layout keeps the weather.
- **Not yet:** the runs still last an hour, so a day is seen in the chart,
  not yet in the run (P07.3).

The weather station, in the second:

- **Its instruments are point sensors** of five new kinds, each reading one
  quantity of the weather the run is under at its samples: the air's
  temperature (`outside_temperature`) and humidity (`outside_humidity`),
  the wind's speed (`wind_speed`) and the direction it blows from
  (`wind_direction`), and the pressure (`barometric_pressure`). They err as
  P06's sensors do, in their own units. A wind vane's reading goes round
  the compass rather than being held at an end; the others are held within
  their instruments' ranges.
- **They report the protocol's outside observations,** which gains the
  types it lacked: `outside_wind_direction_deg`,
  `outside_barometric_pressure_hpa` and `outside_cloud_cover_pct`. Every
  quantity of the weather state now has its `outside_*` type, and a test
  keeps it so.
- **They stand outside the house,** and a layout that puts one inside is
  refused; the house's own sensors still stand inside. Their housings are
  in the way of nothing, as the others' are.
- **The climate box has one** on a mast 3 m in front of the house: its
  thermometer and hygrometer 1.5 m up, its barometer below them, and its
  anemometer and wind vane 6 m up, above the ridge. Its scene has five more
  entities, and its observation log five more sensors.
- **Their truth** is the weather itself, by the same evaluation-only path
  as the others'. Policies see the station's readings, never the weather.
- **In the viewer** each instrument is a sensor like the others: selected,
  its reading and the truth beside it, through the run.

### P07.3: A whole day

The whole-house climate model, runs of a day, and the grid run started from
it for the field at a moment. Visible result: the time slider spans a day,
and the field and the probes follow it. Tests: the whole-house model follows
the grid run's mean; both close their energy and water budgets.

#### As implemented

P07.3 lands in two pull requests: the whole-house model first, the
day-long runs after it.

- **The whole house** (`climate.house`, `WholeHouse`) is the reduction of
  a climate run's grid to one volume: the grid's air cells' volume, its
  exchange with the outside through the glass and the open doors and
  vents, summed, the heat its equipment adds and the water it takes, and
  the weather at the middle of each minute.
  - **Exact between moments:** with those held, temperature, water and
    CO₂ each relax towards where their sources balance, and are advanced
    by the equations' own solution, not by small steps. A minute's
    stretch, and an hour in about a millisecond.
  - **Water** is taken never beyond what the air holds, and what the air
    holds beyond saturation condenses and is counted, as on the grid.
- **Against the grid run's mean** on the climate box, measured and kept as
  the tests' tolerances:
  - **shut, whatever runs:** temperature within 0.3 °C, CO₂ and the water
    equipment takes alike;
  - **condensing:** the grid's air condenses first in the cells against
    the cold glass, the well-mixed air only when its mean saturates, so
    while heating the whole house holds up to 1.3 g/kg more water;
  - **a vent open:** the grid exchanges the cooler air beside the vent,
    the well-mixed air the mean, so with the heater on the whole house runs
    1.7 °C cooler.
- **Budgets:** shut off from the outside, the heat it gains is the
  heater's and the water it loses is what is taken or condenses, to
  rounding.
- **The API:** `GET /api/scenarios/{id}/climate/house?…&t=600` gives the
  house's air every minute up to the moment, and the same run's all off,
  asked as the climate field is.
- **The viewer:** "House air", under the climate run's time slider: the
  house's temperature, humidity and CO₂ through the run up to the moment
  drawn, the run all off dashed beside it.

The day-long runs, in the second:

- **A climate run lasts a day** (`climate.day`, `ClimateDay`): commands and
  moments up to 86 400 s.
- **The field at a moment** is a grid run's. Through the first two hours it
  is the grid run from the start, as before. After them it is a grid run
  started from the whole house's air, the same in every cell, an hour
  before the moment's hour began: 5:20 is drawn from a run started at
  4:00, as is every moment to 6:00. After its hour the grid run's mean lies
  within 0.3 °C of the whole house's, and the heater's corner has taken its
  shape again.
  - **Kept:** the three latest of a day's later grid runs. Scrubbing within
    an hour carries one on; the next hour starts another. An override
    later in the day carries on from the air before it, as P05's do.
  - **Measured:** on the climate box, a later moment costs a grid run of
    one to two hours, 1.5 to 14 s by what runs; the next five minutes
    within it, a fraction of a second.
- **What sensors sample** must be the same air however late the run is
  looked at, and the later grid runs are not kept for every moment of a
  day. So sensors sample the grid run from the start through its first two
  hours, and the whole house's air after them, the same in every cell, in
  the flow the equipment makes then. After two hours, a thermometer by the
  heater reads what one across the house does.
- **Probes** read the grid run that draws the moment asked for, every
  minute from its start, beside the same run all off, and their charts
  span that run's two hours. The house's air is charted from the run's
  start, through the day.
- **The viewer:** the time slider spans the day, a minute at a time;
  playing moves a minute at a time through the first hour and five minutes
  at a time after it. A moment after the first hour is written `5 h 05 min`.

### P07.4: The glazing and the changing outside

A changing outside temperature, the wind's film coefficient, surface
temperatures, and the envelope coloured by them. P05's heater numbers are
recorded again. Visible result: a cold night cools the glass, and then,
more slowly, the air. Tests: no difference passes no heat; reversing it
reverses the flux; U is the configured one at 4 m/s, and rises with
wind.

#### As implemented

- **The changing outside temperature** came with P07.1: the climate run
  already takes the weather at the middle of each minute.
- **U with the wind** (`climate.glazing`): 1/U = 1/h_in + R_glass + 1/h_out,
  h_out = 5.8 + 4.1 v, R_glass 0.004 m²K/W for 4 mm of float glass. A
  configured U is the glass's at 4 m/s; its inner film then follows (8.5
  W/m²K for single glass). Single glass passes 3.4 W/m²K in still air and
  7.3 in a 15 m/s gale. A U above what the glass and the outside film alone
  pass is refused. The grid run and the whole house both take U in the
  weather's wind at each stretch.
- **Glazed surfaces:** each wall's air cells against the grid's side, up to
  the eaves, and each roof slope's under its half of its span, as the
  grid's top. Each surface's mean air, its temperature between the air and
  the outside, and the heat it passes; together they pass what the run's
  glass passes. The whole house's would all be its mean.
- **The API:** `GET /api/scenarios/{id}/climate/glazing?…&t=600`, asked as
  the climate field is, from the grid run that draws the moment.
- **The viewer:** while the climate is drawn, each wall and roof slope
  carries `surface_temperature_c` and `glass_loss_w`, so "Colour by" shades
  the envelope by its glass's temperature and the inspector shows both.
- **P05's numbers, recorded again.** The climate box's night is still, so
  its glass passes 3.4 W/m²K, not 6, and its heater warms it more. Ten
  minutes in, heated: 37.35 °C beside the heater (31.88 before) against
  10.40 all off (9.01), and 18.90 across the house (14.96) against 10.57
  (9.13); settled, 21.2 °C rather than 15.5. The browser tests and the
  climate tests carry the new numbers. With the heater on and the roof
  vent open, the whole house now runs 3.2 °C below the grid's mean, as the
  vent is most of what the house loses.

### P07.5: Infiltration, water and CO₂

Infiltration growing with wind, and the outside's water and CO₂ at each
moment through every path. Visible result: opening a vent under dry outside
air dries the house; a windy night cools a shut house faster than a calm
one. Tests: no exchange path, no exchange; the house's water budget closes.

#### As implemented

- **A shut house leaks** (`ClimateSettings.infiltration_per_h`, 0.25, and
  `infiltration_per_h_per_m_s`, 0.1): ACH = 0.25 + 0.1 v of its air an
  hour. On the grid (`Transport.leaks_m3_s`), the leak is spread over the
  air cells against the walls and roof, each by its share of their area.
  It carries the outside's heat, water and CO₂, as an open vent does. The
  whole house takes the same total. Zero for both seals a house.
- **The outside's water and CO₂ at each moment** reach the house by every
  path that exchanges air: the gaps and the open doors and vents. The
  glass passes heat alone.
- **Checked:** sealed, the house keeps its water and CO₂ to rounding under
  a dry outside. Leaking, the whole house's CO₂ and water relax towards
  the outside's as e^(−0.25) an hour, exactly. The grid's CO₂ follows the
  whole house's within 5 ppm, and in an 8 m/s wind it leaks faster. Under
  the cold spring day's dry night air, an open roof vent dries the house.
- **The recorded numbers move a little again:** the climate box's leaks
  take about 25 W/K, beside its still glass's 750. Ten minutes in, heated:
  37.03 °C beside the heater (37.35) against 10.31 all off (10.40); it
  settles at 20.8 °C (21.2). The browser tests carry them. Tests that
  seal a house (P05's budget tests) now seal its gaps too.

### P07.6: Wind and stack pressure at the openings

Pressure coefficients, the openings' flows and the house's pressure,
through-flow in the grid run, single-sided exchange, and the openings
marked by flow in the viewer. P05's QA numbers that move are recorded
again. Visible result: turning the wind turns which vents take air in.
Tests: reversing the wind in a symmetric house reverses the flows; still
and isothermal, nothing flows; the house's air is conserved.

#### As implemented

- **Where each opening is** (`climate.openings`, `OpeningSite`): its
  aperture, its centre's height and vertical extent, the compass bearing
  its surface faces out to (by the site's compass), and whether it is in
  the roof.
- **Pressure across it:** the wind's dynamic pressure times a coefficient
  by the angle between the way the wind comes from and the surface's
  outward face, every 45° and interpolated between. Walls: +0.7 facing the
  wind, +0.35, −0.5 along it, −0.4, −0.2 in its lee. A shallow roof: −0.7
  to −0.4, drawn whichever way the wind blows. The stack: inside and
  outside air densities from their temperatures and the barometric
  pressure, over the opening's height.
- **Flows:** Q = 0.6 A √(2 |Δp| / ρ) through each, the house's pressure
  bisected until as much air leaves as enters. Each open opening also
  exchanges both ways by the single-sided formulas, the stack's over its
  own height or the wind's turbulence, 0.025 A v, whichever is the more. An
  opening alone has only that.
- **Across the house:** the projection now takes air entering and leaving
  at the grid's faces (`conserving(..., inflow=...)`). Being linear, it is
  solved once per open opening, for a cubic metre a second in through it
  and out through the first, and the openings' flows at each stretch scale
  those. The air entering brings the outside's heat, water and CO₂; the
  air leaving takes the cells' own. Each stretch takes the openings' flows
  for the air's mean temperature and the weather then.
- **The whole house** takes the same flows for its mean air.
- **This replaces P05's fixed exchange speed** (`vent_exchange_m_s` is
  gone). On the climate box, still air and 8 K warmer inside draw about
  1 m³/s in at the side vent and out at the roof vent; a 4 m/s southerly
  drives 4.4 m³/s through. The roof vent alone exchanges 0.19 m³/s by the
  stack over its 0.24 m, where P05 exchanged 1.1 m³/s. So P05's roof-vent
  numbers are recorded again: under it ten minutes in, heated, 0.05 m/s and
  14.57 °C, where P05 had 0.29 m/s and 10.42 °C. With a vent in each side
  wall and a 4 m/s wind across, the house is at the outside's temperature
  in ten minutes.
- **The climate box** gains `side_vent_left`, across the house from its
  side vent, shut. Its scene has one more entity.
- **The API:** `GET /api/scenarios/{id}/climate/openings?…&t=600`, what each
  open opening passes, net and each way, from the grid run that draws the
  moment.
- **The viewer:** while the climate is drawn, each open opening carries
  `flow_in_m3_s` and `exchange_m3_s` for "Colour by" and the inspector,
  and an arrow, in from outside where air enters and out from inside where
  it leaves, a metre long for each cubic metre a second, labelled. Under
  the cold spring day with both side vents open, the south one takes the
  air in ten minutes past midnight, and the north one by eight in the
  evening, when the wind has veered to the west-north-west.

### P07.7: Recorded weather

The CSV format, its validation, gaps, provenance, and a small recorded day
in the repository for tests and the viewer. Visible result: a recorded day
replays from the timeline. Tests: each kind of bad file is refused, naming
its row; a short gap is interpolated and a long one refused; the run's
identity changes with the file.

### P07.8: A controlled and an uncontrolled day

The same weather day run twice, without equipment and with a heater, fan
and vent schedule, and the sensors' charts of both overlaid. Visible
result: the two runs diverge as the night falls. Tests: the controlled run
is warmer through the night than the uncontrolled one; both replay
exactly.

## Final QA: `weather-day`

At runtime, replay the weather day, accelerated, and check that:

- the outside changes through the day;
- the air inside responds, in the field and in the whole-house trace;
- the vents' flows respond to the wind's direction;
- the sensors report the changes inside, and the weather station those
  outside;
- the controlled and uncontrolled runs visibly diverge;
- the replay is the same every time.

## Acceptance criteria

- [ ] Weather is an explicit external boundary state.
- [ ] The simulator runs fully offline, with synthetic or recorded weather.
- [ ] Temperature, moisture and wind can change the air inside.
- [ ] Each boundary calculation is testable on its own.

## Known approximations

What P07 simplifies on purpose, kept here until a later step removes it:

- **The glass has no heat capacity:** its surface temperature follows the
  air at once. Its thermal mass is small beside the air's in a day.
- **The floor and the ground still pass no heat.** The ground's heat is
  P08's, with the sun's.
- **Pressure coefficients are tabulated for low-rise buildings,** not
  computed for each house. CFD (P04) could compute them for a particular
  house later.
- **An opening is a point at its centre's height** for the house's
  pressure balance, its two-way flow within its own height the
  single-sided formula's, added to its net flow; the stack takes the
  house's mean temperature. The flow across the house is the projection's
  potential flow: an incoming stream spreads at once, carrying no momentum
  of its own (P07.6).
- **Infiltration is spread evenly over the envelope,** where real leaks are
  at gaps, vents' edges and doors.
- **The whole-house model is well mixed:** it knows the house's mean, not
  its gradients. The field at a moment comes from the grid run, which takes
  its shape within the hour before it. It condenses only when its mean
  air saturates, not first against the cold glass, and an open vent
  exchanges its mean air, not the cooler air beside the vent (P07.3's
  measured differences).
- **Plants still take their daily climate,** not the air where they stand,
  and transpire nothing, until P09.
- **After a run's first two hours, sensors read the whole house's air,**
  the same wherever they stand: the field is drawn when it is looked at,
  and not kept for every moment of a day (P07.3).

## Review decisions (9 October 2026)

1. **Day-long runs:** a whole-house model for the day, with the grid run
   started from it an hour before the moment whose field is looked at.
2. **The site and the compass:** a site on every scenario now, with the
   bearing of the world's x axis, recorded as a decision.
3. **The boundary's physics:** U changes with wind, and the openings' flows
   come from wind and stack pressure instead of P05's fixed exchange speed,
   with the through-flow carried inside the grid run. P05's QA numbers that
   move are recorded again.
4. **Recorded weather:** columns named after the protocol's outside
   observation types, with wind direction, barometric pressure and cloud
   cover added to the protocol; gaps up to an hour interpolated, longer ones
   refused.
5. **The QA scenario:** the climate box with a second side vent, under a
   synthetic cold spring day.
