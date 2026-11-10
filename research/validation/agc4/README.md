# What the AGC4 archives hold

Item 5 of the [research priorities](../../../docs/roadmap/research-validation-priorities.md)
validates the tomato models on measured data, beginning with the WUR
Autonomous Greenhouse Challenge, 4th edition. [The AGC4 memo](../../../docs/research/agc4-coverage.md)
inventories what the dataset records; this profile counts it, file by file,
so that the memo's statements on rows, spans, gaps and dry weights rest on
numbers anyone can regenerate. It records the numbers, not the data.

```bash
greenhouse-data prepare wur agc4-2024 --profile dev   # the 2024 time-series archive, 6.0 MB
greenhouse-data prepare wur agc4-2023 --profile dev   # the 2023 one, 4.2 MB
python -m research.validation.agc4.profile > research/validation/agc4/profile.json
```

`prepare` downloads each archive from 4TU.ResearchData and checks it
against its manifest; the profile reads it where `prepare` put it, checks
the same checksum, and refuses an archive that is missing or differs. Its
output, [`profile.json`](profile.json), was made from the archives with the
MD5 checksums it names.

## What it holds

For the 2024 challenge
([10.4121/fa102772-32db-4b30-bace-12f2016722ce.v1](https://doi.org/10.4121/fa102772-32db-4b30-bace-12f2016722ce.v1)):

- `time_series`: for each CSV (a team's compartment, the site's weather,
  the forecast), its rows, its first and last timestamp as recorded, its
  most common step in seconds, and for each column the rows holding a
  value (`present`), the share that do not (`missing_share`), and, for a
  column of ten values or fewer, which (`values`);
- `harvest`: for each sheet of `Harvest.xlsx`, its header and its sample
  plants per compartment; on a final harvest's sheet, the plants whose
  fruit were sorted green and red (`sorted_by_colour`), those weighed for
  their red fruit alone (`red_alone`), and each batch of fruit dried
  (`dried`): its colour, its fruit count where the sheet gives one, its
  fresh and dry weight, and its dry-matter percentage, computed and as the
  sheet gives it.

For the 2023 pre-trial
([10.4121/e1ee9de9-6ce9-4502-a37c-34b5b1372bed.v1](https://doi.org/10.4121/e1ee9de9-6ce9-4502-a37c-34b5b1372bed.v1)):
each workbook's sheets, with their rows and their widest row's cells, and
the climate sheet profiled as a 2024 CSV is. Its timestamps are local wall
clock, without an offset.

A cell that is empty, or holds `NaN`, holds no value. Both datasets are
CC BY 4.0: Wageningen University & Research, via 4TU.ResearchData.

## What it shows, in short

- **2024 compartments:** 20,029 to 22,909 rows each, every 5 minutes, from
  00:00 on 3 September 2024 to 12:00 on the compartment's harvest day. The
  drivers a crop model reads (air temperature, humidity, CO₂, PAR, the
  lamps) miss 0.06 % of rows in every compartment. The site's weather is
  complete; the forecast's values are missing from 91.7 % of its rows.
- **2024 fruit:** 6 plants per compartment at each of the three samplings,
  and 50 at the final harvest, of which 30 (21 in 3.06) were sorted green
  and red. No dry weight per plant: one batch of red fruit was dried per
  compartment, and one of green fruit in 3.02, 3.06 and 3.07.
- **2023:** 18,721 climate rows every 5 minutes from 5 September to 9
  November 2023, each channel missing 0.09 % of them.

The memo reads these numbers against what the publisher and the paper say.

## The drivers

Decision [0076](../../../docs/decisions/0076-the-tomato-models-are-calibrated-on-agc4s-pre-trial-and-tested-once-on-its-challenge.md)
runs each tomato model on AGC4 an hour at a time.
[`drivers.py`](drivers.py) builds those hours from the same two archives:

```bash
python -m research.validation.agc4.drivers /tmp/agc4-drivers > research/validation/agc4/drivers.json
```

- **A series per run:** each 2024 compartment, from 00:00 on 3 September
  to the midnight that begins its harvest day; and each 2023 light zone,
  from 00:00 on 5 September to 00:00 on 9 November. Times are at a fixed
  UTC+01:00, so that every day has 24 hours.
- **An hour per row:** its start, the mean temperature, PAR above the
  canopy and CO₂ over the 5-minute rows stamped inside it, and the plants
  per m² in force at its start: the last `dwarf_tomato/plant_density`
  written in 2024, and the destructive workbook's `Info` sheet's in 2023.
- **Filled hours:** a driver with no rows in an hour takes its mean of the
  hour before, and the hour says so in `filled`. That is one hour per 2024
  compartment, the one the clocks repeated on 27 October, and two per 2023
  zone, both 02:00 hours of 29 October, which the pre-trial's wall-clock
  times cannot tell apart.

The CSVs are data derived from AGC4, and are not committed.
[`drivers.json`](drivers.json) is: for each series, its file, its hours,
its first and last hour, the hours filled, and the sha256 of its bytes,
which are the same on every run.

## The harness

[`harness.py`](harness.py) runs either tomato model on a series of hours,
as decision 0076 has it, and reads its state per plant at every midnight.
Each model is the run's own rung, with the parameters it is given, stepped
as the run steps it: Reduced-State TOMGRO a day at a time, Vanthoor's
model an hour at a time. What the harness adds is what AGC4's crop does
and the run's does not:

- **the start:** the 2023 transplants, per plant (`transplants`, from the
  pre-trial's destructive workbook): 0.068 g of dry leaves, 0.043 g of
  stem, 35.1 cm² of leaf and five leaves, scaled to the density at
  transplanting. Vanthoor's buffer starts where its caller says;
- **the spacing:** at each midnight a new density is in force, every state
  per m² of floor is scaled by the new density over the old, and
  Reduced-State TOMGRO's ρ is the density in force;
- **the readings:** at each midnight, per plant, the fruit's dry weight
  (Vanthoor's standing plus harvested), the mature fruit's (Reduced-State
  TOMGRO's alone), the dry weight above ground and the leaf area index.

It compares nothing with a measurement: that is the calibration's and the
test's, in that order. A 2023 zone's 65 days run in under a second for
either model.
