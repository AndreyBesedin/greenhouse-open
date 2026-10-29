# Two published tomato models, and how each is reproduced

A memo for item 4 of the [research priorities](../roadmap/research-validation-priorities.md)
(decision [0057](../decisions/0057-a-published-model-is-reproduced-and-validated-before-the-crops-grow.md)).
Two published tomato models are to become crop models of the run, each
reproduced on its own first. This memo weighs what each needs: equations,
parameters with their sources, drivers, a reference implementation to
compare with, data, and licences. It sets out each reproduction's recipe.
Decision [0060](../decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md)
proposes the plan, and decision
[0062](../decisions/0062-a-canopy-crop-model-grows-a-rows-area-not-its-plants.md)
how a model grown by area becomes a crop model of the run.

Its sources were checked on 2026-10-28 and 2026-10-29: DOIs against
Crossref and DataCite, code against its repositories and releases, data
against their records. What could not be read is said to be so. Two
inventories hold the detail:
- [Vanthoor's model as GreenLight implements it](vanthoor-katzin-inventory.md);
- [Reduced-State TOMGRO as Oliveira et al. implement it](reduced-tomgro-inventory.md).

## Reduced-State TOMGRO

- **The model:** Jones, J. W., Kenig, A. and Vallejos, C. E. (1999),
  "Reduced state-variable tomato growth model", *Transactions of the ASAE*
  42(1), 255–265,
  [doi:10.13031/2013.13203](https://doi.org/10.13031/2013.13203).
  - It reduces TOMGRO (Jones et al. 1991, *Transactions of the ASAE*
    34(2), 663–672,
    [doi:10.13031/2013.31715](https://doi.org/10.13031/2013.31715)) to
    five states: main stem nodes, leaf area index, and the above-ground,
    fruit and mature fruit dry weights, per m².
  - Its full text is behind the publisher's subscription and was not read
    for this memo. Its equations and parameter table are therefore checked
    here only as others restate them.
- **No code by its authors was found.** A later implementation is public:
  Oliveira et al.'s, in Python, under MIT,
  [github.com/mnqoliveira/data-assimilation-tomato-models](https://github.com/mnqoliveira/data-assimilation-tomato-models),
  release v0.4.0
  ([doi:10.5281/zenodo.13294322](https://doi.org/10.5281/zenodo.13294322);
  v0.3.0 is
  [doi:10.5281/zenodo.10629918](https://doi.org/10.5281/zenodo.10629918)).
  - Its forms come from the 1999 and 1991 papers and from a spreadsheet
    Dr J. W. Jones provided. Where the spreadsheet and the paper differ, it
    follows the spreadsheet. The spreadsheet is not published, and is not
    known to be distributable.
  - It also implements Vanthoor's model, as another variant (below).
- **Its drivers, as that implementation takes them:**
  - The five states are updated once a day.
  - Photosynthesis, maintenance respiration and the node rate are worked
    out from each hour's air temperature and PPFD inside the greenhouse,
    and summed into the day's rates.
  - CO₂ is read once a day.
  - Its daily state update is therefore not the same as daily drivers.
- **Another formulation:** Fink et al. (2023), "Comparison of dynamic
  tomato growth models for optimal control in greenhouses", 2023 IEEE
  AGRETA, 28–33,
  [doi:10.1109/AGRETA57740.2023.10262422](https://doi.org/10.1109/AGRETA57740.2023.10262422),
  [arXiv:2308.06031](https://arxiv.org/abs/2308.06031).
  - It writes Reduced TOMGRO with daily drivers.
  - Run on the Autonomous Greenhouse Challenge's climate data, it reports
    the model overestimating biomass by about 2 kg m⁻².
  - No code is published. It is a different variant, and is not
    reproduced here.
- **Published results on its uses:**
  - Oliveira et al. (2024), "Uncertainty in greenhouse tomato growth
    models", *Computers and Electronics in Agriculture* 225, 109324,
    [doi:10.1016/j.compag.2024.109324](https://doi.org/10.1016/j.compag.2024.109324).
    Closed access; only its abstract was read. It compares the
    uncertainty and parameter sensitivity of Reduced TOMGRO, Vanthoor's
    model and SIMPLE.
  - Oliveira et al. (2025), "Leveraging data from plant monitoring into
    crop models", *Information Processing in Agriculture* 12(3), 408–429,
    [doi:10.1016/j.inpa.2025.02.003](https://doi.org/10.1016/j.inpa.2025.02.003).
    Open access, CC BY 4.0. It assimilates plant monitoring into Reduced
    TOMGRO, reporting each state's error against measurements by growing
    cycle.
  - They are results on measured data, not trajectories on public inputs.
    The processed drivers they ran on are not published.
- **Measured data:** Oliveira et al.'s "Tomato growth in production-like
  setting", version 5.5,
  [doi:10.25824/redu/EP4NGO](https://doi.org/10.25824/redu/EP4NGO),
  CC BY-NC 4.0.
  - Mini-tomatoes in greenhouses in Campinas, Brazil, in three cycles of
    about 100 days, from 2019 to 2021, at 1.33 and 2.22 plants per m².
  - The air's temperature and humidity every 5 minutes, and PAR every 15.
    CO₂ was not measured.
  - The fresh and dry mass of leaves, stems, green and mature fruit, three
    plants at a time, every one to three weeks.
  - Leaf area only as scans, about 14 GB of images.
  - A candidate for validation (milestone C), with its non-commercial
    licence assessed first.

## Vanthoor's model, as Katzin simplified it

- **The model:** Vanthoor, B. H. E., de Visser, P. H. B., Stanghellini, C.
  and van Henten, E. J. (2011), "A methodology for model-based greenhouse
  design: Part 2, description and validation of a tomato yield model",
  *Biosystems Engineering* 110(4), 378–395,
  [doi:10.1016/j.biosystemseng.2011.08.005](https://doi.org/10.1016/j.biosystemseng.2011.08.005).
  Its full description is chapter 9 of Vanthoor's thesis (Wageningen
  University, 2011, an open PDF at
  [edepot.wur.nl/170301](https://edepot.wur.nl/170301)).
- **The variant reproduced:** as Katzin (2021) simplified it (thesis,
  Wageningen University,
  [doi:10.18174/544434](https://doi.org/10.18174/544434); and Katzin et al.
  2020,
  [doi:10.1016/j.biosystemseng.2020.03.010](https://doi.org/10.1016/j.biosystemseng.2020.03.010)).
  - **States:** six ODE states, the carbohydrates in a buffer (`cBuf`), in
    the fruit (`cFruit`), leaves (`cLeaf`) and stems (`cStem`), the crop's
    temperature sum (`tCanSum`, an integral), and the last day's mean
    canopy temperature (`tCan24`, a first-order filter).
  - **Leaf area:** the leaf area index is derived from the leaves,
    `sla * cLeaf`, not a state.
  - **Fruit:** a single pool, without the thesis's development stages,
    harvested by a smooth rate past a most mass.
- **Its implementation:** GreenLight, by Katzin and collaborators, a
  later implementation of that simplified model, not Vanthoor's own code.
  - [github.com/davkat1/GreenLight](https://github.com/davkat1/GreenLight),
    BSD 3-Clause Clear; version 2.0.7 on PyPI, uploaded 2026-10-27, its
    files pinned by their hashes; commit `d6282a1`.
  - Three files run the crop alone:
    - the crop
      ([`crop_vanthoor_2011_chapter_9_simplified.json`](https://github.com/davkat1/GreenLight/blob/d6282a1e60734a21502993366816c0acb4397e48/greenlight/models/katzin_2021/definition/vanthoor_2011/crop_vanthoor_2011_chapter_9_simplified.json));
    - an extension that works out the PAR the canopy absorbs
      ([`extension_crop_vanthoor_2011_for_standalone.json`](https://github.com/davkat1/GreenLight/blob/d6282a1e60734a21502993366816c0acb4397e48/greenlight/models/katzin_2021/definition/vanthoor_2011/extension_crop_vanthoor_2011_for_standalone.json));
    - their composition
      ([`main_vanthoor_crop.json`](https://github.com/davkat1/GreenLight/blob/d6282a1e60734a21502993366816c0acb4397e48/greenlight/models/katzin_2021/definition/vanthoor_2011/main_vanthoor_crop.json)).
- **Its drivers:**
  - The canopy's temperature, the PAR above the canopy, and the CO₂,
    sub-daily, interpolated linearly by the solver.
  - The PAR above the canopy is incident. The extension turns it into the
    PAR the canopy absorbs, through its leaf area, its extinction and
    reflection and the floor's reflection, and photosynthesis uses that.
- **Its parameters:** from the thesis's tables 2.2, 8.1, 8.2, 9.1 and 9.2,
  from GreenLight 1's code (the relative growth rate, "assumed"; the
  initial states) and from Katzin (2021) (the fruit harvest). The
  inventory lists every value with its unit and source, and the
  departures the files note: leaf pruning's rate, the harvest, the gas
  constant's units, and an initial buffer that is not GreenLight 1's.
- **Its outputs:**
  - Hourly. Every crop quantity is a mass of carbohydrate, with no factor
    to dry or fresh matter given.
  - The harvest is a rate, whose integral is the harvested fruit.
- **Its solver:** scipy's BDF, at most an hour a step, `atol` 1e-3 and
  `rtol` 1e-6.
- **Its example's drivers** are not in the repository.
  - They are made from an EnergyPlus weather file: the canopy at the
    outdoor air's temperature, PAR as 2.3 times the outdoor global
    radiation, and CO₂ constant.
  - GreenLight itself calls them artificial.
- **Oliveira et al.'s Vanthoor implementation** is another variant, with
  fruit development stages, its own switches, pruning and harvest. It is
  not this one's reference.
- **Data:** Katzin et al.'s GreenLight data on 4TU,
  [doi:10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2](https://doi.org/10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2),
  CC BY-SA 4.0, from a trial in Bleiswijk from October 2009 to February
  2010.
  - **Measured, every 5 minutes:**
    - the outdoor global radiation, temperature, humidity and wind;
    - the indoor air's temperature, humidity and CO₂;
    - the screens, vents, pipes and lamps' states.
  - **Not measured:** the canopy's temperature, and the PAR above the
    canopy as a series. The lamps are known only as on or off, with one
    stated PPFD.
  - **Not stated:** the time zone, though daylight saving ended within the
    trial.
  - **Simulated:** the file GreenLight's test data are made from
    (`climateModel_hps_manuscriptParams.csv`) is GreenLight's simulation
    output, carrying its driving inputs. Some of those were assumed or
    modelled: the outdoor CO₂, the sky's and the soil's temperatures.
  - **No crop measurements.** It cannot validate a crop model.

## Compared

| | Reduced-State TOMGRO | Vanthoor, as Katzin simplified it |
| --- | --- | --- |
| Equations | The 1999 paper (subscription, not read); restated openly; Jones's spreadsheet (not public) | The thesis (open) and the 2011 paper |
| Parameters, with sources | The paper's table; the reference's sets | The thesis's tables and GreenLight 1, per parameter |
| States | 5, updated daily | 6, continuous |
| Drivers | Hourly temperature and PPFD, CO₂ daily (Oliveira's); daily (Fink's) | Sub-daily canopy temperature, incident PAR, CO₂ |
| Reference implementation | Oliveira et al. v0.4.0, MIT, a later one | GreenLight 2.0.7, BSD 3-Clause Clear, by the simplifier's group |
| Measured crop data, open | Oliveira et al.'s, CC BY-NC 4.0 | None found; the trial's climate only, CC BY-SA 4.0 |
| Question it answers | A canopy's growth and yield, compactly and fast | How the day's climate drives growth and yield |

## What the simulator gives a crop model today

A crop model is a rung of the run's crop part (`biology/crop_contract.py`),
built for single plants. The run lives each plant a day at a time and
gives it its day (`LocalEnvironment`): the day's mean air temperature,
the PAR its crown received that day, the CO₂ and its water status.

- **Not either model's input:** neither model's reference takes a day's
  mean temperature and PAR integral. Reduced TOMGRO as Oliveira et al. run
  it needs the day's hours, and Vanthoor's model their course.
- **Any aggregation is an approximation:** a documented one, with a test
  of what it changes.
- **Air for canopy:** the house has no canopy temperature. Its air's
  temperature stands for it, as it does in both references' example runs.
  That is recorded as a difference.
- **CO₂:** the house's follows the outside's through its vents; no crop
  takes it up, and nothing enriches it.
- **A canopy is not a plant:** both models grow a canopy per m², with no
  plants, organs or geometry. Decision 0062 makes that a crop model of its
  own kind, with the day's hours among what the run gives it.

## The plan

Both models, each in three milestones (decision 0060):

- **(A) Reproduced on its own,** outside the packages, compared with its
  reference on the same inputs.
- **(B) A crop model of the run,** chosen by the manifest (decision 0062).
- **(C) Validated on measured crop data.**

The order is practical; neither waits on the other's outcome.
Reduced-State TOMGRO's reproduction is the smaller, and comes first.

## The reproductions

Each is implemented from the documented equations: the publications', and
those the reference code documents. Neither is ported from its reference's
source. Each fixes the following before its first comparison, in a
manifest that the comparison reads:

| | Reduced-State TOMGRO | Vanthoor, as Katzin simplified it |
| --- | --- | --- |
| Variant | Oliveira et al.'s, the spreadsheet's forms | Katzin (2021)'s simplified, GreenLight's |
| Reference | v0.4.0, commit `b9b2c80`, its Zenodo md5 | `greenlight==2.0.7`, its wheel's sha256; commit `d6282a1` cited |
| Parameters | The `gnvman` set, each value with its unit and source | GreenLight's, each with its unit and source |
| Initial state | The reference run's: n 4, LAI 0.014, W 0.09, Wf 0, Wm 0 | GreenLight's six initial values |
| Drivers | Hourly air temperature, PPFD and CO₂, 24 a day | The same series, as canopy temperature, PAR above the canopy and CO₂ |
| Step and solver | Daily Euler, hourly sums | BDF, `max_step` 3600 s, `atol` 1e-3, `rtol` 1e-6, matched by ours |
| Compared | The five states, day by day | The six states, hourly; the leaf area index derived; the harvested fruit integrated from its rate, alike in both |

**The drivers:** a series both use, fixed and checksummed, with its
units, time zone and step stated.
- First, a synthetic diurnal series written for the reproduction:
  - a day's course of temperature, light and CO₂ repeated over a season,
    so that nothing in it is borrowed or licensed;
  - its PPFD given to Reduced TOMGRO as the light inside, and to
    Vanthoor's model as the PAR above the canopy, the same numbers.
- Then a series from measured data:
  - the 4TU trial's indoor air and CO₂, with its PAR derived and said to
    be so;
  - or Oliveira et al.'s, its licence permitting.
- Every transformation is applied alike to both implementations.

**The tolerances**, stated before the first run (to be confirmed in
decision 0060's review):
- **Reduced TOMGRO:** the same daily Euler arithmetic, so each state
  within 1e-9 relative and 1e-12 of its unit absolute.
- **Vanthoor's model:** two ODE solvers' answers, so each carbohydrate
  state and the harvested fruit within 1e-4 relative or 1 mg CH₂O m⁻²
  absolute, whichever is larger; `tCanSum` and `tCan24` within 1e-3 of
  their units; and the leaf area index within 1e-5.

**What is reported:**
- every difference beyond its tolerance, with its cause or as unexplained;
- the run times;
- what the comparison does not show.

An equation is never changed to force agreement. Agreement shows that the
implementation matches its reference. It does not show that the model is
right for a greenhouse: that is milestone C, on measured data,
comparing like with like. Dry matter is compared with dry matter, not with
fresh market yield; harvested with harvested, not with fruit standing; and
per m² with per m², not with per plant, unless a stated conversion stands
between them.

## Licences

| What | Licence | How it is used |
| --- | --- | --- |
| GreenLight | BSD 3-Clause Clear (no patent grant) | Run apart, as a reference, at its pinned release; not shipped |
| Oliveira et al.'s code | MIT on its repository; its Zenodo record says CC BY 4.0 | Run apart, as a reference, at its pinned release; not shipped |
| The 4TU GreenLight data | CC BY-SA 4.0 | Downloaded when used; anything derived and published keeps its licence and attribution |
| Oliveira et al.'s measured data | CC BY-NC 4.0 | Downloaded when used; its non-commercial term assessed before anything derived from it is published |
| The papers and theses | Their publishers' terms | Equations and values implemented from them and cited; no text or code copied |

Nothing is redistributed or committed that a licence does not allow. The
implementations are written from the documented equations; neither
reference's source is transplanted.

## Not represented by either model

- organs, single plants and their geometry;
- crop work and robots' tasks;
- the crop's effect on the house's air: transpiration and CO₂ uptake;
- water and nutrients;
- pests and diseases;
- fruit quality.

## Open

- The 1999 paper's own forms, where they differ from the spreadsheet
  variant: they need its full text.
- The tolerances above, until decision 0060's review confirms them.
- Whether Oliveira et al. (2024) or Katzin (2021) publish crop outputs on
  inputs that are public, which a second comparison could reproduce.
- The measured data for milestone C: Oliveira et al.'s (non-commercial)
  or AGC4's, and the conversions each needs.
