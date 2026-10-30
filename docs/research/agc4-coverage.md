# What the AGC4 dataset gives a tomato model's validation

**Status:** Memo, 2026-10-28. An inventory for item 5 of the
[research priorities](../roadmap/research-validation-priorities.md)
([decision 0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md)):
what the WUR Autonomous Greenhouse Challenge, 4th edition (AGC4), records,
what the repository's adapters read of it, what of it a tomato crop model
can be held to, and how it can be split without leaking. It decides
nothing: the first splits and metrics are for a decision record.

## Sources, and how they were checked

- **The two records** on 4TU.ResearchData, read through their DataCite
  metadata (`https://api.datacite.org/dois/<DOI>`): title, creators, issue
  date, licence, abstract and location.
  - The 2024 challenge: "4th Autonomous Greenhouse Challenge: Dwarf Tomato
    Timeseries and Images", version 1, issued 2025-06-23,
    [10.4121/fa102772-32db-4b30-bace-12f2016722ce.v1](https://doi.org/10.4121/fa102772-32db-4b30-bace-12f2016722ce.v1).
  - The 2023 pre-trial: "4th Autonomous Greenhouse Challenge: Pre-trial
    Dwarf Tomato Measurements and Images", version 1, issued 2024-06-17,
    [10.4121/e1ee9de9-6ce9-4502-a37c-34b5b1372bed.v1](https://doi.org/10.4121/e1ee9de9-6ce9-4502-a37c-34b5b1372bed.v1).
- **The paper** the 2024 record names as the experiment's description:
  Maree, Zhang, van Marrewijk, de Zwart, Bijlaard and Hemming (2025),
  "Autonomous Greenhouse Cultivation of Dwarf Tomato: Performance
  Evaluation of Intelligent Algorithms for Multiple-Sensor Feedback",
  *Sensors* 25(14), 4321,
  [10.3390/s25144321](https://doi.org/10.3390/s25144321), open access under
  CC BY 4.0. Below it is "the paper", cited by section, table or figure.
- **The file lists**, with sizes and checksums: the repository's manifests,
  `greenhouse_adapters/greenhouse_adapters/manifests/wur_agc4-challenge-2024.json`
  and `wur_agc4-pretrial-2023.json`, which `greenhouse-data inventory`
  regenerates from 4TU's API, and the fixture
  `greenhouse_adapters/tests/fixtures/4tu_agc4_challenge_2024.json`, a
  trimmed copy of that API's answer for the 2024 record.
- **What is inside the archives**, sheet by sheet and column by column:
  the adapters' code and notes, under
  `greenhouse_adapters/greenhouse_adapters/wur/`, written against the real
  files; their notes date their measurements of the files to 2026-09-14.
  They are the repository's reading of the files, not the publisher's
  description, and are cited below as "the adapter's notes".

**Not checked.** `data.4tu.nl` and the challenge's website did not answer
on 2026-10-28, so the records' landing pages, the 2024 record's
`README.md` (3,715 bytes) and the `channel_info.json` inside its
time-series archive were not read for this memo. No file was downloaded
from either record. A statement marked *not verified* is one that neither
the publisher's texts above nor the adapters settle.

## The two records

| | 2024 challenge | 2023 pre-trial |
| --- | --- | --- |
| Experiment | six compartments, each controlled by one team's algorithm, one crop cycle each | one compartment, tables under four light and two EC treatments, one crop cycle |
| Crop | dwarf cherry tomato 'Pick-&-Joy Red Cherry' (paper §2.2) | dwarf tomato, `Variety` written `Cherry` (adapter's notes); the cultivar is *not verified* |
| Period | transplanted 3 September 2024; harvested per compartment, the last on 21 November 2024 (paper §2.1) | climate from 5 September to 9 November 2023; crop measured from 4 September to 9 November 2023 (adapter's notes) |
| Files | `autonomous_greenhouse_challenge4_timeseries.zip` (6.0 MB), `autonomous_greenhouse_challenge4_canopy_camera.zip` (31.4 GB), `README.md` | `4th_autonomous_greenhouse_challenge_dwarf_tomato_pretrial_Timeseries.zip` (4.2 MB), `..._pretrial_canopy_cam.zip` (4.5 GB), `..._pretrial_single_plant_cam.zip` (7.5 GB) |
| Licence | CC BY 4.0 | CC BY 4.0 |

Both were grown in 96 m² compartments of Wageningen UR Greenhouse
Horticulture, Violierenweg 1, Bleiswijk, the Netherlands (52.03203 N,
4.53094 E), as each record's DataCite `geoLocations` and abstract say.
The pre-trial was the teams' training data for the challenge (paper §2.1).

## 1. What the dataset records

### The 2024 challenge

The time-series archive holds, under
`autonomous_greenhouse_challenge4_timeseries/`, one CSV per compartment in
`timeseries/`, the site's `timeseries/weather.csv` and
`timeseries/weather_forecast.csv`, the workbook `Harvest.xlsx`, and a
`channel_info.json` giving each channel's unit (adapter's notes,
`agc4_challenge_2024/channels.py`). Whether it holds anything else is
*not verified*.

| Compartment | Team | File | Canopy camera |
| --- | --- | --- | --- |
| 3.01 | Tomatonuts | `timeseries/tomatonuts.csv` | `camir_27` |
| 3.02 | MuGrow | `timeseries/mugrow.csv` | `cam_21` |
| 3.03 | Agrifusion | `timeseries/agrifusion.csv` | `cam_20` |
| 3.06 | Reference | `timeseries/reference.csv` | `cam_1` |
| 3.07 | IDEAS | `timeseries/ideas.csv` | `cam_19` |
| 3.08 | Trigger | `timeseries/trigger.csv` | `cam_18` |

Compartments and teams are the paper's (Figure 1); files and cameras are
the adapter's (`agc4_challenge_2024/compartments.py`, taken from the
README). The Reference compartment was run by the paper's authors
(§2.1). The six compartments are equal in size and equipment, with three
tables of 200 plants each (§2.2).

**Time.** Column `time`, Dutch local time with its UTC offset, `+02:00`
before and `+01:00` after the clock change of 27 October 2024 (adapter's
notes, `common/time.py`). One row every 5 minutes (DataCite abstract;
paper Table A3). The adapter reads the energy and cost columns as
increments over the 5 minutes ending at the row; whether other values are
instants or means over the interval is *not verified*. Sensors were
installed from 1 August and remote control tested from 15 August 2024
(§2.1); when the files' rows begin and end is *not verified*.

**Weather outside** (`timeseries/weather.csv`, one for the site; paper
Table A3 for units and meaning):

- `weather/air_temperature.outside` (°C), `weather/relative_humidity.outside`
  (%), `weather/humidity_deficit` and
  `weather/air_absolute_humidity_content.outside` (g/m³);
- `weather/radiation_global` (W/m²), `weather/radiation_sum` (J/cm², reset
  daily), `weather/par.outside` (µmol/m²/s);
- `weather/wind_speed` (m/s), `weather/wind_direction.registration`,
  `weather/rain_state` (1 rain, 0 dry), `weather/heat_emission` (W/m², from
  a pyrgeometer).

Neither Table A3 nor the adapter's map has an outside CO₂.

**Weather forecast** (`timeseries/weather_forecast.csv`): expected
temperature, relative humidity, global radiation, the day's radiation sum
and cloudiness (1 to 8), "updated a few times per day" and spanning "the
coming 7 days" (Table A3); wind too (adapter's notes). The adapter found
its rows indexed by the time a forecast is for, with no issue time.

**Climate inside** (each compartment's CSV):

- `compartment/air_temperature`, `compartment/relative_humidity`,
  `compartment/humidity_deficit` and `compartment/co2_concentration`, from
  one aspirated measuring box in the centre of the compartment, beside the
  middle table, at crop height (§2.3);
- `compartment/par`, from one PAR sensor on the middle table at a fixed
  height of 0.5 m (§2.3);
- substrate sensors in three pots: moisture (relative permittivity), bulk
  EC and temperature (§2.3, Table A3);
- the teams' own sensors (Table A4): pot weighing scales (Agrifusion,
  Trigger), microclimate temperature and humidity and an electrophysiology
  sensor (Agrifusion), leaf temperature by infrared thermometers (Trigger),
  chlorophyll fluorescence (MuGrow).

The substrate and team sensors' column names are *not verified*; the
adapter's notes say they are per-sensor columns of the compartment files.
Each compartment has one measuring point, so no spatial gradient is
recorded.

**Equipment** (§2.2): pipe-rail heating, 120 W/m² at peak; continuous roof
ventilation, 0.3 m² of opening per m², behind insect netting; an energy
screen and a black-out screen; 8 dimmable LED fixtures, 20 to
200 µmol/m²/s, spectrum fixed for all, at an assumed 3.2 µmol/J; fogging,
220 g/(m² h); CO₂ dosing, 7.5 g/(m² h).

**Setpoints and states** (Tables A1 and A2; columns from the adapter's
`CHANNELS`):

- setpoints: `compartment/heating_temperature_setpoint`,
  `compartment/ventilation_temperature_setpoint`,
  `compartment/minimum_pipe_temperature_setpoint`,
  `compartment/minimum_window_position_lee_side_setpoint`,
  `compartment/co2_concentration_setpoint`,
  `compartment/humidity_deficit_setpoint` (venting and fogging, 2.5 g/m³
  apart, §2.4), `compartment/lamps_activation_percentage_setpoint` (off or
  10 to 100 %), both screens' `screen_position_setpoint`, and
  `compartment/water_supply/water_supply_interval_setpoint`;
- for each, a `*_vip` column: the value the climate computer used, which
  rate limits and other influences can make differ from the setpoint
  (Table A1);
- states: `compartment/heating_lower_circuit/pipe_temperature` ("0 if
  there is no water flow", Table A2), `compartment/window_position_lee_side`
  and `..._wind_side`, both screens' `screen_position`,
  `compartment/lamps_activation_percentage`,
  `compartment/co2_actuation_state` and
  `compartment/co2_dosage_minutes_cumulative` (reset daily, Table A2).

No column for fogging's state is in Table A2 or the adapter's map; whether
the files have one is *not verified*.

**Irrigation** (§2.2, Tables A1 to A3): one 1.2 L/h dripper per pot, shots
of 1 minute (20 mL), the interval set by the algorithm;
`compartment/water_supply/water_flow_duration` (minutes, cumulative, reset
daily); the drain's `compartment/water_drain/water_volume`, `.../ec` and
`.../ph`. One nutrient recipe for all, EC 2.8 dS/m (§2.2, Appendix A).

**Energy and costs** (`energy/*`, `economics/*`): computed from the
recorded states, not metered. The DataCite abstract says so, and the
paper's §2.5 ("Cultivation Objective") gives the formulas: heating from
the difference between pipe and air temperature, lighting from the lamps'
activation, CO₂ from the dosing minutes.

**Crop and fruit** (`Harvest.xlsx`): measured by hand, destructively; the
samplings' results were not disclosed to the teams' algorithms (§2.2).

- Sheets: an information sheet; three intermediate samplings named like
  `Destructive harvest 7-10-24`, on 7 October, 22 October and 5 November
  2024 (§3.3); one `Final Harvest <compartment>` sheet per compartment
  (adapter's notes and tests).
- One row per plant, labelled `<compartment code>-<n>` such as `306-1`,
  with the fruit's total fresh weight and count (`FW tot`, `# tot`; the
  first sampling's sheet calls them `FW` and `# tom`) and, on later sheets,
  green and red counts and weights (`# tom green`, `FW green`, `#tom red`,
  `FW red`); aggregate rows per compartment, and standard-error columns
  on the first sampling's sheet (adapter's notes;
  `greenhouse_adapters/tests/test_wur_2024_harvest.py` mirrors the
  shapes).
- Six plants per intermediate sampling; at the final harvest, 50 plants
  from the centre of the middle table, their fruit sorted by ripeness,
  counted, weighed and dried (§2.2). Table 1 gives each compartment's red
  fruit dry-matter percentage. Whether `Harvest.xlsx` holds dry weights
  per plant is *not verified*.

Neither the paper nor the abstract describes a vegetative measurement in
2024: no plant height, leaf count, leaf area or leaf or stem mass. The
canopy height of the paper's Figure 9 is computed from the images; it is
*not verified* as a published column.

**Yield and harvest.** `dwarf_tomato/harvest_date` holds the day of year of
the compartment's single final harvest, "Jan 1st = 1" (Table A1), written
once, on the harvest day's last row (adapter's notes). The whole crop is
harvested at once, as pot plants (§1, §2.2). Table 1 gives, per
compartment, red fruit fresh weight per pot (219 to 283 g), its dry matter
(5.9 to 7.3 %), the red share of the fruit, and the cultivation's length
(70 to 80 days).

**Cultivar, density and spacing.** 'Pick-&-Joy Red Cherry' (Vreugdenhil),
a determinate dwarf tomato (§2.5), in 13 cm pots of a
compost-based substrate, on tables (§2.2). All compartments start at 56
plants/m²; an algorithm could space to 42, 30 and 20, skipping steps
(§2.2, Table A1), and staff did it by hand once a day (§2.4).
`dwarf_tomato/plant_density` (pots/m²) is written only on the day it
changes, at local midnight, and `dwarf_tomato/pot_area` is its reciprocal
(adapter's notes, `agc4_challenge_2024/spacing.py`). Mean densities over
the cycle range from 23.0 to 39.7 pots/m² (Table 1).

**Management interventions.** In the files: the spacings and the harvest
day. In the paper only (§2.2, §3.3, §3.4, §4.7):

- bumblebee pollination, the hive open from 10:00 to 14:00 each day; the
  black-out screen closed from 20:00 to midnight by local regulation;
- one intervention, when Trigger's irrigation stopped;
- the harvest brought forward by hand in Trigger and in Tomatonuts, the
  latter by about 10 days for fear of whitefly damage; whiteflies were
  present;
- a late spacing in IDEAS on 20 October, of intertwined plants;
- fruit fallen off plants by the final harvest;
- pests found by sticky-trap cameras, plants scouted by hand.

Whether the files record any of these beyond spacing and harvest is *not
verified*.

**Images.** `autonomous_greenhouse_challenge4_canopy_camera.zip`: one
top-view Oak-D S2 RGB-D camera per compartment, about 1.5 m above the
middle table (§2.3). The DataCite abstract says 4 images a day, the paper
says hourly.

### The 2023 pre-trial

The time-series archive holds three workbooks (adapter's notes,
`agc4_pretrial_2023/`).

- **Time** (`ClimateTimeseries.xlsx`, sheet `weather_climate`): `datenum`,
  a MATLAB datenum in Dutch local wall-clock time with no offset; a row
  every 5 minutes from 5 September to 9 November 2023; the hour repeated
  when the clocks went back on 29 October left empty; missing values
  written `NaN` (`climate.py`).
- **Weather outside:** `tout`, `rhout`, `iglob`, `windsp`, `rain` (a share
  of the 5 minutes, not a 0/1 state), `parout`, `pyrgeo`, `co2out`.
- **Climate inside:** `t_air`, `rh`, `co2`, `t_rail` (the rail pipe); and
  `par1` to `par4`, PAR in each light treatment's zone (the data spell the
  first `part1`). No setpoints and no humidity deficit.
- **Equipment:** `scr_enrg`, `scr_blck`, `vent_lee`, `vent_wind`; and
  `ligth_on`, fractional and undocumented by the workbook's `Info` sheet.
  No irrigation or energy columns.
- **Crop, non-destructive** (`CropMeasurements.xlsx`, sheet `All data`):
  40 labelled plants (labels 41 to 80), on nine weekly dates from 6
  September to 1 November 2023, five in each of eight treatment fields (EC3
  or EC6; high, medium, low or no light). Columns `Plantheigth`, `# leaves`,
  `leaf length`, `leaf width`, `#trusses`, and flowering, set, yellow,
  orange and red counts on each of the oldest five trusses. Dated without a
  time (`crops.py`).
- **Crop, destructive** (`DestructiveHarvest.xlsx`, sheet `All Data`):
  plants sampled on 4 September (at transplanting, before any treatment),
  18 September (switch to the generative phase), 29 September (fruit set)
  and 9 November 2023 (end product): 12 untreated plants, then 48 treated
  plants on each later date, 156 in all. Columns `Date`, `Phase`, `DAS`,
  `Treatment`, `Variety`, `EC`, `Light`, `Plant density (p/m2)`,
  `Sample n`, `Sample name`, and per-plant organ measurements such as
  `FW leaves (g/plant)` and `Trusses (#/plant)`, dry weights among them
  (`destructive.py`). The full list of measured columns is *not
  verified*.
- **Single plants:** 479 plants imaged one by one, "as well their plant
  traits (height, fresh weight, leaf area, number of red fruits)"
  (DataCite abstract), in the 7.5 GB single-plant archive. Whether the
  traits sit in a small file of their own inside it is *not verified*.
- **Canopy images:** one camera, 4 times a day (DataCite abstract).

### Sampling, and what is missing

| | 2024 challenge | 2023 pre-trial |
| --- | --- | --- |
| Climate, weather, controls | every 5 minutes, six compartments, 10 to 11 weeks of crop | every 5 minutes, one compartment, about 9 weeks |
| Fruit | per compartment, 3 samplings of 6 plants and a final harvest of 50 | at 4 destructive dates, 48 treated plants each after transplanting |
| Vegetative | none described | weekly on 40 plants; organ weights at 4 dates; 479 imaged plants |
| Images | canopy, per compartment | canopy, and single plants |

- **Gaps.** An empty cell in a 2024 CSV and `NaN` in 2023 are missing
  values (adapter's notes). How much is missing, per channel and
  compartment, has been measured neither by the publisher's texts read here
  nor by the repository. Data were delayed or sensor connections lost "a
  number of times" (§4.6).
- **Fruit lost before measurement.** Fruit fresh weight drops at the final
  harvest in most compartments; staff saw fruit fallen off (§3.3).
- **2023 crop sheet.** Coloured fruit is split into yellow, orange and red
  only in weeks 43 and 44; earlier, a blank and a zero cannot be told
  apart. From week 40, label 47 is a replacement plant (adapter's notes,
  `crops.py`).

## 2. What the adapters read

`greenhouse-data prepare wur agc4-2024` (or `agc4-2023`) writes the
canonical tier: the protocol's observations and events, timestamps in
UTC, values as recorded. The `tiny` and `dev` profiles never fetch the
image archives (`greenhouse_adapters/greenhouse_adapters/profiles.py`),
and `tiny` builds compartment 3.06 only (`cli.py`). Paths below are under
`greenhouse_adapters/greenhouse_adapters/wur/`.

### The 2024 challenge (`agc4_challenge_2024/`)

- `build.py`, `build_greenhouse`: reads the chosen compartments' CSVs,
  `weather.csv`, `weather_forecast.csv` and `Harvest.xlsx` from the
  time-series archive.
- `timeseries.py`: `parse_timeseries`, `parse_weather` and
  `parse_forecast` write one observation per mapped column per row,
  skipping empty cells, recoding `compartment/co2_actuation_state` (1 on,
  2 off) and reading the source's `1e-10` stand-in for zero in increment
  columns as 0. `final_harvest_timestamp` takes the harvest instant from
  `dwarf_tomato/harvest_date`, checked against the row's local day.
- `channels.py`: the columns read and what they become. `CHANNELS`:
  climate, actuator states, setpoints, `*_vip` values, CO₂ dosing,
  irrigation, drain and plant density. `INCREMENT_CHANNELS`: energy and
  per-m² costs. `WEATHER_CHANNELS`, and `FORECAST_CHANNELS`, which is
  `weather_forecast/radiation_sum` alone. Units are channel_info's, not
  converted.
- `spacing.py`, `spacing_events`: a `SPACING` event at each change of
  density.
- `harvest.py`: `read_harvest_workbook` reads the per-plant rows;
  `sampling_observations` writes, per sampling and compartment, the mean
  fruit count and mean fruit fresh weight per sampled plant, at local noon;
  `final_harvest_event` writes one `HARVEST` event per compartment with the
  sampled plants' summed fruit fresh weight (`harvested_mass_g`) and count,
  their number, and the means per plant of total and red fruit count and
  weight.

Left out:

- the canopy images;
- the substrate and team sensors, which need each probe's identity kept
  (`channels.py`);
- the forecast, except its daily radiation sum, since the rest has no
  issue time; and `weather/wind_direction.registration`, whose values are
  eight bit flags, not the degrees its description gives;
- the per-pot cost columns (each is the per-m² cost times the pot's area)
  and `dwarf_tomato/pot_area`;
- of `Harvest.xlsx`: the per-plant values (only means and sums are
  written), the green and red split at the three intermediate samplings,
  the standard errors, any dry weight, and the information sheet.

`harvested_mass_g` is the total fruit, ripe and unripe, of the plants on
the final-harvest sheet: neither the compartment's yield nor a mass per
m².

### The 2023 pre-trial (`agc4_pretrial_2023/`)

- `build.py`, `build_greenhouse`: reads the three workbooks.
- `climate.py`, `parse_climate`: the 8 weather and 8 compartment columns
  above (`WEATHER_CHANNELS`, `COMPARTMENT_CHANNELS`); a local time that the
  clocks skip or repeat is refused (`common/time.py`,
  `matlab_datenum_to_utc`).
- `crops.py`, `read_crop_measurements`: the 40 labelled plants, their
  treatment as their zone, and their weekly height, leaf count, leaf length
  and width, truss count, open flowers, set fruit, red and coloured fruit,
  the counts summed over measured truss cells only.
- `destructive.py`, `read_destructive_samples`: each sampled plant as one
  `DESTRUCTIVE_SAMPLE` event with every measured column as a parameter;
  the untreated plants listed once per treatment are kept once.

Left out: `par1` to `par4`, which need the treatment zones as regions;
`ligth_on`; the per-week sheets, which repeat `All data`; and both image
archives, with the single plants' traits.

## 3. What a tomato crop model can be held to

The two kinds of model named in the priorities, in outline; the model
survey records their equations, time steps and parameters.

- **Reduced-State TOMGRO** (Jones, Kenig and Vallejos, 1999,
  *Transactions of the ASAE* 42(1), 255–265,
  [10.13031/2013.13203](https://doi.org/10.13031/2013.13203)): five
  states per m² of ground, main-stem node number, leaf area index,
  above-ground dry weight, fruit dry weight and mature fruit dry weight; a
  daily step driven by the day's mean and daytime temperature, radiation
  and CO₂, as [arXiv:2308.06031](https://arxiv.org/abs/2308.06031)
  restates it; the plant density among its parameters.
- **A Vanthoor-type model** (Vanthoor, de Visser, Stanghellini and van
  Henten, 2011, *Biosystems Engineering* 110(4), 378–395,
  [10.1016/j.biosystemseng.2011.08.005](https://doi.org/10.1016/j.biosystemseng.2011.08.005)):
  a carbohydrate buffer feeding leaves, stems and fruit, the fruit counted
  and weighed through development stages; leaves and fruit harvested, the
  leaf area capped; driven by canopy temperature, CO₂ and PAR absorbed by
  the canopy; dry matter per m² of greenhouse; as the Modelica
  Greenhouses library's
  [`TomatoYieldModel`](https://build.openmodelica.org/Documentation/Greenhouses.Components.CropYield.TomatoYieldModel.html)
  implements it.

AGC4's crop is a determinate dwarf pot plant, harvested once after 70 to
80 days, grown at 56 to 20 plants/m². A Vanthoor-type model describes an
indeterminate crop whose leaves and fruit are picked as it grows; which
crops Reduced-State TOMGRO's parameters were fitted to is for the model
survey to record. Parameters for development, leaf area and fruit load
may not carry over unchanged; the reproduction and the calibration will
show how far they do.

### Drivers

| A model's input | 2024 columns | 2023 columns | Notes |
| --- | --- | --- | --- |
| Air temperature | `compartment/air_temperature` | `t_air` | One box per compartment. A model wanting canopy temperature gets air temperature; Trigger's leaf thermometers (Table A4) are not read. |
| PAR at the crop | `compartment/par`; or `weather/par.outside` or `weather/radiation_global`, times the cover's and screens' transmission, plus the lamps' PAR from `compartment/lamps_activation_percentage` | `par1` to `par4`, one per treatment zone; `parout`, `iglob` | The 2024 sensor sits at a fixed 0.5 m. The paper's Figure 5 computes PAR "from the transmissivity of the screens and cover" instead, "for robustness"; those transmissivities are not in what was read. The lamps give 200 µmol/m²/s at 100 %, linear in the activation (§2.2, §2.5). Table 2 gives each compartment's daily PAR sum over the first 70 days, a check on any reconstruction. |
| CO₂ | `compartment/co2_concentration` (ppm) | `co2` | |
| Plant density | `dwarf_tomato/plant_density` | `Plant density (p/m2)`, per destructive sample | 2024's changes are steps at local midnight. |
| Start and end | transplanting, 3 September 2024 (§2.1); `dwarf_tomato/harvest_date` | transplanting, 4 September 2023 | |
| Initial state | not measured, as far as the paper describes | the 12 plants sampled at transplanting | |
| Humidity, where a model uses it | `compartment/relative_humidity`, `compartment/humidity_deficit` | `rh` | |

Hourly or daily drivers are aggregates of the 5-minute rows, taken over
local days (Europe/Amsterdam): the lamps, screens and CO₂ dosing follow
local time, and the day of a clock change has 23 or 25 hours.

### Outputs

| A model's output | What AGC4 measured | What differs |
| --- | --- | --- |
| Fruit dry weight per m² | 2024: total fruit fresh weight per plant (`FW tot`) at 3 samplings and the final harvest | Fresh, not dry: only the red fruit's dry-matter percentage is given, once per compartment (Table 1). Per plant, not per m². |
| Mature fruit dry weight (TOMGRO), harvested fruit dry matter (Vanthoor) | 2024: red fruit fresh weight per plant (`FW red`) at the final harvest, and red and green splits on later sampling sheets | Red is a colour, not the model's maturity. AGC4 harvests nothing until the end, so a model's harvested fruit must be added back to its standing fruit, or its harvest switched off. Fruit fallen off before the final harvest is missing from the measurement. |
| Fruit number | `# tot`, `#tom red` per plant | A Vanthoor-type model counts fruit; Reduced-State TOMGRO does not. |
| Leaf area index, node number, above-ground dry weight | 2024: none. 2023: weekly leaf and truss counts and leaf length and width; organ weights at 4 dates; leaf area of 479 imaged plants | A different year and treatments. Leaf length and width are not leaf area. |
| Yield per m² per year | 30 to 45 kg/m²/year (§3.3.3) | Extrapolated by the paper from Table 1, not measured. |

**Fresh against dry.** A model's dry fruit weight compares with AGC4's
fresh weight only through a dry-matter fraction. The only one given is
the red fruit's, per compartment at the final harvest (5.9 to 7.3 %);
none is given for green fruit, or for the intermediate samplings. Either
the fraction becomes a stated parameter of the comparison, or the
comparison waits for dry weights per plant, if `Harvest.xlsx` has them.

**Harvested against standing.** Every 2024 fruit measurement is of fruit
on the plant: the samplings and the final harvest alike. A model that
removes ripe fruit as it goes compares through its harvested plus its
standing fruit.

**Per plant against per m².** AGC4 measures per plant; the models work
per m² of ground. Density changes from 56 down to as few as 20 plants/m²,
so a per-m² value jumps at each spacing while a per-plant value does not.
Converting with the density in force on the sampling day, from
`dwarf_tomato/plant_density`, keeps the two comparable. The density is per
m² occupied by the pots (§2.5); the energy and cost columns are per m² of
greenhouse (adapter's notes), and the three tables cover only part of the
96 m² compartment (§2.2), so the two areas differ.

**Which plants.** The final harvest's 50 plants come from the centre of
the middle table, the two side rows left out (§2.5); where the six plants
of each sampling came from is *not verified*.

### The climate, briefly

For a greenhouse climate model, the 2024 data are richer: the inputs
(outside weather, every actuator's state) and the outputs (inside
temperature, humidity, CO₂, PAR) every 5 minutes in six compartments.
What it lacks, as far as this inventory shows, is the cover's and
screens' optical and thermal properties, fogging's state, the lamps'
heat, and a metered heating energy.

## 4. Calibration and test splits

What can be held out: a 2024 compartment, which is also a team's whole
strategy; a period; the year, 2023 against 2024; and, in 2023, a
treatment.

1. **By year: calibrate on the 2023 pre-trial, test on the 2024
   challenge.** Another season, weather and set of treatments. The
   pre-trial has the vegetative and organ measurements a calibration
   needs, the challenge the fruit yields a test needs, and the teams had
   the pre-trial as their training data (§2.1). Its limits: the same cultivar
   in both years is *not verified*; the pre-trial varies light and EC, not
   temperature or CO₂; and 2024's fruit is weighed fresh.
2. **By compartment, within 2024.** Calibrate on some compartments, test
   on the others, chosen before any run is compared with their harvests;
   with six, leaving one out at a time gives six results and their spread.
   A held-out compartment holds out a whole strategy: temperature, light,
   CO₂, irrigation and spacing at once. Its limits: all six share the
   weather, the start, the cultivar, the substrate and the nutrients, so
   this tests the response to strategies, not to another season; and six
   is few. The Reference compartment, run by the paper's authors, is the
   natural one to calibrate on if one 2024 compartment is needed.
3. **By period.** Not for the crop: a compartment has four fruit
   measurements, and its crop at the split carries everything before it.
   For the climate, whole days or weeks with a gap between them, on
   held-out compartments as well.
4. **By treatment, within 2023.** Holding out a light level tests the
   response to light; all treatments share one compartment's air.

What would leak:

- a compartment's later measurements tested against a calibration on its
  earlier ones: the same crop, under the same controller;
- tuning on all six compartments' harvests, then reporting one of them as
  held out: the split is fixed before any comparison with 2024's fruit;
- calibration targets that pool the test compartments: the paper's Tables
  1 and 2 and its light use efficiencies are computed over all six;
- a test compartment's own dry-matter percentage used to turn its modelled
  dry weight into fresh weight: that is its measured output;
- features from a test compartment's images fed into the model: that makes
  the model an estimator of the state, no longer a prediction;
- the forecast's columns used as a forecast: they are indexed by the time
  they are for, so they hold what was measured later;
- a random split of 5-minute rows: neighbouring rows are nearly equal.

The spacing and the harvest day are inputs: the algorithms chose them
from what their sensors and images showed. A test that takes them as
given checks the crop's response, not those choices.

**Sample counts.** For fruit, 2024 gives four dates per compartment, 24
compartment-dates in all, with 6 plants at each sampling and 50 at each
final harvest. 2023 gives 4 destructive dates with 48 treated plants on
each of the last three, and 9 weekly dates on 40 plants.

## 5. Limitations

**Licence.** Both records are CC BY 4.0 (DataCite `rightsList`; the
manifests). It allows copying, redistributing and adapting the data, for
any purpose, with attribution: the creators, a link to the data (its
DOI), the licence, and whether the data were changed
([legal code](https://creativecommons.org/licenses/by/4.0/legalcode), §3).
It gives no warranty (§5). The paper is CC BY 4.0 too (its Crossref
record). Decision 0057 has a dataset downloaded, not redistributed,
unless its licence allows; CC BY 4.0 allows it, with attribution. The
repository holds no AGC4 data today: the adapters download it from the
publisher (`greenhouse_adapters/README.md`), the fixture holds 4TU's
metadata only, and the tests build miniature workbooks of their own.

**What it cannot validate:**

- vegetative growth in 2024: leaf area, nodes, leaf or stem mass;
- fruit dry weight per plant in 2024, unless `Harvest.xlsx` holds it, and
  the dry matter of green fruit;
- photosynthesis, respiration, transpiration and water uptake as fluxes:
  no gas exchange or transpiration is measured; two compartments' pot
  scales are not read;
- a response to one factor at a time in 2024: each compartment changes
  many at once, in one cycle, with no replicate;
- a long season with continuous picking: one short cycle of a determinate
  pot plant;
- spatial variation: one measuring box and one PAR sensor per compartment;
- light spectrum, fixed for all (§4.2); the root zone and nutrients, one
  recipe at EC 2.8; and pests, whose effect is not quantified.

**Known data issues:**

- the share of missing values per channel is unknown (above);
- fruit fallen off before the final harvest (§3.3);
- `weather/wind_direction.registration` holds bit flags, while Table A3
  describes degrees (adapter's notes);
- the forecast has no issue time (adapter's notes);
- the `*_vip` values often differ from their setpoints, which Table A1
  says "often match": the CO₂ value used matched its setpoint 62 % of the
  time and was up to 1,114 ppm from it, the irrigation interval's 67 % of
  the time (adapter's notes, `channels.py`);
- CO₂ dosing minutes reset each day around 07:40 local, not at midnight
  (adapter's notes);
- a pipe temperature of 0 means no water flows (Table A2), not 0 °C;
- the drain volume is "liter/10 pots" in Table A3, while the adapter takes
  channel_info's L/m² for it; which is right is *not verified*;
- the irrigation interval is in seconds in §2.4 and in minutes in Table A1;
- the images: 4 a day in the DataCite abstract, hourly in §2.3;
- Table 1 gives 101 % red fruit for one compartment, worth checking
  against the per-plant rows;
- 2023: one sample, `Cherry_EC3_ML_3` on 18 September 2023, lists 1,287.85 g
  of dry flowers on a 19.17 g plant; the `Info` sheet's column names differ
  from the data's; the workbook's own sum columns count a blank truss cell
  as zero (adapter's notes, `destructive.py` and `crops.py`).

## 6. Next steps

1. When `data.4tu.nl` answers, read the 2024 `README.md` and
   `channel_info.json` and the 2023 workbooks' `Info` sheets, and correct
   this memo where they differ.
2. Profile the time-series archives with the adapters, at the `dev`
   profile, without images: per compartment and column, the first and last
   timestamp, the rows and the share missing; per `Harvest.xlsx` sheet, the
   plants per compartment and the columns, dry weights included. Record
   the numbers, not the data.
3. With the model chosen (item 4 of the priorities), write its inputs and
   outputs against this inventory: each driver's column, aggregation and
   unit, and each output's measured counterpart and conversion.
4. Fix the split, the metrics and the conversions (dry matter, per plant
   or per m², which PAR) in a decision record, before any run is compared
   with 2024's fruit.
5. Extend the adapters only for what that model reads: likely the
   per-plant values and the red and green split of `Harvest.xlsx`, and the
   pre-trial's `par1` to `par4` with the zone each belongs to.
6. Build the drivers per compartment, calibrate on the calibration data,
   run the test once, and report the metrics, sample counts, missing data,
   run times and differences of definition, as the priorities ask.
