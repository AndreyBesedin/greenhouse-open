# 0076: The tomato models are calibrated on AGC4's pre-trial and tested once on its challenge

**Status:** Proposed
**Date:** 2026-11-10

## Context

Decision 0057 has a published model reproduced, then integrated, then
validated on measured data, and asks a validation to fix its calibration
and test data before any tuning. The research priorities leave four
choices to be made before that work starts: which measured data constrain
the models, the first splits, the metrics, and, for a reproduction, its
tolerances. Both tomato models have passed their first two milestones
(decision 0060): Reduced-State TOMGRO and Vanthoor's model as Katzin
simplified it are reproduced and are crop models of the run. Their
outputs are predictions until the third.

Three memos prepare the choice:

- [The AGC4 memo](../research/agc4-coverage.md) inventories the WUR
  Autonomous Greenhouse Challenge, 4th edition, CC BY 4.0. The 2024
  challenge grew a dwarf cherry tomato in six compartments, each under
  another team's control, and weighed its fruit per plant, fresh, three
  times and at the final harvest. The 2023 pre-trial grew one under four
  light and two EC treatments, and measured its organs' dry weights and
  leaf area at four dates. The memo lists the splits possible and what
  each leaks.
- [The profile](../../research/validation/agc4/README.md) counts what the
  files hold. The drivers a crop model reads miss 13 rows in each 2024
  compartment. There is no dry weight per plant in 2024: one batch of
  red fruit per compartment was dried, and one of green in three.
- [The mapping memo](../research/agc4-model-mapping.md) maps each model's
  drivers to AGC4's columns, and each output to a measurement. It names
  three conversions (per m² to per plant, carbohydrate to dry matter, dry
  to fresh), with candidate values, and lists what is left to decide.

Oliveira et al.'s greenhouse tomato observations, the other dataset the
priorities name, are CC BY-NC 4.0, and their non-commercial term is to be
assessed before anything derived from them is published (decision 0060).

## Decision

**AGC4 first.** The first validation of both tomato models uses AGC4
alone. Oliveira et al.'s observations wait for their licence's
assessment, and are a validation of their own.

**Calibrate on the 2023 pre-trial; test once on the 2024 challenge.**

- *Calibration data:* the pre-trial's destructive samples, per plant and
  per treatment: the dry weight above ground, of the fruit, of the leaves
  and of the stem, and the leaf area. Each treatment is run with its own
  zone's PAR. Neither model reads EC, so a light level's two EC
  treatments are two measurements of one prediction.
- *Test data:* every 2024 fruit measurement of all six compartments: the
  three samplings' fruit per plant, and the final harvest's fruit per
  plant over the plants weighed whole, for both models; and, for
  Reduced-State TOMGRO alone, the final harvest's red fruit over the 50
  plants weighed for it, held to its mature fruit. Vanthoor's model tells
  no ripeness, so it has no red fruit to compare. None of it is read before
  the test, nor any 2024 dry matter.
- *Once:* each model runs the test once, with the calibrated parameters,
  and its result is reported whatever it is. A model changed after its
  test, and tested again, reports both tests, the first kept.
- *Why by year:* the 2024 fruit is the only fruit to test on, and the
  pre-trial holds the vegetative and organ data a calibration needs. A
  split by compartment within 2024 would spend part of the only test on
  calibration, among six compartments that share their weather, start and
  cultivar. The test then also measures how far a calibration carries
  from one year to the next. Two limits are recorded with the result: the
  cultivars of the two years are not known to be the same, and the
  pre-trial varies light and EC, not temperature or CO₂.

**At most four parameters per model are calibrated, named before.** Each
calibration commits a manifest before it runs. The manifest names its
parameters, each with its bounds and why it is chosen, and its targets,
objective, starting values and method. Every other parameter keeps its
published value. The objective is the sum, over the calibration targets,
of the squared natural logarithm of (predicted + c) over (measured + c),
each per plant. For each quantity, c is half the smallest value above
zero measured of it in the calibration data. A target measured as zero is
kept, since fruit not yet set is itself a measurement. A prediction of
zero then still gives a finite residual. A target with no measurement is
no target. Each quantity weighs the same, so no one quantity's scale
dominates. A calibrated parameter set is kept apart from the model's
published defaults, with its source and its data, and is never one of
them.

**The conversions are fixed here.**

- *Per plant:* a model's value per m² of floor, divided by the density in
  force on the day measured.
- *Spacing:* the harness that runs a model on AGC4 multiplies every state
  per m² of floor (the masses, the leaf area index) by the new density
  over the old at each spacing's midnight. Reduced-State TOMGRO's nodes,
  per plant, are left as they are, and its ρ follows the density.
