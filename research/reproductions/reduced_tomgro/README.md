# Reduced-State TOMGRO, reproduced

Milestone A of decision
[0060](../../../docs/decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md)
for Reduced-State TOMGRO (Jones, Kenig and Vallejos 1999,
[doi:10.13031/2013.13203](https://doi.org/10.13031/2013.13203)): an
implementation written on its own, outside the packages, compared on the
same drivers with a pinned reference implementation.

## What is compared

- **The variant:** Oliveira et al.'s. It follows the paper and Jones et
  al. (1991), and Jones's spreadsheet where they differ. The inventory
  ([reduced-tomgro-inventory.md](../../../docs/research/reduced-tomgro-inventory.md))
  lists its forms and where they depart from the paper. The paper's full
  text was not read.
- **The reference:** Oliveira et al.'s
  [data-assimilation-tomato-models](https://github.com/mnqoliveira/data-assimilation-tomato-models),
  release v0.4.0, commit `b9b2c80`,
  [doi:10.5281/zenodo.13294322](https://doi.org/10.5281/zenodo.13294322),
  MIT. Its `run_simul` runs unmodified, in an environment of its own.
- **The implementation:** [`model.py`](model.py), plain Python floats,
  written from those equations, not from the reference's code. It imports
  nothing of the simulator's.
- **What both run with:** [`manifest.json`](manifest.json):
  - the parameter set `gnvman` (the developers' calibration for their
    Gainesville data) and the inputs `gnv_n01` (LAI at most 4, 3.5 plants
    per m²), each value with its unit and source;
  - the initial state;
  - the drivers and their sha256;
  - the step;
  - the tolerances.
- **The drivers:** [`drivers.csv`](drivers.csv), written by
  [`drivers.py`](drivers.py). A synthetic season of 120 days, hour by
  hour:
  - the air's mean warming from 18 to 25 °C, with a day's swing of 4.5 °C;
  - PPFD up to 900 µmol m⁻² s⁻¹ from 06:00 to 18:00, varied by a week's
    cycle of cloud;
  - CO₂ at 420 ppm by day and 520 by night.

  The warming carries the daytime past the fruit's critical temperature,
  so the hot-day branch is exercised. The model reads CO₂ from each day's
  first hour, so the night's value counts.

## The result

Both implementations agree on every state and every day, within the
tolerances fixed before the run: 1e-9 relative and 1e-12 absolute.

| State | Unit | Day 120 (reference) | Largest difference | On day |
| --- | --- | --- | --- | --- |
| n | nodes | 51.355 | 0 | — |
| lai | m² m⁻² | 4.0 (its most) | 2.8e-17 | 16 |
| w | g dry weight m⁻² | 895.56 | 1.1e-13 | 81 |
| wf | g dry weight m⁻² | 368.43 | 6.9e-18 | 49 |
| wm | g dry weight m⁻² | 288.85 | 1.8e-15 | 65 |

The differences are floating point's, from the order of the sums.
[`tests/test_reproductions.py`](../../../tests/test_reproductions.py)
holds the agreement on every run of the root tests. It also checks that the
comparison catches a parameter moved by a millionth and refuses drivers
other than the pinned ones. Reading the day's mean CO₂ in place of its
first hour's fails it.

**What it shows:** this implementation computes what Oliveira et al.'s
does, on these drivers.

**What it does not show:**
- that either matches the 1999 paper where the paper and the spreadsheet
  differ;
- that the model is right for a greenhouse: that is milestone C, on
  measured data;
- anything about the model driven by the run, which is milestone B.

## Running it again

```bash
# The reference, in a folder of its own: its archive checked, unpacked,
# and an environment with what it imports.
source=$(research/reproductions/reduced_tomgro/reference/setup.sh /tmp/tomgro-reference)
/tmp/tomgro-reference/venv/bin/python -I \
    research/reproductions/reduced_tomgro/reference/run_reference.py \
    "$source" research/reproductions/reduced_tomgro/drivers.csv \
    research/reproductions/reduced_tomgro/reference/output.csv

# This implementation, against it.
python -m research.reproductions.reduced_tomgro.compare
```

`reference/output.csv` is the reference's output on these drivers, kept so
that the comparison runs without the reference. It is the work of
Oliveira et al.'s MIT-licensed code (Copyright (c) 2022 Monique Oliveira),
run here unmodified.
