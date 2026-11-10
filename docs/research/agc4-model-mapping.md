# What each tomato model reads of AGC4, and what it is held to

**Status:** Memo, 2026-11-10. Step 3 of [the AGC4 memo](agc4-coverage.md)'s
next steps, for item 5 of the
[research priorities](../roadmap/research-validation-priorities.md)
([decision 0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md)):
for each of the two tomato models in the run, which AGC4 column gives each
driver, how it is aggregated and in what unit, and which measurement each
output is held to, through which conversion. Decision
[0060](../decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md)
compares like with like, and names, sources and bounds any conversion; this
memo lists them. It decides nothing: the split, the metrics and the
conversions chosen are for a decision record (the AGC4 memo's step 4).

Numbers about the files are [the profile](../../research/validation/agc4/README.md)'s,
or read from the same archives; the models' are their manifests' and
parameter files'. "The AGC4 memo" is [agc4-coverage.md](agc4-coverage.md),
cited by section.

## The models, as the run has them

- **Reduced-State TOMGRO** (`tomgro`, Oliveira et al.'s parameters,
  `greenhouse_sim/greenhouse_sim/biology/tomato/tomgro/parameters.py`):
  five states per m² of floor, the main stem's nodes `n` (per plant), the
  leaf area index `lai`, and the dry weights above ground `w`, of the fruit
  `wf` and of the mature fruit `wm` (g m⁻²). Its parameters are for an
  indeterminate crop at ρ = 3.5 plants/m², its first fruit setting at
  node 22 (`n_ff`). It converts CH₂O to dry weight at E = 0.75 g g⁻¹.
- **Vanthoor's model as Katzin simplified it** (`vanthoor_katzin`, version
  1, GreenLight 2.0.7's parameters): a carbohydrate buffer, fruit, leaves
  and stems in mg CH₂O per m² of floor, a temperature sum, the canopy's
  temperature over the last day, and the fruit harvested since planting. It
  harvests fruit beyond 300 g CH₂O m⁻² standing and prunes leaves beyond a
  leaf area index of 3. It has no plant density and counts no fruit.
- **Both** are driven an hour at a time through the `house_hours` profile,
  version 1: each hour's mean temperature, PAR above the canopy and CO₂
  (`HourDrivers`), a day of at most 24 hours to a step (`StepCourse`).
  Neither changes its plant density during a run; neither counts fruit.

AGC4's crop is a determinate dwarf pot plant, transplanted at 56 plants/m²,
spaced down to as few as 20, and harvested once, whole, after 69 to 79 days
(the AGC4 memo, §1 and §3). Neither model's parameters were fitted to such
a crop; how far they carry over is what a calibration and a test measure.

## The drivers

Each driver is the mean over an hour of local time (`Europe/Amsterdam`) of
the 5-minute rows inside it.

| Driver (`HourDrivers`) | 2024, per compartment | 2023, per light zone | Unit |
| --- | --- | --- | --- |
| `temperature_c` | `compartment/air_temperature` | `t_air` (one for the compartment) | °C |
| `par_above_umol_m2_s` | `compartment/par` | `part1`, `par2`, `par3`, `par4` (high, medium, low and no light; the first spelled `par1` in the `Info` sheet) | µmol m⁻² s⁻¹ |
| `co2_ppm` | `compartment/co2_concentration` | `co2` (one for the compartment) | ppm |

- **Temperature.** Reduced-State TOMGRO reads the air's, as its reference
  does. Vanthoor's model reads the canopy's, which the profile gives as the
  air's: in GreenLight's simulated greenhouse that ran its temperature sum
  2.1 % ahead by day 109
  ([the two tomato models in the run](tomato-models-in-the-run.md#what-the-driver-profile-changes)).
  In 3.08 alone, Trigger's two `compartment/leaf_temperature` columns allow
  the same question to be asked of measured leaves, as a sensitivity; they
  are empty on 8.8 % of rows.
- **PAR.** One sensor per compartment, on the middle table at a fixed
  0.5 m (paper §2.3), so its distance to the canopy shrinks as the crop
  grows. The paper's Figure 5 computes PAR from the screens' and cover's
  transmissivity instead, which the files do not hold. The paper's Table 2,
  each compartment's daily PAR sum over the first 70 days, checks the
  sensor's series.
- **CO₂.** The compartment's measuring box, beside the middle table at crop
  height.
- **Gaps.** The same 13 rows are empty in every 2024 compartment: the first,
  at 00:00 on 3 September, and the second 02:00 to 02:55 when the clocks
  went back on 27 October. No other driver row is missing. The repeated
  hour needs a rule: its first occurrence held, or the hour left out.
- **The day of the clock change.** It has 25 local hours, and a step takes
  at most 24. Either the run's days are kept at a fixed offset, UTC+01:00,
  so that every day has 24 hours and the summer ones begin at 01:00 local,
  or that one day's extra hour is dropped. The lamps, screens and CO₂ dosing
  follow local time (the AGC4 memo, §3), so the choice moves a daily
  aggregate, not an hourly one.
- **What else the files have,** and neither model reads: humidity, the
  equipment's states and setpoints, irrigation and drain, and the teams'
  own sensors.

**Density.** `dwarf_tomato/plant_density` steps at local midnight (the
AGC4 memo, §1): from 56 plants/m² to 42, 30 or 20 in each 2024
compartment, some steps skipped (3.01 goes from 56 to 20; 3.02 from 56 to
30). In 2023 the `Info` sheet gives 48, 36, 25 and 20 plants/m² by date,
with none from 29 September to 9 October. Neither model is spaced during a
run. A spacing moves pots apart and leaves each plant's mass as it was, so
in a run of AGC4 every state per m² of floor is multiplied by the new
density over the old at the spacing's midnight: the masses and the leaf
area index, not Reduced-State TOMGRO's nodes, which count per plant, nor
the temperature sums. Reduced-State TOMGRO's ρ, which scales its growth per
m², is the density in force. This is the harness's doing, not the run's,
and is an approximation: a plant spaced out also intercepts more light per
plant, which each model sees only through its leaf area index.

**Start and initial state.** The 2024 crop was transplanted on 3 September
(paper §2.1), and its rows begin at 00:00 that day. Its state at
transplanting was not measured. The 2023 transplants, sampled on 4
September 2023 before any treatment (12 plants, each listed once per
treatment), weighed 0.111 g dry above ground (0.068 g leaves, 0.043 g
stem), with 35.1 cm² of leaf and about five leaves, three of them longer
than 5 cm. At 56 plants/m² that is 6.2 g m⁻² and a leaf area index of
0.20; Oliveira et al.'s start, for Reduced-State TOMGRO, is 0.09 g m⁻²
and 0.014 at 3.5 plants/m². Whether 2024's transplants matched 2023's is
*not verified*, nor is it that the two years' cultivars are the same (the
AGC4 memo, §2).

## The outputs, and what they are held to

The 2024 crop was measured as fruit per plant, fresh, on fruit still on
the plant: three samplings of 6 plants per compartment, on 7 October, 22
October and 5 November (days 34, 49 and 63 after transplanting), and the
final harvest on the compartment's harvest day, day 69 to 79 (11 to 21
November).

| Measured, 2024 | Plants | Reduced-State TOMGRO | Vanthoor's model |
| --- | --- | --- | --- |
| Fruit fresh weight per plant: `FW tot` at the samplings; at the final harvest, the `HARVEST` event's mean | 6 per sampling; 30 at the final harvest (21 in 3.06) | `wf` | `c_fruit` + `harvested_fruit`: AGC4 harvests nothing before the end |
| Red fruit fresh weight per plant at the final harvest (`mean_red_fresh_weight_g_per_plant`) | 50 | `wm`, mature fruit, which is not a colour | none: it tells no ripeness |
| Fruit counts (`# tot`, `#tom red`) | as above | none | none |
| Dry matter of a dried batch of fruit | one red batch per compartment, one green in three | not an output | not an output |

Each comparison of fruit goes through three conversions:

1. **Per m² of floor to per plant:** divided by the density in force on
   the day measured. The models' fruit per m² falls at each spacing; a
   plant's does not.
2. **Carbohydrate to dry matter,** for Vanthoor's model only. GreenLight
   2.0.7's own yield (`greenlight/main_cli.py`, in the wheel the
   reproduction pins) divides the harvested fruit's mg CH₂O by an "assumed
   fruit dry matter content" of 0.06 to give fresh weight: it takes a
   carbohydrate equivalent for a gram of dry matter. Reduced-State TOMGRO's
   E, 0.75 g of dry weight per g CH₂O, shows how far apart the two can be:
   a quarter.
