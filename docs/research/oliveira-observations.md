# What Oliveira et al.'s tomato observations give a validation, and on what terms

**Status:** Memo, 2026-11-11, checked against the record's metadata, its
data paper and its licence's legal code. An assessment for item 5 of the
[research priorities](../roadmap/research-validation-priorities.md), which
asks for Oliveira et al.'s greenhouse tomato observations to be assessed
as [the AGC4 memo](agc4-coverage.md) inventories AGC4, their licence
included. It reads none of the data. Decision
[0060](../decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md)
has the licence's non-commercial term assessed before anything derived from
the data is published, and a profile of the files would be derived from
them, so this memo leaves the files unread. It decides nothing: whether to
validate on these data is a decision of its own (decision
[0076](../decisions/0076-the-tomato-models-are-calibrated-on-agc4s-pre-trial-and-tested-once-on-its-challenge.md)).
It is not legal advice.

## Sources, and how they were checked

- **The record:** "Tomato growth in production-like setting", by M. P. G.
  de Oliveira, R. P. Amaro, H. B. Pescarini and L. H. A. Rodrigues, on
  REDU, Unicamp's research data repository, version 5.5, released
  2025-03-24, first published 2021-12-09,
  [doi:10.25824/redu/EP4NGO](https://doi.org/10.25824/redu/EP4NGO). It was
  read through the repository's Dataverse API
  (`/api/datasets/:persistentId/?persistentId=doi:10.25824/redu/EP4NGO`):
  its licence, terms, description, dates and file list. Its three tabular
  files were read through their DDI metadata
  (`/api/access/datafile/<id>/metadata/ddi`): rows, columns and column
  names, no values.
- **The data paper** the record cites: Oliveira, Amaro, Pescarini and
  Rodrigues (2024), "Tomato plants' growth observations obtained from
  multiple sources in a production-like setting", SciELO Preprints,
  version 2 of 2024-05-20,
  [doi:10.1590/SciELOPreprints.7667](https://doi.org/10.1590/SciELOPreprints.7667),
  CC BY 4.0. It is a preprint, not peer-reviewed, and no journal version
  was found. Below it is "the paper", cited by section or table.
- **The authors' code**,
  [data-assimilation-tomato-models](https://github.com/mnqoliveira/data-assimilation-tomato-models),
  MIT, the reference of the
  [Reduced-State TOMGRO reproduction](reduced-tomgro-inventory.md). At
  v0.4.0 its `data/` folder holds a text file and two plot themes, no
  observation; its README sends readers to the record for the data. Its
  Zenodo records, [10.5281/zenodo.7632419](https://doi.org/10.5281/zenodo.7632419)
  among them, are software, not data.
- **The licence:** CC BY-NC 4.0's
  [legal code](https://creativecommons.org/licenses/by-nc/4.0/legalcode),
  cited by section.

## The record

- **Licence:** CC BY-NC 4.0, the record's licence. The record adds no
  terms of use or of access, and none of its 17 files is restricted.
- **Size:** 16.6 GB. Leaf scans are 14.0 GB in six archives, plant photos
  2.5 GB, and the photos' annotated masks 22 MB. Everything else is 38 MB:
  - the three destructive workbooks;
  - the climate, from two sets of sensors;
  - the load cells' weights;
  - substrate moisture;
  - the authors' processing scripts.
- **The destructive workbooks:**
  - Their original format is `.xlsx`, one per cycle, with "different
    variables ... in different tabs" (the paper, Table 5).
  - The repository's tabular view of each holds one sheet: 999, 24 and 36
    rows of 13, 14 and 16 columns. Its columns are the date, the days after
    transplanting, the week and the replicates; the masses are in the
    originals.
- **The archives** are stored with a `.zipfile` extension, to be renamed
  `.zip` (the paper, §2).

## What it holds

Mini-tomatoes, grown in Campinas, Brazil (22°49′ S, 635 m), in plastic
greenhouses, in three cycles of about 100 days. A fourth, pilot cycle,
cycle 0, is described in the paper but is not in the record. From the
paper (Table 1, §3, §4):

| Cycle | Cultivar | Grown | Greenhouse | Plants per m² | The paper notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Fercam Milla | 12 Jul to 28 Oct 2019 | 6.4 × 10.98 m, pad-and-fan cooling on a schedule | 1.33 | water deficit throughout |
| 2 | Feltrin Carolina | 5 Nov 2020 to 12 Feb 2021 | the same | 1.33 | excess nitrogen, then rust mite |
| 3 | Seminis DRC 564 | 16 Mar to 11 Jun 2021 | 6.4 × 18 m, insect-screen walls | 2.22 | closest to full irrigation and fertilization |

The record's collection dates differ from the paper's by up to six days
(cycle 3 from 10 March).

- **The crop:**
  - The plants were transplanted about 30 days after seeding into 8 L pots
    of coconut fibre and fertigated by drip.
  - Each was grown on one stem, side shoots were removed one to three times
    a week, and growth was stopped at the top wire.
  - Leaves were pruned "only when their senescence was dominant".
  - Fruit was harvested "when the whole truss was mature" (§4).
- **Destructive samples:**
  - Every one to three weeks, three plants that were not monitored.
  - The fresh and dry mass of the leaves, the stem, the green fruit and the
    mature fruit, weighed apart. Nodes were counted in cycles 2 and 3, and
    height measured in cycle 3.
  - Guard plants were "not always" kept (§2.2).
- **Leaf area:**
  - Recorded only as scans of the leaves, each with a reference of known
    size (Table 4).
  - A leaf area index needs the scans measured: the authors' scripts do
    it, and the record has no leaf area as a number.
- **Climate, inside the greenhouse only** (Table 2):
  - Air temperature and humidity every 5 minutes, from SHT75 transducers
    in aspirated, shielded tubes, two per node and two nodes.
  - The same from low-cost DHT22 sensors, every 5 minutes.
  - PAR from a LI-190SA quantum sensor per node, every 15 minutes.
  - Light from a BH1750, every 5 minutes.
  - Neither the record nor the paper gives a CO₂ measurement, outside
    weather or heating.
- **Monitoring:**
  - Two plants per cycle on load cells, weighed each minute.
  - Photos of them every other day, from above and from the side.
  - 618 photos annotated by hand into leaves, green fruit and mature fruit.
  - Substrate moisture every 10 minutes.

## What it would hold the models to

In some ways this fits a crop model better than AGC4. It has dry mass by
organ at every sample, green and mature fruit weighed apart, and nodes.
Oliveira et al. built their Reduced-State TOMGRO for it. In others it
fits worse:

- **No CO₂.** Both models read CO₂: Reduced-State TOMGRO daily, Vanthoor's
  model through the `house_hours` profile. A run would assume it, the
  outside air's for example, and the assumption would be reported beside
  every result. AGC4 measured it.
- **The fruit harvested before a sample.** Fruit was picked truss by truss
  as it matured. The paper does not say whether a sampled plant's mature
  fruit includes its trusses picked earlier. Vanthoor's model counts its
  harvested fruit, and Reduced-State TOMGRO's mature fruit is never
  picked, so this must be settled from the workbooks before anything is
  compared. AGC4 picked nothing before it weighed a plant.
- **Three plants a sample, and few samples.** Cycles 2 and 3 have 24 and
  36 rows in their first sheet, which suggests 8 and 12 dates of three
  plants. The workbooks would confirm it. A standard error over three
  plants is wide.
- **Leaf area from images.** Comparing a leaf area index means measuring
  the scans first: one more processing step, with its own error, before
  any comparison.
- **A different cultivar, and a different stress, in each cycle.** A split
  by cycle tests a calibration across cultivars, years and seasons at
  once, and the paper names water and nitrogen stress, which neither
  model represents, in cycles 1 and 2.
- **Per plant, at two densities:** 1.33 and 2.22 plants per m², converted
  as decision 0076 converts AGC4's.

## The licence

CC BY-NC 4.0 grants its licensee ("You", the person or entity exercising
the rights, §1(l)) a licence to reproduce and share the data, and to
produce and share adapted material, "for NonCommercial purposes only"
(§2(a)(1)). "NonCommercial means not primarily intended for or directed
towards commercial advantage or monetary compensation" (§1(i)).

- **What it covers:** "Copyright and Similar Rights", database rights
  included (§1(c)). Adapted material is material subject to those rights
  that is derived from the data "in a manner requiring permission" (§1(a)).
  Where database rights apply, extracting, reusing or sharing all or a
  substantial portion of the database's contents is for non-commercial
  purposes only (§4(a)).
- **What it does not restrict:** it "does not ... impose conditions on any
  use of the Licensed Material that could lawfully be made without
  permission" (§8(a)). Whether a number computed from the data, a metric
  or a calibrated parameter, needs permission at all is a question of law,
  and the licence leaves it there.
- **Its conditions:** attribution, a link to the licence, and a note of any
  change, when the data or adapted material are shared (§3(a)). The
  licensor reserves royalties for any use that is not non-commercial
  (§2(b)(3)).

A non-commercial term binds whoever uses the data and why, not a
repository. Two facts frame it here:

1. The repository's code is Apache 2.0. Anyone may use anything in the
   repository commercially, unless a file says otherwise.
2. The repository's rule for data: no data is included, the adapters
   download it from its publisher, and it stays under the publisher's
   licence ([the adapters' README](../../greenhouse_adapters/README.md)).

Case by case:

| Use | Under CC BY-NC 4.0 | As the repository would do it |
| --- | --- | --- |
| An adapter that downloads and reads the files | The code is not the licensed material | Apache 2.0, like the others. Its manifest records the licence, and `inventory` prints it |
| Downloading and reading the files | Reproduction: non-commercial only | For whoever runs it to judge their purpose, as for any dataset; the repository cannot decide it for them |
| Committing the files, or a substantial part of their values | Sharing: non-commercial only, with attribution | Not done, as for AGC4 |
| A profile: rows, spans, gaps, counts | Facts about the files, likely outside the licence (§8(a)), but derived | Committed only if marked as derived from CC BY-NC 4.0 data |
| A model's metrics against the data, or a parameter set calibrated on it | Numbers computed from the values; whether they need permission is unsettled | Kept in `research/`, marked, and never in a package, a run's default, or a parameter set shipped as an asset (P20) |

## What this suggests

- **The data are usable for non-commercial research**, under the rule that
  serves AGC4:
  - downloaded when used, and nothing of their values committed;
  - attribution to the record and to the paper;
  - the licence named wherever the data are read.
- **Anything derived that is committed is marked and kept apart.** This
  covers a profile, a test report and a calibrated set. It would sit
  under `research/validation/`, with a notice that names the record and
  the licence and says that the derived numbers are not offered on the
  repository's Apache 2.0 terms. It stays out of the packages and their
  defaults, so that nothing a commercial user takes from the repository
  carries the term.
- **The clearest path is the authors' permission.** A Creative Commons
  licence is non-exclusive: the licensor can grant more, in writing,
  outside it. The record names a contact. Permission to publish derived
  numbers, profiles, metrics and calibrated sets on the repository's terms
  would remove the marking and the question of §8(a). That request is
  the maintainers' to make, before any validation on these data is
  committed.
- **Compared with AGC4**, this dataset adds three things AGC4 lacks: dry
  mass by organ through each cycle, green and mature fruit weighed apart,
  and nodes. It lacks CO₂ and a leaf area as a number. It picks fruit
  before sampling, and its licence restricts commercial use. AGC4's
  dataset is CC BY 4.0.

## Open

- Whether a sampled plant's mature fruit includes its trusses picked
  earlier: in the workbooks.
- The samples per cycle and their dates: in the workbooks.
- Whether to ask the authors for permission, and on what terms.
- Whether to validate on these data at all: a decision of its own, after
  this, which would fix its split, its CO₂ assumption and its conversions
  before any run, as decision 0076 did for AGC4.
