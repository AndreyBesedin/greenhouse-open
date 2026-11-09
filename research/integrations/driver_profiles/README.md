# What the first driver profile changes

Decision
[0062](../../../docs/decisions/0062-a-crop-model-declares-its-scope-drivers-outputs-and-capabilities.md)
gives a crop model grown by area its drivers through a named, versioned
profile. It asks that the profile's effect on a model's results be
measured and reported, against the reference's own resolution and against
a canopy temperature. This measures the first profile, `house_hours`,
version 1 (`greenhouse_sim/greenhouse_sim/core/drivers.py`), for both
published tomato models (decision
[0060](../../../docs/decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md),
milestone B).

The profile changes two things against what each model's reference takes:

- **The resolution:** each driver is the hour's mean, held through the
  hour.
  - Vanthoor's model's reference, GreenLight, runs its drivers straight
    between their moments.
  - Reduced-State TOMGRO's reference takes hourly values and sums them
    over the day, which the profile's hours give as they are.
- **The temperature:** the house has no canopy temperature, so the air's
  stands for it.
  - Vanthoor's model reads the canopy's, so the profile substitutes the
    air's and says so (`DriverProfile.substitutes`).
  - Reduced-State TOMGRO reads the air's, which the profile gives with no
    substitution.

## On the reproductions' own forcing

This is the synthetic season both reproductions share
([`reduced_tomgro`](../../reproductions/reduced_tomgro/README.md),
[`vanthoor_katzin`](../../reproductions/vanthoor_katzin/README.md)): 120
days, hour by hour. Its air temperature stands for the canopy's, so only
the resolution can be measured on it.

- **Vanthoor's model:** given each hour's mean in place of the drivers
  running between hourly moments, it moves by up to 0.68% of a mass, and
  0.30% of the fruit harvested by the season's end.
  `greenhouse_sim/tests/test_vanthoor.py` holds it to that
  (`test_driven_by_hour_means_it_stays_within_what_the_means_change`).
- **Reduced-State TOMGRO:** nothing moves. Its forcing is hourly means
  already (`tmean`), and its rung reads them as its reference does,
  `greenhouse_sim/tests/test_tomgro.py` holding it on every state and day.

## With a canopy's temperature