3. **Dry to fresh:** divided by a dry-matter fraction of fruit. The
   candidates, each with its source:

   | Fraction | Source | What it is |
   | --- | --- | --- |
   | 6 % | GreenLight 2.0.7, `main_cli.py` | assumed |
   | 8.0 % | 2023, last destructive date: per plant, `DW fruits` over `FW fruits clusters`, 48 plants | mostly green fruit (33.9 green, 6.9 orange, 6.4 red per plant), cluster stems included; the other year's |
   | 5.93 to 7.28 % | 2024, the red batches, one per compartment (the AGC4 memo, §1) | ripe fruit, each compartment's own |
   | 7.61 to 8.08 % | 2024, the green batches of 3.02, 3.06 and 3.07 | unripe fruit |

   Between 6 % and 8 % a predicted fresh weight moves by a third. A
   compartment's own batches are its measured output: using them for its
   own conversion is a leak (the AGC4 memo, §4).

**When.** A model stepped by the day holds its states at the day's
boundaries; a sampling took place during its day (the adapter stamps it at
local noon), and the final harvest on its harvest day. The state at the
midnight before and after a sampling brackets it; their difference is a
day's growth, the uncertainty of the timing. A compartment's file ends at
12:00 on its harvest day, so the final harvest has drivers up to the
midnight before it and half a day past, not to the midnight after.

