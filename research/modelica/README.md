# OpenModelica, for the Modelica comparison

Item 6 of the [research priorities](../../docs/roadmap/research-validation-priorities.md)
compares the simulator with a Modelica model: one documented, measured
interval of TiGwerLib reproduced in OpenModelica, then compared on matched
inputs. This folder sets OpenModelica up for it, apart from the
repository's own environment, checks the setup on TiGwerLib's global
model, and reproduces the indoor climate of the paper that model was
published with ([below](#reproducing-sourisseau-et-al-2026)).

## What it runs on

| What | Version | Pinned by |
| --- | --- | --- |
| OpenModelica | 1.25.0, its `minimal` image, for arm64 and amd64 | the image index's digest, `sha256:c85938d4dd4cdc15ea2d2af899920907e707ef94243e13603bd347679e5e6a14` |
| TiGwerLib | 0.7.0, MIT, [doi:10.5281/zenodo.15590404](https://doi.org/10.5281/zenodo.15590404) | its archive's sha256, `9ed2c0b2ad6c0ba0d68b49bd0c597fb5a2fb3a61c8a4c0e9c1e8ea9aa9a1b1cb`, and the md5 Zenodo published, `019f1aa5f5735fc42bc348246e3d6a20` |
| Sourisseau et al. (2026)'s dataset | its measurements and its global model's outputs, CC BY 4.0, [doi:10.5281/zenodo.17554203](https://doi.org/10.5281/zenodo.17554203) | its archive's sha256, `5462cecc6874262f18136971a8ec7c6db33374c8ff2cadb8f9309a61ece8e480`, and the md5 Zenodo published, `d0e4486fa1041fac5e6e47673b6c95d3` |
| The Modelica Standard Library | 4.0.0, as OpenModelica's `4.0.0+maint.om`, with ModelicaServices and Complex | its commit, `bbdadca3e90d73e42b9c86e184e8a5fb2a8120a8` |
| The Buildings library | 9.1.0 | its commit, `d34a259960ca12b2126ef188f2d20fc8148eafb2` |

They are the versions TiGwerLib's record says it was tested with:
OpenModelica 1.25.0, the Modelica Standard Library 4.0.0, and the
Buildings library 9.1.0 or 12.0.0. Its `uses` names 9.1.0. The libraries
come from OpenModelica's package index, which records beside each library
the commit it was installed from. The setup refuses a library installed
from another commit.

OpenModelica runs in its container because its official builds for macOS
stopped after 1.16. Its macOS build today is experimental, built from the
development version
([its download page](https://openmodelica.org/download/download-mac/)).
The image is the release itself, and runs natively on Apple silicon.

Nothing here is committed but the code: the image, TiGwerLib and the
libraries are fetched into a folder of their own (decision
[0063](../../docs/decisions/0063-a-data-file-is-generated-committed-or-fetched-by-one-rule.md),
rule 1). Nothing is published from here either: each comes from where its
authors publish it, pinned by its content.

## Setting it up

Docker must be running: Docker Desktop on macOS or Windows, Docker Engine
on Linux. The commands need Python's standard library and the simulator's
module for containers, `greenhouse_sim.containers`: in the repository's
environment, or with `PYTHONPATH=greenhouse_sim`. From the repository's
root:

```bash
python -m research.modelica.openmodelica setup ~/.greenhouse-open/modelica
python -m research.modelica.openmodelica check ~/.greenhouse-open/modelica /tmp/modelica-check
```

`setup` pulls the image, fetches TiGwerLib into `tigwerlib/`, installs
the libraries into `home/`, and fetches the paper's dataset (126 MB)
beside them. It can run again: what is there and pinned is kept. `check` builds TiGwerLib's global model,
`TiGwerLib.Applications.CTIFLGreenhouse.GlobalModels.UsingStatuses.CTIFLGreenhouseBaseModel`,
over the first day of its experiment. It simulates the day with DASSL,
OpenModelica's default solver, at the experiment's tolerance (1e-5) and
interval (300 s), with results at its intervals alone, not at its events
too. It prints what each step took, and leaves the build, the results and
both logs in its working folder. It first removes what an
earlier check left there, and stops at a step that fails.

Any other command runs in the same container:

```bash
python -m research.modelica.openmodelica run ~/.greenhouse-open/modelica WORKDIR -- omc script.mos
```

The command runs in `WORKDIR`. The libraries are on its `MODELICAPATH`,
and TiGwerLib is read-only at `/tigwerlib`. A model
reads its data from the paths it was built with, so it is built and run
with TiGwerLib at that same place.

The container runs as `greenhouse_sim.containers` runs every container,
OpenFOAM's for the airflow too: on Linux as the user who runs it, so that
what it writes is theirs, and under Docker Desktop, whose mounts carry no
owners, as the image's own user. It has run on Linux, and on macOS as the
user who ran it. As the image's user, as it now runs on macOS and on
Windows, it has not been tried yet.

## Checking the pins

The pins are not ours: an image, an archive or a library's commit can go
away, and the package index can move a version to another commit, as a
maintenance branch does. `verify` checks, without Docker, that each is
still published as pinned:

```bash
python -m research.modelica.openmodelica verify
```

It asks Docker Hub for the image's digest, which pulls nothing. It asks
Zenodo whether each archive's record still lists it with the md5 Zenodo
published: a record's files do not change, a new version is a new record,
so it downloads neither. It reads OpenModelica's package index (0.5 MB)
for each library's commit, and asks GitHub for that commit's archive. It
takes a few seconds, with Python's standard library alone.

The [Modelica workflow](../../.github/workflows/modelica.yml) runs it each
week, and when this folder changes. Building and simulating is left to
`check`, run by hand: the pins cannot change what they hold, so it needs
running again only when the setup here changes.

## What it takes

Measured on an Apple M2 with 8 GB of memory, with Docker Desktop 4.92 and
its default virtual machine of 4 GB and 8 CPUs. The check ran twice:
first with 28 % of the Mac's memory free, then with 12 to 19 % free and
9 GB of swap in use, other applications open both times.

| Step | Time | Time, short of memory | Peak memory | Disk |
| --- | --- | --- | --- | --- |
| The image, pulled | 13 s | | | 1.1 GB |
| TiGwerLib and the libraries, fetched and installed | 20 s | | | 15 MB archived, 64 MB unpacked (57 MB of data); 240 MB of libraries |
| The global model, built | 43 s | 421 s | 2.6 GiB | 180 MB |
| One day, simulated with DASSL | 11 s | 31 s | 0.7 GiB | 62 MB of results |

On GitHub's Linux runners (4 CPUs, 16 GB), over two runs, the build took
24 to 27 s with a peak of 2.5 GiB, and the day 15 to 20 s with a peak of
0.5 GiB.

The peak is the container's, from its control group, the page cache
included. The build is the heavy step: it needs about 3 GB in Docker's
virtual machine, and it slows tenfold when the Mac has to swap that
machine's memory out. On 8 GB, it runs best with other large
applications closed, and Docker Desktop quit after it.

A longer run is light in memory but heavy on disk. At 62 MB a day, every
variable at each interval and each event as these runs wrote them, the
experiment's 334 days would write about 20 GB of results, so a longer run
keeps only the variables it compares (`variableFilter`). At the first
day's pace, that season would take about an hour.

## What the check found

These are first observations for item 6, not results:

- **Dymola's libraries:** TiGwerLib's `uses` also names DymolaCommands
  1.10 and DataFiles 1.1.0, which OpenModelica does not have. It skips
  them, and nothing in TiGwerLib refers to either.
- **The build** passes with warnings:
  - a conditional connector, `CO2Port_a`, used outside a `connect` in six
    places;
  - alias variables whose start or nominal values conflict;
  - initial conditions that are not fully specified.
- **DASSL** simulates the first day, through 287 state events. Some
  assertions on cumulative totals fire, at the information level, when
  the totals dip just below zero (−6e-6 and smaller).
- **CVODE,** the solver the experiment names for Dymola, stops 0.51 s
  into the day: `##CVODE## -8 error occurred at time = 29030400.5146821`.
  `check --solver cvode` runs the day with it.

## Reproducing Sourisseau et al. (2026)

TiGwerLib's global model was published with
[Sourisseau et al. (2026)](https://doi.org/10.1371/journal.pone.0340619),
which ran it with Dymola and DASSL over a season of a Venlo tomato
greenhouse at CTIFL, Carquefou, from the 3rd of December, 2014. Its
dataset holds, every 5 minutes of that season, the model's indoor
temperature and relative humidity beside the measurements. The model
reads the season's weather and the equipment's recorded states (vents,
screens, heating) from TiGwerLib's own data; its control loops are not
modelled.

The reproduction runs the same model, unchanged, in OpenModelica, from the
season's start to the end of one of the paper's figures' windows, and
compares its indoor climate with the paper's at every moment of the
window:

| Window | The paper's | Days | Simulated from the season's start |
| --- | --- | --- | --- |
| `fig8` | Fig 8, winter | 9 to 19 January 2015 | 47 days |
| `fig9` | Fig 9, summer | 15 to 25 July 2015 | 235 days |

```bash
python -m research.modelica.sourisseau_2026 ~/.greenhouse-open/modelica /tmp/fig8 fig8
```

What is compared, where and within which tolerances is stated in
[`sourisseau_2026.json`](sourisseau_2026.json), committed before any run:
the indoor air's temperature within 0.16 K and its relative humidity
within 1 %RH of the paper's, at every 5-minute moment of the window. They
are a tenth of what the paper holds its model to against the
measurements, a day's RMSE of 1.6 K and of 10 %RH: a difference within
them moves a day's RMSE against the measurements by no more than they
are. The report, in `results/<window>.json`, also gives each day's RMSE
against the measurements, ours beside the paper's, and the paper's own
from its Fig 10 data.

The dataset is CC BY 4.0, and is fetched, not committed. A report holds
the comparison's numbers alone, none of its series.

### What it found

Each window ran once, at the commit that states it, on an Apple M2 with
8 GB and Docker Desktop's 4 GB virtual machine:
[`results/fig8.json`](results/fig8.json) and
[`results/fig9.json`](results/fig9.json), committed as written.

| Window | Moments compared | Beyond tolerance | Largest difference, T and RH | RMSE of the difference, T and RH | Within, as stated |
| --- | --- | --- | --- | --- | --- |
| `fig8` | 3,169 of 3,169 | 0 | 0.0024 K, 0.018 %RH | 0.0003 K, 0.003 %RH | yes |
| `fig9` | 3,168 of 3,169 | 0 | 0.0037 K, 0.015 %RH | 0.0003 K, 0.003 %RH | no: a moment is missing |

- **The paper's indoor climate is reproduced in OpenModelica,** without
  Dymola, at every moment compared in both windows, to a fiftieth of the
  tolerances or less. The dataset gives its values to 0.0001 K and
  0.01 %RH, a part of what is left.
- **July misses a moment, so it is not within as stated.** OpenModelica
  wrote the result for the 22nd of July, 2015 at 13:05 at 13:00:20.05
  instead, and no row at 13:05. Its output holds six such rows over the
  season, at 13:00:20 every two or four weeks from the 15th of April, each
  in place of the 13:05 row; January's window holds none. It is the
  output's grid, not the model's values: the rule stated before the run
  counts a missing moment, and stands.
- **Each day's RMSE against the measurements** is the paper's, from its
  own series, to 0.0006 K and 0.0001 (0.01 %RH): from 0.25 to 1.15 K in
  January and from 0.54 to 2.20 K in July. The paper's own daily values,
  in its Fig 10 data, differ from those its series gives by −1.1 % to
  +3.7 %: they are computed otherwise than from the 5-minute series, in a
  way the paper does not state.
- **What it took:** in January, a build of 64 s at a peak of 3.0 GB and
  47 days simulated in 8 minutes at 0.7 GB; in July, a build of 126 s at
  2.8 GB and 235 days in 44 minutes at 1.0 GB, other applications open.
