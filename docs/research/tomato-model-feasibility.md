# Which published tomato model to reproduce first

A feasibility memo for item 4 of the [research priorities](../roadmap/research-validation-priorities.md)
(decision [0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md)):
reproduce one published tomato model, and compare it with its original
implementation, before the simulator grows a crop by it. It compares two
candidates on what a reproduction needs, and recommends one first result.
No code comes with it. Decision
[0060](../decisions/0060-the-first-tomato-model-reproduced-is-vanthoors-as-greenlight-runs-it.md)
proposes the choice.

Checked on 2026-10-28. Where a source could not be read, this memo says so.

## The candidates

### Reduced-State TOMGRO

- **Source:** Jones, J. W., Kenig, A. and Vallejos, C. E. (1999), "Reduced
  state-variable tomato growth model", *Transactions of the ASAE* 42(1),
  255–265, [doi:10.13031/2013.13203](https://doi.org/10.13031/2013.13203).
  It reduces TOMGRO (Jones et al. 1991, *Transactions of the ASAE* 34(2),
  663–672, [doi:10.13031/2013.31715](https://doi.org/10.13031/2013.31715))
  to five states: the number of main stem nodes, the leaf area index, the
  total, fruit and mature fruit dry weight. It keeps TOMGRO's
  photosynthesis, respiration and development, with new relations for leaf
  area and dry matter.
- **Equations and parameters:** in the paper, behind the publisher's
  subscription; this memo did not read its full text. Its equations are
  restated in open papers, among them Fink et al. (2023), "Comparison of
  dynamic tomato growth models for optimal control in greenhouses",
  [arXiv:2308.06031](https://arxiv.org/abs/2308.06031). The paper reports
  vegetative parameters stable across its sites and fruit parameters
  varying with location.
- **Drivers:** daily, or hourly: the mean and daytime temperature, PAR and
  CO₂.
- **Validation data:** experiments in Florida and in Avignon. This memo
  found them published nowhere as data.
- **Original implementation:** this memo found none published by the
  authors. Third-party implementations exist; none was checked here, nor
  their licences.
- **A published result on open data:** Fink et al. (2023) ran it daily on
  the Autonomous Greenhouse Challenge's climate data, with Python and
  CasADi, and report that it overestimated biomass by about 2 kg m⁻²
  against the measurements. They publish no code.

### Vanthoor's tomato yield model, as GreenLight runs it

- **Source:** Vanthoor, B. H. E., de Visser, P. H. B., Stanghellini, C.
  and van Henten, E. J. (2011), "A methodology for model-based greenhouse
  design: Part 2, description and validation of a tomato yield model",
  *Biosystems Engineering* 110(4), 378–395,
  [doi:10.1016/j.biosystemseng.2011.08.005](https://doi.org/10.1016/j.biosystemseng.2011.08.005).
  Its full description is chapter 9 of Vanthoor's thesis, *A model-based
  greenhouse design method* (Wageningen University, 2011), an open PDF at
  [edepot.wur.nl/170301](https://edepot.wur.nl/170301).
- **The version reproduced:** simplified by Katzin (2021), *Energy saving
  by LED lighting in greenhouses: a process-based modelling approach*,
  thesis, Wageningen University,
  [doi:10.18174/544434](https://doi.org/10.18174/544434), and Katzin et
  al. (2020), "GreenLight – An open source model for greenhouses with
  supplemental lighting", *Biosystems Engineering* 194, 61–81,
  [doi:10.1016/j.biosystemseng.2020.03.010](https://doi.org/10.1016/j.biosystemseng.2020.03.010).
  Seven states: the carbohydrates in a buffer, the fruit, the leaves and
  the stems, the leaf area index, and two integrals of the canopy's
  temperature. About thirty parameters, from the thesis's tables 9.1 and
  9.2, each cited to its table in the implementation.
- **Drivers:** sub-daily: the canopy's temperature (°C), the PAR above the
  canopy (µmol m⁻² s⁻¹) and the CO₂ around it (ppm). The implementation's
  example inputs are at 5-minute steps.
- **Original implementation:** GreenLight, by its authors' group,
  [github.com/davkat1/GreenLight](https://github.com/davkat1/GreenLight),
  version 2.0.7 on PyPI (`greenlight`), in Python, under the BSD 3-Clause
  Clear licence. The crop model is
  `greenlight/models/katzin_2021/definition/vanthoor_2011/crop_vanthoor_2011_chapter_9_simplified.json`,
  and `main_vanthoor_crop.json` runs it alone, from given drivers, with
  no greenhouse. The repository's scripts regenerate Katzin et al.
  (2020)'s figures and tables.
- **Data:** Katzin et al.'s data on 4TU.ResearchData,
  [doi:10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2](https://doi.org/10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2),
  under CC BY-SA 4.0: the outdoor weather, the indoor climate and the
  climate control of a trial of cocktail tomatoes in Bleiswijk, under LED
  and under HPS lamps, from October 2009 to February 2010, and
  GreenLight's simulations of them. It holds no crop measurements.
  Vanthoor's validation data, from Dutch and southern Spanish greenhouses,
  were found published nowhere as data.

## Compared

| | Reduced-State TOMGRO | Vanthoor, as GreenLight runs it |
| --- | --- | --- |
| Equations | The paper (subscription); restated openly | The thesis (open) and the paper |
| Parameters, with their sources | The paper's table; fruit parameters by site | The thesis's tables, cited per parameter in the code |
| States and step | 5, daily | 7, sub-daily |
| Drivers | Mean and daytime temperature, PAR, CO₂ | Canopy temperature, PAR above the canopy, CO₂ |
| Original implementation to compare with | None found | GreenLight 2.0.7, BSD 3-Clause Clear |
| Measured data, open | None of the paper's found | Climate only (CC BY-SA 4.0); no crop measurements |
| Published outputs on open inputs | Fink et al. (2023), on the Challenge's data, without code | Katzin et al. (2020), climate and energy, regenerated by GreenLight's scripts |
| Size of the work | Small | Moderate |

## What the simulator gives a crop model today

A crop model is a rung of the run's crop part (`biology/crop_contract.py`,
P14.3). The run lives each plant a day at a time and gives it its day
(`LocalEnvironment`): the day's mean temperature, its PAR integral, its CO₂
and its water status. Its house's air is worked exactly through the day
(P11.2), and its plants' light by the hour (P08), but neither reaches the
crop below a day. The house's CO₂ follows the outside's through its vents;
no crop takes CO₂ up and nothing enriches it.

- **Reduced-State TOMGRO** would fit that day nearly as it is, with the
  day's daytime temperature added.
- **Vanthoor's model** needs the day's course: the crop part's contract
  would give a rung the air and light through the day. That is P14's work,
  after the reproduction, as the priorities have it: a model is reproduced
  on its own before the simulator grows a crop by it.

Neither is a model of single plants: both grow a canopy per square metre,
which the run's plants would share by their density. Neither represents
the crop work the organ model carries out, leaf by leaf and truss by truss.

## Recommendation

Reproduce **Vanthoor's model as GreenLight runs it** first. It is the only
candidate whose original implementation can be run on the same inputs,
which is decision 0057's stronger comparison; its equations and parameters
are open, with their sources; and the implementation and its data are
licensed for the use. Reduced-State TOMGRO comes second, as the simple
daily model beside it: its comparison can only be with published values,
and it fits the run's day as it is.

The first result:

1. **An independent implementation** of the crop model, written from the
   thesis's chapter 9 and Katzin (2021)'s simplifications, not ported from
   GreenLight's definitions, in a research folder outside the simulator's
   packages.
2. **The same drivers for both:** a fixed series of canopy temperature,
   PAR and CO₂ at 5-minute steps, such as the indoor climate of the 4TU
   dataset's HPS compartment, with its checksum.
3. **GreenLight 2.0.7's standalone crop run** on those drivers, as the
   reference, at a pinned version.
4. **The comparison:** each state's trajectory and the harvested dry
   matter, their differences reported with their causes, against a
   tolerance decided before the run.
5. **What it does not show:** that the model is right for a greenhouse.
   That needs measured crop data, item 5 of the priorities.

The experiment records its manifest as the priorities ask: the model and
its version, both implementations' versions, the drivers and their
checksum, the solver and its tolerances, the command, and the results.

## Licences

- **GreenLight**, BSD 3-Clause Clear: use and redistribution are allowed
  with its notice kept; it grants no patent rights. It is run as a
  reference, not shipped, and is not a dependency of the packages.
- **The 4TU dataset**, CC BY-SA 4.0: it is downloaded when the experiment
  runs, never committed. A derived dataset published would carry the same
  licence and its attribution.
- **The papers' equations and parameter values** are implemented from the
  publications and cited; no text or code is copied from them.

## Open

- Whether Vanthoor (2011) or Katzin (2021) publish crop outputs on inputs
  that are public, which a second check could reproduce: not checked here.
- The tolerance that counts as reproducing the original implementation.
- Whether Reduced-State TOMGRO's parameters can be read from an open
  source, or need the paper itself.
