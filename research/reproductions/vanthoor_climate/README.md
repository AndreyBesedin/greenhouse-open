# Vanthoor's greenhouse climate, its fluxes at the same states

The house air's `vanthoor` model (P24.3, decision
[0078](../../../docs/decisions/0078-a-multi-node-climate-is-a-model-of-the-houses-air-chosen-by-the-manifest.md))
writes Vanthoor's (2011, chapter 8, [edepot.wur.nl/170301](https://edepot.wur.nl/170301))
heat and vapour fluxes from the thesis and from GreenLight's published
definitions (Katzin 2021, [doi:10.18174/544434](https://doi.org/10.18174/544434)),
in `greenhouse_sim/greenhouse_sim/climate/vanthoor.py`. Its fluxes are held to
GreenLight's own, evaluated at the same states.

## What is compared

- **The reference:** [GreenLight](https://github.com/davkat1/GreenLight) 2.0.7,
  BSD 3-Clause Clear, its wheel checked by its sha256, set up by the crop
  reproduction's [`setup.sh`](../vanthoor_katzin/reference/setup.sh) in an
  environment of its own. Nothing in the repository imports it.
- **What is evaluated:** [`reference/fluxes.py`](reference/fluxes.py) reads the
  chapter 8 definitions from the installed wheel,
  `models/katzin_2021/definition/vanthoor_2011/greenhouse_vanthoor_2011_chapter_8.json`,
  and evaluates each flux of the model's frame by its own definition and its
  own functions, at four cases of states and inputs, every other variable at its
  definition's value: the Netherlands house, with no screen drawn and none
  permanent.
- **The fluxes:** the air and the cover's inside by free convection
  (`hTopCovIn`), the water condensing on it and its latent heat (`mvTopCovIn`,
  `lTopCovIn`), the conduction through the cover (`hCovInCovE`), the cover's
  outside and the outside air (`hCovEOut`), the cover and the sky (`rCovESky`),
  the sun the cover absorbs (`rGlobSunCovE`), and the roof's coefficients and
  heat capacity.
- **What they are held to:** `greenhouse_sim/tests/test_covered_house.py`,
  each per m² of floor as GreenLight gives it, exactly, but for two departures
  the model states: the conduction through the cover and its heat capacity are
  per m² of the cover itself, and the saturation pressure is Buck's, so that
  condensation agrees to 2 %.

## Running it again

    research/reproductions/vanthoor_katzin/reference/setup.sh <folder>
    <folder>/venv/bin/python -I research/reproductions/vanthoor_climate/reference/fluxes.py \
        research/reproductions/vanthoor_climate/reference

It writes `reference/fluxes.json`, which is committed as it is written.