- *Initial state:* the 2023 transplants' per plant, for both years. They
  had 0.111 g of dry weight above ground (0.068 g leaves, 0.043 g stem),
  35.1 cm² of leaf and five leaves, scaled to the density at
  transplanting. Reduced-State TOMGRO starts at five nodes, with no
  fruit. Vanthoor's model takes the leaves' and stem's dry weight as its
  carbohydrate, by the convention below, with no fruit. Its buffer's
  initial value is its calibration manifest's to set: the published one,
  20 g CH₂O m⁻², is three times the whole transplant's dry weight per m²
  at 56 plants/m².
- *Carbohydrate to dry matter,* for Vanthoor's model: one for one, as
  GreenLight 2.0.7's own yield takes them. Reduced-State TOMGRO's 0.75 is
  reported as a sensitivity.
- *Vanthoor's fruit* is its standing fruit plus its harvested fruit, in
  the calibration and the test alike: AGC4 picked nothing from a plant
  before it was measured. Its leaves pruned past a leaf area index of 3
  are kept in no state, and AGC4 pruned none, so a run that prunes says so
  beside its comparisons.
- *Dry to fresh:* the pre-trial's fruit dry-matter fraction at its last
  date, 8.0 %, the mean over 48 plants of `DW fruits` over
  `FW fruits clusters`. It is the calibration year's own measurement,
  mostly of green fruit, cluster stems included. GreenLight's assumed 6 %
  and the range of 2024's red batches are reported as sensitivities. No
  2024 batch is used in the headline result, since each is a measured
  output of its compartment.
- *Hours and days:* each driver is the mean of the 5-minute rows stamped
  inside its hour. Days are taken at a fixed UTC+01:00, so that every day
  has 24 hours. An hour with no rows takes the previous hour's means; that
  happens once in 2024, the repeated hour of 27 October, and twice in
  2023, both of 29 October's 02:00 hours, which the pre-trial's wall-clock
  times cannot tell apart. A 2024 run starts
  at 00:00 UTC+01:00 on 3 September, an hour after its files begin. A
  2023 run starts at 00:00 UTC+01:00 on 5 September, the first whole day
  of its climate, from the state sampled on 4 September.
- *Timing:* a measurement is compared with the model's state at the
  midnight that begins its day. For a sampling, the midnight after is
  reported beside it, as the timing's uncertainty. A 2024 compartment's
  file ends at 12:00 on its harvest day, so no run goes past the midnight
  before its final harvest.

**The metrics, for each model.**

- *Per compartment and date:* the prediction, the measured mean per plant
  with its standard error and its count of plants, the error, and the
  relative error.
- *Over the test:* the mean relative error (the bias), the root mean
  square of the relative errors, and how many of the 24 compartment-dates
  of fruit per plant fall within two standard errors of their
  measurement. Reduced-State TOMGRO's six red-fruit comparisons are
  reported apart, with the same measures, and are not pooled with them.
- *Across the six final harvests:* Spearman's rank correlation between
  predicted and measured fruit per plant: whether the model orders the
  teams' strategies as their crops came out. A shared conversion factor
  does not move it.
- *Against a baseline:* the skill, one minus the model's sum of squared
  errors over the baseline's. The baseline gives every compartment the
  pre-trial crop's fruit per plant at the same days after transplanting:
  the mean of its EC3 treatments (2024's EC was 2.8), linear between its
  destructive dates, from none at transplanting, and on past its last
  date at its last interval's rate. It uses no 2024 fruit. A model that
  does not beat it has not shown that it uses each compartment's climate.
- *With them:* the run times, the sample counts, the rows missing, and
  each difference of definition between a model's output and the
  measurement.

No tolerance makes a model pass. A validation reports how far a model is
from the data, and a claim made of a model's outputs is bounded by that
report.

**Where it lives.** The harness, its manifests and its results are under
`research/validation/agc4/`, outside the packages (the research
priorities). Data stays downloaded, not committed: what is committed is
numbers and checksums, as the profile's are.

## Consequences

- The work follows in this order, each step its own pull request:
  1. the drivers, built per 2024 compartment and per 2023 treatment from
     the archives, with their checksums;
  2. the harness, which runs either model on them with the spacing and
     initial state above;
  3. each model's calibration manifest, committed before its calibration
     runs;
  4. the calibration, with its fit on the calibration data;
  5. the test, run once, and its report.
- Neither model's published defaults change, and the run's crop models do
  not change with this decision: a calibrated set is a research result
  until crop parameters become versioned assets (P20).
- The test's numbers are claims about AGC4's dwarf pot plants, grown for 69
  to 79 days. They say nothing of an indeterminate crop picked through a
  season.
- Some known weaknesses are accepted, and reported with the result rather
  than corrected:
  - the 8.0 % fraction is mostly green fruit, while the final harvest is
    mostly red;
  - the PAR sensor is at a fixed height;
  - the canopy's temperature is the air's;
  - spacing changes each plant's light, and the models see that only
    through their leaf area.
- A later validation, on Oliveira et al.'s data, or within 2024 by
  compartment, is a decision of its own. It does not replace this test.
