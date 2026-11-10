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
- **the spacing:** where a new density is in force, every state per m² of
  floor is scaled by the new density over the old, and Reduced-State
  TOMGRO's ρ is the density in force. Vanthoor's model is spaced at the
  hour the density changes, 23:00 at the fixed offset for a summer spacing
  at local midnight; Reduced-State TOMGRO, a day to a step, at the midnight
  of the day the new density is in force;
- **the readings:** at each midnight, per plant, the fruit's dry weight
  (Vanthoor's standing plus harvested), the mature fruit's (Reduced-State
  TOMGRO's alone), the dry weight above ground and the leaf area index.
  Vanthoor's model also gives the leaves it has pruned so far, which no
  state keeps: the harness takes each hour's pruning as the mean of its
  rate at the hour's start and end, times the hour.

It compares nothing with a measurement: that is the calibration's and the
test's, in that order. A 2023 zone's 65 days run in under a second for
either model.

## The calibration's targets, screen and manifests

Decision 0076 has each model's calibration name its parameters, bounds,
targets, objective, start and method in a manifest committed before it
runs. [`calibration.py`](calibration.py) gives the targets and the
objective, and a screen of which parameters move it:

```bash
python -m research.validation.agc4.calibration /tmp/agc4-drivers > research/validation/agc4/screen.json
```

- **The targets:** the pre-trial's destructive samples on 18 and 29
  September and 9 November 2023, per light zone and EC treatment, the mean
  per plant of the dry weight above ground, the fruit's, the leaves' and
  the stem's, and the leaf area index: 120 in all, in
  [`screen.json`](screen.json). A plant whose fruiting clusters weigh
  nothing fresh has no fruit, a measured zero. An organ dried heavier than
  it weighed fresh is no target, nor its plant's total: seven stems and one
  flower cluster on 18 September.
- **The objective:** decision 0076's, the sum of squared log ratios, each
  side raised by half the smallest mean above zero of its quantity.
  Reduced-State TOMGRO is held to the dry weight above ground, the fruit's
  and the leaf area index; Vanthoor's model to all five.
- **The screen:** each model at its published parameters, then each
  parameter alone at 0.8 and 1.25 times its value, on the calibration data
  alone. At the published parameters the objective is 89.5 for
  Reduced-State TOMGRO and 173.3 for Vanthoor's model.

The manifests, [`manifests/tomgro.json`](manifests/tomgro.json) and
[`manifests/vanthoor_katzin.json`](manifests/vanthoor_katzin.json), each
name four parameters from the screen, chosen for distinct processes, not
two that move the objective the same way:

| Model | Parameter | Process | Bounds | Screen |
| --- | --- | --- | --- | --- |
| Reduced-State TOMGRO | `n_ff` | the fruit's onset | 6 to 22 nodes | 60.7 |
| | `delta` | leaf area per node | 0.004 to 0.05 m² | 24.5 |
| | `qe` | light use (with E, not both) | 0.04 to 0.1 | 33.4 |
| | `alpha_f` | the fruit's share of growth | 0.4 to 1.0 | 6.0 |
| Vanthoor's model | `sla` | leaf area per carbohydrate | 2.0 to 6.0 × 10⁻⁵ m² mg⁻¹ | 134.9 |
| | `alpha` | light use (with the CO₂ terms, not all) | 0.25 to 0.5 | 87.1 |
| | `t_end_sum` | the fruit's onset | 200 to 1,500 °C day | 26.6 |
| | `rg_fruit` | the fruit's sink | 0.15 to 0.8 mg m⁻² s⁻¹ | 33.8 |

Each says why it is chosen, which strong ones are left and why, and the
method: scipy's Powell from the published values, each parameter scaled to
its bounds. Vanthoor's buffer starts at its `c_buf_min`, the least below
which its growth stops.

## The calibration

[`calibrate.py`](calibrate.py) runs a model's calibration as its manifest
names it, on the 2023 data alone, and writes its report,
[`calibrated/tomgro.json`](calibrated/tomgro.json) and
[`calibrated/vanthoor_katzin.json`](calibrated/vanthoor_katzin.json):

```bash
python -m research.validation.agc4.calibrate tomgro /tmp/agc4-drivers > research/validation/agc4/calibrated/tomgro.json
python -m research.validation.agc4.calibrate vanthoor_katzin /tmp/agc4-drivers > research/validation/agc4/calibrated/vanthoor_katzin.json
```

It refuses a 2023 series whose sha256 is not the one `drivers.json`
records. Each report holds the calibrated parameters beside the
published, the objective at both, the optimizer's evaluations, message
and run time, and the fit: each target's prediction at the midnight that
begins its day, its error and relative error, and whether it falls within
two standard errors of its measurement, with the same measures per
quantity. The fruit not yet set on 18 September, a mean of zero, has no
relative error and, every plant weighing the same, no spread to judge an
error by. A calibrated set is a research result kept here, never one of the
models' published defaults (decision 0076). Powell is deterministic: the
same data, code and scipy give the same parameters.

The report of Vanthoor's model also gives the leaves it has pruned per
plant by each date.

| Model | Objective, published → calibrated | Evaluations | Run time |
| --- | --- | --- | --- |
| Reduced-State TOMGRO | 89.5 → 4.2 | 163 | 2 s |
| Vanthoor's model | 173.3 → 19.8 | 464 | 10 min |

| Model | Parameter | Published | Calibrated | Bounds |
| --- | --- | --- | --- | --- |
| Reduced-State TOMGRO | `n_ff` | 22 | 10.1 | 6 to 22 |
| | `delta` | 0.038 | 0.0195 | 0.004 to 0.05 |
| | `qe` | 0.08 | 0.0998, at its upper bound | 0.04 to 0.1 |
| | `alpha_f` | 0.8 | 0.998, at its upper bound | 0.4 to 1.0 |
| Vanthoor's model | `sla` | 2.66 × 10⁻⁵ | 4.26 × 10⁻⁵ | 2.0 to 6.0 × 10⁻⁵ |
| | `alpha` | 0.385 | 0.384 | 0.25 to 0.5 |
| | `t_end_sum` | 1,035 | 1,388 | 200 to 1,500 |
| | `rg_fruit` | 0.328 | 0.254 | 0.15 to 0.8 |

The fit on the calibration data: the bias is the mean relative error, and
the share within two standard errors counts the targets that have a
spread.

| Model | Quantity | Bias | RMS relative error | Within 2 SE |
| --- | --- | --- | --- | --- |
| Reduced-State TOMGRO | dry weight above ground | −6 % | 22 % | 14 of 24 |
| | fruit | −7 % | 26 % | 12 of 16 |
| | leaf area index | +10 % | 42 % | 4 of 24 |
| Vanthoor's model | dry weight above ground | −18 % | 28 % | 8 of 24 |
| | fruit | +23 % | 68 % | 1 of 16 |
| | leaves | −38 % | 43 % | 3 of 24 |
| | stem | +26 % | 64 % | 5 of 24 |
| | leaf area index | −13 % | 40 % | 8 of 24 |

What it shows:

- **Reduced-State TOMGRO grows less than the crop did.** Two of its four
  parameters end at their upper bounds: the leaves' quantum efficiency and
  the fruit's share of growth. On 9 November its dry weight above ground
  is 11.0 to 21.8 g per plant, against 17.3 to 30.9 g measured, short in
  every treatment; its fruit is 10.0 to 16.0 g, against 12.0 to 21.0 g.
- **Its leaf area does not see the light.** It follows the nodes, which
  follow temperature, and the four zones shared one compartment's air: the
  leaf area index is the same in every zone, and reaches the model's most,
  4.0, by 9 November, where 2.1 to 3.0 were measured. `lai_max` is not
  among the parameters calibrated.
- **Vanthoor's model keeps its light use and moves its organs.** Its
  `alpha` stays within 0.3 % of the published value; the leaf area per
  carbohydrate rises by 60 %, the fruit's growth takes a larger
  temperature sum to come to its full, and its sink is smaller. Its fruit
  is 29 to 166 % over the measurement on 29 September, and 7.7 to 13.6 g
  on 9 November, against 12.0 to 21.0 g. Its stem, 3.4 to 6.1 g on 9
  November, is about twice the 1.5 to 3.4 g measured.
- **Vanthoor's model prunes.** Its leaf area index never passes 2.31,
  short of its most, 3, but its pruning is a smooth switch: by 9 November
  it has pruned 4.7, 3.9, 1.9 and 0.8 g of leaf per plant in the high,
  medium, low and unlit zones, where 2.6 to 2.7 g stand in each. AGC4
  pruned none, and measured 3.8 to 6.7 g of leaves. The fit holds the
  leaves standing, as decision 0076 has it. The pruning, heavier where
  more grows, leaves about the same standing in every zone.

Each limit is reported, not corrected: decision 0076 has a calibration
change nothing outside its manifest. The test on 2024 runs these
parameters once.
