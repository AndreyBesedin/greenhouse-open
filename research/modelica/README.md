# OpenModelica, for the Modelica comparison

Item 6 of the [research priorities](../../docs/roadmap/research-validation-priorities.md)
compares the simulator with a Modelica model: one documented, measured
interval of TiGwerLib reproduced in OpenModelica, then compared on matched
inputs. This folder sets OpenModelica up for it, apart from the
repository's own environment, checks the setup on TiGwerLib's global
model, reproduces the indoor climate of the paper that model was
published with ([below](#reproducing-sourisseau-et-al-2026)), and compares
the simulator's with it ([further below](#comparing-the-simulator-with-tigwerlib)).

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

## Comparing the simulator with TiGwerLib

The simulator's indoor air temperature is compared with TiGwerLib's, as
OpenModelica reproduces it above, on matched inputs, over the same two
windows:

```bash
python -m research.modelica.simulator_comparison ~/.greenhouse-open/modelica /tmp/fig8 fig8
```

It runs TiGwerLib to the window's end, as the reproduction does, then the
simulator's whole house through the window, and compares the two at every
5-minute moment. The simulator's side is built from TiGwerLib's own
records of the greenhouse, its `WeatherData.txt` and `MainData.txt`
(MIT), read from the folder `setup` made:

- **the house:** TiGwerLib's geometry, 43.2 by 24 m, 6.97 m to the
  gutters and 7.78 m to the ridges, its length at 331°, on six spans whose
  slope is its roof's, 22°; and its roof windows, 4.05 by 1.4 m, opening
  to 44°, 23 on each side of the roof, as many as its two sides have on
  average;
- **the weather:** TiGwerLib's records every 5 minutes, as a recorded
  weather, at Carquefou, on the dataset's clock (UTC+1);
- **the windows:** at each 5-minute step, those on the side of the roof
  facing the wind open as TiGwerLib's windward record, the others as its
  leeward;
- **the heating:** a heater giving, through each step, the heat
  TiGwerLib's pipes give the greenhouse: the energy each network took,
  filtered and limited as the model does, worked out exactly;
- **the start:** TiGwerLib's air at the window's start.

Each of the simulator's own parameters is its default. What is compared,
what cannot be, and the bar a day is held to are stated in
[`simulator_comparison.json`](simulator_comparison.json), committed before
any run: the temperature alone, a day within the bar when the RMSE of the
difference over it is at most 1.6 K, the bar the paper holds its own model
to against the measurements. The relative humidity is not compared: the
simulator's air takes no water from a crop. Five processes TiGwerLib has
are recorded as blockers, not worked around: its screens, its crop's
exchanges with the air, the heat its floor, soil, structure and crop
store, its roof's radiation to the sky, and walls that face corridors
rather than the outside. The report, in `results/simulator_<window>.json`,
holds the comparison's numbers alone, none of either model's series or of
the data's.

### What it found

Each window ran once, from the commit that states it, on a Linux machine
with 32 CPUs and Docker Engine:
[`results/simulator_fig8.json`](results/simulator_fig8.json) and
[`results/simulator_fig9.json`](results/simulator_fig9.json), committed as
written.

| Window | Moments compared | Days within 1.6 K | Mean difference | RMSE of the difference | Sun up: mean, RMSE | Sun down: mean, RMSE | Largest difference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fig8` | 3,169 of 3,169 | 0 of 11 | −4.24 K | 5.20 K | −1.74 K, 3.17 K | −5.69 K, 6.08 K | −11.1 K, 18 January 19:45 |
| `fig9` | 3,168 of 3,169 | 0 of 11 | +2.29 K | 3.57 K | +3.67 K, 4.44 K | −0.16 K, 0.66 K | +12.2 K, 25 July 12:00 |

The difference is the simulator's temperature less TiGwerLib's.

- **The simulator does not agree with TiGwerLib on any day,** by the bar
  stated: a day's RMSE of the difference runs from 3.0 to 7.7 K in
  January and from 2.1 to 5.1 K in July. Against the measurements, a
  day's RMSE is 3.0 to 7.7 K for the simulator in January and 2.3 to
  6.3 K in July, where TiGwerLib's is 0.25 to 1.15 K and 0.54 to 2.20 K.
- **The inputs were matched as stated.** The heat each model was given
  over a window is the same to a part in 10¹²: 36.3 GJ in January and
  31.1 GJ in July. Each step's heat, worked out here, lies within 252 W
  in January and 100 W in July of the mean of TiGwerLib's own at the
  step's two ends, the pipes giving 38 and 33 kW on average. July's
  comparison misses the moment OpenModelica wrote off its grid, 22 July at
  13:05, as the reproduction does, and so do the heat's checks of the two
  steps on either side of it.
- **Where they differ, the blockers stated would push the simulator that
  way, but this comparison cannot tell them apart.** In January the
  simulator is coldest at night, 5.7 K below on average: it has no
  thermal screen to draw, stores no heat but in its air, and loses heat
  through four walls of glass, 937 m² of its 1,974 m², where TiGwerLib
  loses it to the outside through its south wall alone, 177 m², and its
  roof. In July it is warmer by day, 3.7 K on average and up to 12 K at
  noon: it has no shading screen and no transpiring crop. July's nights,
  with the vents open and no heat to give, are the closest: 0.16 K
  colder on average, an RMSE of 0.66 K. Which blocker accounts for how
  much is not measured: no run here adds or removes one.
- **The house's air** is 7,225 m³ on the simulator's grid, 5.5 % less than
  TiGwerLib's 7,646 m³.
- **What it took:** TiGwerLib, in January 17 s to build and 12 minutes for
  its 47 days, in July 15 s and 59 minutes for its 235 days; the
  simulator, 7 minutes for each window's 11 days.

## Apportioning the gap among the blockers

How much of that gap each blocker accounts for is measured by taking it
out of TiGwerLib, in the comparison's own harness, one at a time and all
together, on the same two windows:

```bash
python -m research.modelica.blockers run ~/.greenhouse-open/modelica /tmp/fig8-screens fig8 screens
python -m research.modelica.blockers apportion
```

A variant is a model of its own, written into the run's working folder,
that extends TiGwerLib's global model, unchanged, with modifiers on its
components: each sets a parameter, or the value a component gives, and
none edits an equation. [`blockers.json`](blockers.json), committed before
any run, states each variant's modifiers, what each takes out, what could
not be made without an edit, and how the gap is attributed:

| Variant | Takes out |
| --- | --- |
| `screens` | the thermal and shading screens, held open |
| `crop` | the crop's transpiration: its minimum stomatal resistance a million times TiGwerLib's (as stated; it took nothing out, [below](#what-it-found)) |
| `storage` | the heat stored in the floor, the soil, the roof, the walls, the structure, the gutters and the growing medium: each capacity a hundredth of TiGwerLib's |
| `ground` | the floor's tie to the deep soil at 18.1 °C: the soil's conductivities a hundredth |
| `sky` | the cold sky: the roof and the south wall radiate to a sky at the outside air's temperature |
| `walls` | the corridors: the east and north walls face air at the outside air's temperature |
| `all` | the six together (five, since `crop` took nothing out) |
| `transpiration` | the crop's transpiration, as `crop` meant to: the canopy in TiGwerLib's `Custom` mode, its minimum stomatal resistance a million times TiGwerLib's |
| `all_six` | the six together, `transpiration` in `crop`'s place |

`transpiration` and `all_six` were stated in a commit of their own after
the first fourteen reports, which found `crop` a no-op, and before either
ran.

Not made, since each needs an edit: a west wall, which TiGwerLib does not
have; walls with the outside's wind and sky beyond them; a crop that
exchanges no heat; no heat capacity at all; and screens taken out rather
than held open.

A blocker's part, in each window, over all its moments and with the sun up
and down, is how far taking it out moves the RMSE and the mean of the
simulator's difference from TiGwerLib, from the comparison's own reports.
The blockers are ranked by the RMSE each takes away. The six moves need
not add up to the move all six make together: their sum is given beside
it, and the difference as the interaction, nothing rescaled. What the
`all` variant leaves is the gap no variant could close. The reports, in
`results/blockers/<variant>_<window>.json`, hold the comparison's numbers
alone.

### What it found

Each variant ran once on each window, from the commit that states them,
on the same machine as the comparison: its reports, in
[`results/blockers/`](results/blockers/), are committed as written, one
commit each. Six of them, July's `crop`, `storage`, `ground`, `sky` and
`walls` and January's `walls`, were written by the simulator's half
alone: their TiGwerLib simulation had finished when the run was stopped
before its report, and the report was written over that finished output,
the build and simulation seconds taken from the run's own logs. The
simulator's half is the comparison's, unchanged: `crop`'s reports give
the comparison's own numbers to the last digit.

A move is the comparison's RMSE of the difference less the variant's,
positive where taking the blocker out closes the gap; the share is the
part of the comparison's mean difference the variant takes away. The
difference is the simulator's temperature less TiGwerLib's.

January (`fig8`), from an RMSE of 5.20 K and a mean of −4.24 K (sun up
3.17 K, sun down 6.08 K), no day within 1.6 K:

| Variant | RMSE | Move | Mean | Share of the mean | Move, sun up | Move, sun down | Days within 1.6 K |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `screens` | 3.30 K | +1.90 K | −2.33 K | 45 % | +0.78 K | +2.35 K | 1 of 11 |
| `storage` | 4.00 K | +1.20 K | −3.57 K | 16 % | −0.50 K | +1.90 K | 0 of 11 |
| `walls` | 4.17 K | +1.03 K | −3.12 K | 26 % | +0.48 K | +1.25 K | 0 of 11 |
| `ground` | 4.49 K | +0.71 K | −3.79 K | 11 % | −0.35 K | +1.11 K | 0 of 11 |
| `crop` | 5.20 K | 0.00 K | −4.24 K | 0 % | 0.00 K | 0.00 K | 0 of 11 |
| `sky` | 6.52 K | −1.32 K | −5.68 K | −34 % | −0.98 K | −1.49 K | 0 of 11 |
| `all` | 3.15 K | +2.05 K | −2.47 K | 42 % | −1.28 K | +4.03 K | 2 of 11 |

July (`fig9`), from an RMSE of 3.57 K and a mean of +2.29 K (sun up
4.44 K, sun down 0.66 K), no day within 1.6 K:

| Variant | RMSE | Move | Mean | Share of the mean | Move, sun up | Move, sun down | Days within 1.6 K |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `storage` | 3.20 K | +0.37 K | +2.63 K | −15 % | +0.62 K | −0.94 K | 0 of 11 |
| `sky` | 3.26 K | +0.31 K | +1.72 K | 25 % | +0.46 K | −0.54 K | 0 of 11 |
| `ground` | 3.35 K | +0.22 K | +2.54 K | −11 % | +0.33 K | −0.48 K | 0 of 11 |
| `screens` | 3.50 K | +0.07 K | +2.22 K | 3 % | +0.09 K | 0.00 K | 0 of 11 |
| `crop` | 3.57 K | 0.00 K | +2.29 K | 0 % | 0.00 K | 0.00 K | 0 of 11 |
| `walls` | 3.62 K | −0.05 K | +2.37 K | −4 % | −0.07 K | +0.04 K | 0 of 11 |
| `all` | 2.63 K | +0.94 K | +2.04 K | 11 % | +1.26 K | −0.48 K | 0 of 11 |

- **The `crop` variant took nothing out.** TiGwerLib's global model runs
  its canopy's transpiration in Stanghellini's mode, where the minimum
  stomatal resistance is a constant of the equations, 82 s/m; `param1`,
  which the variant sets, is read in the `Custom` mode alone
  (`Flows.WaterVapourTransfer.CanopyTranspiration`). The crop's part is
  therefore not measured, and `all` takes out five blockers, not six. A
  variant that takes the transpiration out by modifiers alone sets the
  mode to `Custom` as well, whose other parameters' defaults are
  Stanghellini's constants; it ran afterwards as `transpiration`, stated
  in a commit of its own
  ([below](#the-crops-transpiration-taken-out)), and `blockers.json`
  keeps `crop` as it ran.
- **In January the screens account for the most:** held open, they take
  the RMSE from 5.20 to 3.30 K and 45 % of the mean difference, mostly at
  night, where the RMSE falls from 6.08 to 3.73 K. The heat stored
  (1.20 K), the corridors (1.03 K) and the deep soil (0.71 K) follow,
  each at night; the heat stored and the deep soil widen the gap by day.
- **The cold sky hides part of January's gap rather than making it:**
  without it, TiGwerLib's air radiates less and is warmer, and the
  simulator, which has no sky to radiate to either, falls further below
  it, by 1.32 K in the RMSE.
- **January's parts overlap:** the six single moves add up to 3.52 K
  where all of them at once close 2.05 K, an interaction of −1.47 K, so
  the parts are not additive there. All at once, two days of 11 come
  within the bar; the night's RMSE falls from 6.08 to 2.05 K and the
  day's rises from 3.17 to 4.45 K.
- **In July none of the first five taken out accounts for much:** the largest single
  move is 0.37 K, the heat stored, and all five together take the RMSE
  from 3.57 to 2.63 K, the single moves adding up (0.92 K against
  0.94 K). The day's warmth, +3.67 K on average, is still +2.58 K with all
  five out. The shading screen held open moves July's days by 0.09 K, so
  of the two blockers the comparison named for them, the transpiring
  crop, which this run could not take out, is the one left. Taken out
  afterwards, it accounts for them
  ([below](#the-crops-transpiration-taken-out)).
- **What no variant closes:** with all five out, the RMSE is still 3.15 K
  in January and 2.63 K in July, beyond the bar on 9 and 11 days of 11.
  That holds the crop's part and what the variants could not make
  without an edit, listed above. With the crop's transpiration out as
  well, July's RMSE comes to 1.89 K and January's to 5.39 K
  ([below](#the-crops-transpiration-taken-out)).
- **July's reports** compare 3,168 or 3,169 moments: the moment
  OpenModelica writes off its grid is in some variants' output and not in
  others'.
- **What it took:** TiGwerLib built each variant in 13 to 22 s and
  simulated it in 9 to 12 minutes in January and in 46 to 62 minutes in
  July; the simulator's half took 6 to 8 minutes. A report's simulator
  half peaks above 10 GB of memory, so on a machine of 32 GB the reports
  are written one at a time.

### The crop's transpiration, taken out

`crop` set `param1` alone. `transpiration` puts the canopy in TiGwerLib's
`Custom` mode as well, whose other parameters' defaults are Stanghellini's
constants (`param10` and `param11` read in thousandths), with `param1` a
million times its 82 s/m; `all_six` takes the six blockers out at once,
`transpiration` in `crop`'s place. Both were stated in
[`blockers.json`](blockers.json) after the first fourteen reports and
before either ran. Flattened by OpenModelica 1.25.0, `transpiration`
differs from `crop` in the mode and the five equations of Stanghellini's
resistances alone: its minimum stomatal resistance is bound to `param1`,
8.2e7 s/m, where `crop`'s is 82. Each ran once on each window, on the same
machine, and its reports are committed as written, one commit each.

January (`fig8`), from an RMSE of 5.20 K and a mean of −4.24 K:

| Variant | RMSE | Move | Mean | Share of the mean | Move, sun up | Move, sun down | Days within 1.6 K |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `transpiration` | 6.56 K | −1.36 K | −5.99 K | −41 % | −1.62 K | −1.32 K | 0 of 11 |
| `all_six` | 5.39 K | −0.19 K | −4.18 K | 1 % | −5.04 K | +3.47 K | 0 of 11 |

July (`fig9`), from an RMSE of 3.57 K and a mean of +2.29 K:

| Variant | RMSE | Move | Mean | Share of the mean | Move, sun up | Move, sun down | Days within 1.6 K |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `transpiration` | 2.97 K | +0.60 K | −1.29 K | 156 % | +1.76 K | −2.78 K | 0 of 11 |
| `all_six` | 1.89 K | +1.68 K | −1.29 K | 156 % | +2.10 K | +0.20 K | 2 of 11 |

- **In July the crop's transpiration accounts for the day's warmth.**
  Taken out alone, it takes the day's mean difference from +3.67 K to
  −0.15 K and the day's RMSE from 4.44 to 2.67 K: the largest single move
  in July, 0.60 K over the window, ahead of the heat stored (0.37 K). At
  night it widens the gap, from an RMSE of 0.66 to 3.43 K: without the
  crop's water, TiGwerLib's nights are 3.31 K warmer than the
  simulator's.
- **With all six out, July comes closest:** an RMSE of 1.89 K, two days
  of 11 within the bar, and the nights within 0.45 K. The single moves add
  up (1.52 K against 1.68 K). By day the simulator is then 1.81 K colder
  than TiGwerLib.
- **In January the transpiration hides part of the gap, as the cold sky
  does:** without it TiGwerLib's air is warmer, by day and by night, and
  the simulator, which has no crop giving the air water either, falls
  further below it: the RMSE goes from 5.20 to 6.56 K.
- **With all six out, January's nights close and its days open:** the
  night's RMSE falls from 6.08 to 2.61 K, the day's rises from 3.17 to
  8.21 K, the simulator 7.34 K colder by day, and over the window the
  RMSE is 5.39 K. The parts are far from additive there: the single moves
  add up to 2.17 K where all six at once move −0.19 K, an interaction of
  −2.36 K. What is left is the day: TiGwerLib's air, with no water taken
  by a crop and little heat stored, warms under January's sun much more
  than the simulator's.
- **Ranked again,** `transpiration` in `crop`'s place: in January the
  screens (1.90 K), the heat stored (1.20 K), the corridors (1.03 K), the
  deep soil (0.71 K), then the sky (−1.32 K) and the transpiration
  (−1.36 K), which hide part of the gap; in July the transpiration
  (0.60 K), the heat stored (0.37 K), the sky (0.31 K), the deep soil
  (0.22 K), the screens (0.07 K) and the corridors (−0.05 K).
- **What it took:** TiGwerLib built each in 12 or 13 s and simulated it in
  8 and 10 minutes in January and in 43 and 55 minutes in July; the
  simulator's half took 6 to 7 minutes.