The reproductions' forcing has no canopy temperature, so this uses a
greenhouse that has one: GreenLight 2.0.7's own greenhouse, Katzin
(2021)'s, with Vanthoor's crop and high-pressure sodium lamps, run
unmodified on the Bleiswijk weather its wheel ships. The weather runs
from 20 October 2009, through 109 whole days. GreenLight works out the
air's and the canopy's temperatures by its energy balance, every 5
minutes. **They are simulated, not measured:** the trial behind the
weather measured the air, not the canopy (Katzin et al.'s 4TU data,
[doi:10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2](https://doi.org/10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2)).

- **The canopy against the air,** every 5 minutes:
  - The canopy is 0.40 °C cooler on average, from 3.06 °C cooler to
    5.85 °C warmer.
  - Under the lamps alone, 36% of the time, it is 0.63 °C cooler on
    average, and never warmer.
  - In the dark, 23% of the time, it is 0.55 °C cooler.
  - In the sun it is as warm on average. Its warmest is under the sun.
- **The drivers:** the PAR above the canopy is the sun's and the lamps',
  each by GreenLight's own conversion to µmol (4.6 and 5.4 µmol J⁻¹). Its
  mean is 198 µmol m⁻² s⁻¹. The CO₂ is the air's, 917 ppm on average.

Each model is the package's rung, grown from its planted state. Its
values are per m² of floor at day 109, with the largest difference
through the season and its day. Vanthoor's quantities are carbohydrate
equivalents (mg CH₂O m⁻²), and TOMGRO's are dry weights (g m⁻²).

**First, the forcing read as GreenLight's crop reads it.** Vanthoor's
model is given the canopy's drivers running straight between the 5-minute
moments. Set against GreenLight's own crop in the same run, it agrees to
134 mg of 285 g of fruit (0.05%), 12 mg of 96 g of leaf, and 62 mg of
298 g of stem. The buffer agrees to 108 mg, small beside its 20 g most. The
temperature sum agrees to 0.03 °C day of 2101. GreenLight runs at its
default solver here, which reproduces its own temperature sum only to some
6e-3 °C day (the reproduction's README), and its canopy's temperature is
read every 5 minutes.

**Vanthoor's model:**

| Output | 5 min, canopy | Hour means, canopy | Hour means, air (the profile) | Air against canopy, largest |
| --- | --- | --- | --- | --- |
| Fruit standing | 284.678 g | 284.683 g | 284.674 g | 4.5 g, day 33 |
| Leaves | 95.893 g | 95.894 g | 95.872 g | 0.39 g, day 5 |
| Stems | 297.58 g | 297.78 g | 293.50 g | 4.3 g, day 109 |
| Buffer | 0.223 g | 0.224 g | 0.219 g | 1.6 g, day 22 |
| Fruit harvested | 1003.3 g | 1004.3 g | 1005.5 g | 5.1 g, day 49 |
| Temperature sum | 2101.4 °C d | 2101.4 °C d | 2145.3 °C d | 43.9 °C d, day 109 |
| Last day's canopy | 18.80 °C | 18.80 °C | 19.20 °C | 1.1 °C, day 3 |
| Leaf area index | 2.5508 | 2.5508 | 2.5502 | 0.010, day 5 |

- **The resolution** (hour means against 5 minutes, both the canopy's)
  moves no mass by more than 0.23 g, and the harvest by 1.0 g (0.10%) by
  the end.
- **The air for the canopy** moves the model five to twenty times as much:
  - The temperature sum runs 44 °C day (2.1%) ahead by day 109.
  - The last day's temperature runs up to 1.1 °C warm.
  - The stems end 4.3 g (1.4%) lighter.
  - The fruit grows faster and is harvested earlier: 4.5 g more fruit
    standing on day 33, and 5.1 g more harvested on day 49. By the end the
    harvest is 1.2 g (0.12%) ahead, as the fruit standing is held near its
    most unharvested and the harvest follows its growth.
- **The profile as it is** (hour means, air) against the reference's own
  drivers (5 minutes, canopy): the same as the air for the canopy, since
  the resolution's part is small. The harvest is 2.2 g (0.22%) ahead by the
  end, and the stems 4.1 g (1.4%) lighter.

**Reduced-State TOMGRO:** the profile gives what its reference takes, the
hour's mean air temperature, so it substitutes nothing for this model.
Given the canopy's temperature in the air's place, as a sensitivity and
not a correction, it grows by day 109:

| Output | Air (the profile) | Canopy in its place | Difference |
| --- | --- | --- | --- |
| Nodes | 44.44 | 43.89 | −1.2% |
| Leaf area index | 3.684 | 3.612 | −2.0% |
| Dry weight above ground | 919.5 g | 896.8 g | −2.5% |
| Fruit | 305.1 g | 282.1 g | −7.5% |
| Mature fruit | 190.9 g | 172.1 g | −9.9% |

Its nodes, and with them its fruit, follow the temperature, so a canopy
0.4 °C cooler slows its season by about a day in a hundred. Its fruit
moves by 8 to 10%, where Vanthoor's harvest moves by under 0.3%.

**What it shows:**
- In this greenhouse, the profile's hour means change the models little.
  The air standing for the canopy's temperature changes Vanthoor's model's
  temperature sum and stems by about 2%, and its harvest by under 0.3%.
- The forcing taken from GreenLight's greenhouse is the one its crop reads:
  driven by it, the package's rung agrees with GreenLight's crop.

**What it does not show:**
- **Another greenhouse:** this is one greenhouse, one season and one
  lighting, simulated. A canopy's departure from its air depends on the
  lamps, the screens, the cover's temperature and the transpiration. In a
  sunlit summer house, with its vents open, it differs.
- **The run's own house:** the run's house air is its own model's, not
  GreenLight's. This holds the run's house and its light apart, to
  measure the profile alone.
- **Validation:** the models' outputs here are predictions, as every
  output of milestone B is (decision 0060, milestone C).
- **A test:** none holds these numbers. GreenLight's simulation of the
  weather it ships is the reference's and the data's publisher's, under
  their licences (BSD 3-Clause Clear; the weather's source CC BY-SA 4.0).
  It is never committed (decision
  [0063](../../../docs/decisions/0063-a-data-file-is-generated-committed-or-fetched-by-one-rule.md),
  rule 1), and it takes ten minutes to make.

## Running it again

```bash
# The reference, as the Vanthoor reproduction sets it up.
research/reproductions/vanthoor_katzin/reference/setup.sh /tmp/greenlight-reference
mkdir -p /tmp/greenlight-reference/greenhouse
# GreenLight's greenhouse through its season, about ten minutes; it
# writes forcing.csv there.
/tmp/greenlight-reference/venv/bin/python -I \
    research/integrations/driver_profiles/reference/greenhouse.py \
    /tmp/greenlight-reference/greenhouse
# The package's rungs on it, a few seconds: the tables above.
python -m research.integrations.driver_profiles.measure \
    /tmp/greenlight-reference/greenhouse/forcing.csv
```

The run measured here took 9.5 minutes on one laptop, and wrote a
`forcing.csv` of sha256
`f7405fa39c04819cc97d9a4289989c8748804cf7365c880bd2c5f23df6c5a71e`. The
checksum is recorded, not checked: a solver's last digits may differ on
another machine.
