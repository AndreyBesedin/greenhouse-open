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
