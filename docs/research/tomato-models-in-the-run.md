# The two tomato models in the run

What the two published tomato models predict as crop models of the run
(decision
[0060](../decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md),
milestone B), and how the run's way of driving them moves them. Item 4 of
the [research priorities](../roadmap/research-validation-priorities.md)
asks for both. Reduced-State TOMGRO's season is documented with
[P14.10](../roadmap/archive/p14-models-by-manifest.md#reduced-state-tomgro-in-a-season-p1410).

Every number here is a prediction, not validated on measured data
(milestone C). It holds for the version of each model and driver profile
named. A test holds the season's numbers to the run; the measurement's
are recorded, not held.

## Vanthoor's model in a season

The Vanthoor house
(`greenhouse_sim/greenhouse_sim/scenarios/manifests/vanthoor_house.json`)
is the TOMGRO house with a different crop and seed. It keeps the
reference greenhouse's house, season, daily schedule and controller, and
the whole house's air as one well-mixed volume. Its four rows grow
Vanthoor's model as Katzin simplified it, by area, each row a scope
([0062](../decisions/0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md)):

- **Its crop:** `vanthoor_katzin`, version 1, with GreenLight 2.0.7's
  parameters (`greenlight_2_0_7`), each with its unit and source in
  [its reproduction's manifest](../../research/reproductions/vanthoor_katzin/manifest.json).
  It is driven through the `house_hours` profile, version 1, an hour at a
  time, and its canopy's light is read 2 m above its planting positions.
  Its fruit is harvested, and its leaves pruned, by the model's own rules.
  It takes no crop work.
- **Its seed:** 4202, its own. Its weather follows the reference
  greenhouse's season, and wanders from the TOMGRO house's on days of its
  own.
- **Its run:** a season's takes some three minutes.

**What it predicts,** in carbohydrate equivalents (g CH₂O m⁻² of floor),
never dry matter. Where two values are given, the first is rows 1 and 3,
the second rows 2 and 4, which take less light; the pairs differ in the
fourth digit at most.

| Day | Leaf area index | Buffer | Fruit standing | Leaves | Stems | Fruit harvested |
| --- | --- | --- | --- | --- | --- | --- |
| 30 | 2.58 | 10.1 / 7.5 | 146 / 145 | 97.2 / 97.1 | 118 / 121 | 0 |
| 60 | 2.59 / 2.55 | 2.0 / 0.2 | 287 / 285 | 97.4 / 96.0 | 216 / 201 | 273 / 210 |
| 90 | 2.57 / 2.56 | 0.25 / 0.24 | 285 | 96.4 / 96.3 | 281 / 242 | 797 / 585 |
| 120 | 2.58 | 11.0 / 10.0 | 287 | 97.0 | 314 / 282 | 1252 / 1018 |

The temperature sum is 515, 1073, 1701 and 2399 °C day on those days. The
canopy's mean over the last day rises from 17.6 to 23.2 °C, and between
days 1 and 120 it stays between 16.5 and 26.9 °C.

- **The leaves** reach a leaf area index of 2.58 within the first month,
  and stay there. That is under the most, 3, so they are never pruned:
  their growth and their maintenance balance. The reproduction's season
  peaks at 2.59 too.
- **The fruit** fills to near the most left unharvested, 300 g, and from
  day 43 it is harvested about as fast as it grows. The crop is fully
  generative by its temperature sum from day 59.
- **The buffer** runs nearly empty from the second month to the third, as
  the fruit draws on it, and fills again by the season's end, in June's
  long days.
- **The light:** rows 2 and 4 harvest a fifth less than rows 1 and 3 by
  the season's end, and grow less stem. Their leaves and fruit standing
  are the same.

`greenhouse_sim/tests/test_vanthoor_house.py` holds days 60 and 120 to
the run, and marks the test slow.

**What these numbers are:** predictions. The viewer draws each row as a
canopy, marked as a proxy, with its numbers marked as predictions. They
are not comparable with the TOMGRO house's: carbohydrate equivalents are
not dry matter, and no conversion between the two is applied (decision
0060). They also rest on how the run drives the model, which the
reproduction does not cover:

- the canopy's temperature is the house air's, hour by hour;
- the PAR is the light above each row's canopy, under the house's glazing
  and structure;
- the CO₂ is the house air's, which the crop takes none of, since the
  coupling is one-way;
- each driver is the hour's mean, held through the hour.

How far that profile moves each model is measured below.

## What the driver profile changes

[`research/integrations/driver_profiles`](../../research/integrations/driver_profiles/README.md)
measures the `house_hours` profile, version 1, for both models, as
decision 0062 asks: against each reproduction's own forcing, and with a
canopy's temperature. The canopy's temperature comes from GreenLight's own
greenhouse, simulated through 109 days of a Dutch winter under
high-pressure sodium lamps. There the canopy is 0.40 °C cooler than the
air on average, from 3.1 °C cooler to 5.9 °C warmer.

- **Hour means** in place of the reference's resolution:
  - Vanthoor's model moves by up to 0.68% of a mass on its reproduction's
    season, held by `test_vanthoor.py`. In GreenLight's greenhouse it moves
    by 0.23 g CH₂O m⁻² of any mass at most, and 0.10% of its harvest.
  - Reduced-State TOMGRO does not move: its reference takes hourly
    values.
- **The air's temperature for the canopy's:**
  - Vanthoor's model reads the canopy's, which the profile replaces. Its
    temperature sum runs 2.1% ahead by day 109, its stems end 1.4%
    lighter, and its harvest is 0.12% ahead. The fruit grows faster early,
    by up to 4.5 g CH₂O m⁻².
  - Reduced-State TOMGRO reads the air's, which the profile gives as it
    is. Given the canopy's instead, as a sensitivity, its fruit ends 7.5%
    lighter and its mature fruit 9.9%.

That is one simulated greenhouse and season. A sunlit, vented house moves
its canopy from its air otherwise, and no test holds these numbers: the
simulation is GreenLight's, of its publisher's weather, and is not
committed.
