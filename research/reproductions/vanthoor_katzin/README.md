# Vanthoor's tomato model, reproduced

Milestone A of decision
[0060](../../../docs/decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md)
for Vanthoor's tomato yield model as Katzin simplified it (Vanthoor 2011,
chapter 9, [edepot.wur.nl/170301](https://edepot.wur.nl/170301); Katzin
2021, [doi:10.18174/544434](https://doi.org/10.18174/544434)): an
implementation written on its own, outside the packages, compared on the
same drivers with a pinned reference implementation.

## What is compared

- **The variant:** GreenLight's. It is its crop definition and its
  standalone extension, as its `main_vanthoor_crop.json` composes them.
  The inventory
  ([vanthoor-katzin-inventory.md](../../../docs/research/vanthoor-katzin-inventory.md))
  lists its states, parameters and equations, and where they depart from
  the thesis.
- **The reference:** [GreenLight](https://github.com/davkat1/GreenLight)
  2.0.7, commit `d6282a1`, BSD 3-Clause Clear. Its wheel is checked by its
  sha256, and its load, solve and save run unmodified, in an environment of
  their own.
- **The implementation:** [`model.py`](model.py), the right-hand side in
  plain Python floats, written from those equations, not from GreenLight's
  code. It imports nothing of the simulator's. It is solved as the
  reference solves it: scipy's BDF, with the same step limit and
  tolerances. Every output is then interpolated linearly onto the hourly
  moments, as the reference's save does.
- **What both run with:** [`manifest.json`](manifest.json):
  - the parameters and the initial state, each value with its unit and
    source;
  - the drivers and their sha256;
  - the two solvers' settings;
  - what is compared, with its tolerances.
- **The drivers:** [`drivers.csv`](drivers.csv), written by
  [`drivers.py`](drivers.py). They are the numbers of the
  [TOMGRO reproduction's](../reduced_tomgro/README.md) synthetic season,
  120 days hour by hour, so that both models are driven alike:
  - its air temperature as the canopy's;
  - its PPFD inside as the PAR above the canopy;
  - its CO₂.

  They are interpolated linearly between hours. Up to the second hour the
  first is held, as GreenLight does.
- **What the season exercises:**
  - the temperature sum passes the fully generative crop's on day 53;
  - the fruit is harvested from day 48, as it nears its most unharvested;
  - the canopy's last day is warmer than its upper limit on ten days;
  - the buffer empties on day 61 (its least is −1.4 mg CH₂O m⁻², which the
    smooth switch allows).

  The leaf area index peaks at 2.59, under its most of 3, so the leaves
  are pruned only at the switch's low end.

## The results

There are three comparisons, each against the reference's kept output on
these drivers.

**The rates, at the same states:** the six states' rates of change at 2,879
points. Each point is half an hour between output moments, at states from
the converged run. GreenLight's rates are the function it hands to
`solve_ivp`. No solver step stands between the two. They agree within 1e-9
relative or 1e-12 absolute. The largest difference is 1.7e-16 mg CH₂O m⁻²
s⁻¹, about one unit in the last place.

**The run, with GreenLight's default solver** (BDF, `rtol` 1e-6, `atol`
1e-3), against the tolerances declared before the first run:

| Output | Unit | Largest difference | Allowed there | Verdict |
| --- | --- | --- | --- | --- |
| cBuf | mg CH₂O m⁻² | 12.7 | 1 | beyond |
| cFruit | mg CH₂O m⁻² | 0.46 | 3.8 | within |
| cLeaf | mg CH₂O m⁻² | 1.6 | 9.5 | within |
| cStem | mg CH₂O m⁻² | 1.7 | 18.6 | within |
| tCanSum | °C day | 6.2e-3 | 1e-3 | beyond |
| tCan24 | °C | 4.2e-3 | 1e-3 | beyond |
| lai | m² m⁻² | 4.2e-5 | 1e-5 | beyond |
| harvested fruit | mg CH₂O m⁻² | 0.92 | 1.0 | within |

The four differences beyond their tolerances are the solver's, not the
equations':
- The rates agree to the last place.
- At these settings, GreenLight does not reproduce itself to those
  tolerances. Its own outputs move by as much when its `rtol` moves by one
  part in 10⁷, to 1.0000001e-6: cBuf by 14.8 mg CH₂O m⁻², tCanSum by
  6.1e-3, tCan24 by 3.6e-3, and the leaf area index by 5.0e-5.
- Two runs of the same equations take different steps from the first
  difference in the last place. At these tolerances, their answers then
  differ by this much.
- tCanSum integrates the drivers alone, so its exact value is known. Both
  answers are 8 to 9e-3 °C day from it.

The tolerances stay as declared, and the defaults' comparison is recorded
as this result, not held.

**The run, with a converged solver** (BDF, `rtol` 1e-10, `atol` 1e-7), against
the same tolerances. These settings were declared after the first run. They
are the loosest of the three tried (`rtol` 1e-8, 1e-9 and 1e-10, each with
`atol` a thousand times it) at which GreenLight's own outputs move by less
than a tenth of each tolerance when its `rtol` moves by one part in 10⁷.

| Output | Largest difference | Share of what is allowed there |
| --- | --- | --- |
| cBuf | 0.039 mg CH₂O m⁻² | 0.039 |
| cFruit | 0.045 mg CH₂O m⁻² | 0.0016 |
| cLeaf | 4.2e-3 mg CH₂O m⁻² | 0.0015 |
| cStem | 3.2e-3 mg CH₂O m⁻² | 0.0016 |
| tCanSum | 8.3e-5 °C day | 0.083 |
| tCan24 | 8.1e-5 °C | 0.081 |
| lai | 3.6e-7 m² m⁻² | 0.036 |
| harvested fruit | 0.018 mg CH₂O m⁻² | 0.0047 |

On day 120, the reference's converged run has:
- 284.9 g CH₂O m⁻² of fruit standing;
- 612.5 g CH₂O m⁻² harvested since the start;
- a leaf area index of 2.48.

All of these are carbohydrate equivalents, never dry matter.

**Run times,** on one laptop: ours took 2.5 s with the defaults and 10 s
converged, and GreenLight took 4.8 s and 19.5 s.

[`tests/test_reproductions.py`](../../../tests/test_reproductions.py)
holds the rates on every run of the root tests, and the converged run
where the slow tests run (CI). It also checks that the rates catch a
parameter moved by a millionth, and that drivers other than the pinned
ones are refused. Three changes to `model.py` each fail the rates:
- the leaves' published pruning rate, 5e4, in place of GreenLight's 1e5;
- the first hour interpolated rather than held;
- Γ's reference temperature moved by a millionth.

**What it shows:** this implementation's equations are GreenLight's, and,
solved tightly, give its answer on these drivers.

**What it does not show:**
- that GreenLight follows Vanthoor's thesis where the inventory lists a
  departure;
- that the model is right for a greenhouse: that is milestone C, on
  measured data;
- anything about the model driven by the run, which is milestone B.
  There, the solver's settings matter: at GreenLight's defaults, a run is
  reproducible only to the first table's spread.

## Running it again

```bash
# The reference, in a folder of its own: its wheel checked, and an
# environment with what its run imports.
research/reproductions/vanthoor_katzin/reference/setup.sh /tmp/greenlight-reference
mkdir -p /tmp/greenlight-reference/scratch
/tmp/greenlight-reference/venv/bin/python -I \
    research/reproductions/vanthoor_katzin/reference/run_reference.py \
    research/reproductions/vanthoor_katzin/drivers.csv \
    research/reproductions/vanthoor_katzin/reference \
    /tmp/greenlight-reference/scratch

# This implementation, against it.
python -m research.reproductions.vanthoor_katzin.compare
```

The reference's three outputs come back byte for byte. They are
`reference/defaults.csv`, `reference/converged.csv` and
`reference/rates.csv`, its outputs on these drivers, kept so that the
comparison runs without the reference. They are the work of GreenLight's
BSD 3-Clause Clear-licensed code (Copyright (c) 2025 David Katzin,
Wageningen Research Foundation), run here unmodified.