**In 2023,** the calibration candidates (the AGC4 memo, §4): per plant and
per light and EC treatment, the dry weights of leaves, stem, flowers and
fruiting clusters at four dates, the leaf area measured (a leaf area index
of 1.28, 1.31 and 2.54 at the last three dates, with the density then in
force), and weekly leaf and truss counts on 40 plants.

| Measured, 2023 | Reduced-State TOMGRO | Vanthoor's model |
| --- | --- | --- |
| `DW whole plant`, per plant | `w` | `c_leaf` + `c_stem` + `c_fruit` (+ `c_buf`), as dry matter by GreenLight's convention |
| `DW fruits`, per plant | `wf` | `c_fruit` |
| `DW leaves`, `DW stem` | none: `w` is not split | `c_leaf`, `c_stem` |
| Leaf area per plant, times the density | `lai` | `lai` (from `c_leaf` and its specific leaf area) |
| Leaf counts | `n`, as nodes: a leaf per node is an approximation | none |

## What this leaves to decide

For the decision record, before any run is compared with 2024's fruit:

- the split: calibrate on 2023 and test on 2024, or within 2024 by
  compartment, or both (the AGC4 memo, §4);
- the initial state: 2023's transplants, scaled to 2024's density, or the
  models' own;
- which parameters are calibrated, against which measurements, by which
  method, and what stays the published value;
- the density's handling, as above, and the day of the clock change;
- the dry-matter fraction, and for Vanthoor's model the carbohydrate
  convention;
- which measured quantity each model is held to (fruit per plant at each
  date; red fruit at the final harvest for Reduced-State TOMGRO), the
  metrics, and a baseline that a model should beat to be worth its
  complexity.
