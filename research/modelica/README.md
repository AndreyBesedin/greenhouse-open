# OpenModelica, for the Modelica comparison

Item 6 of the [research priorities](../../docs/roadmap/research-validation-priorities.md)
compares the simulator with a Modelica model: one documented, measured
interval of TiGwerLib reproduced in OpenModelica, then compared on matched
inputs. This folder sets OpenModelica up for it, apart from the
repository's own environment, and checks the setup on TiGwerLib's global
model. It reproduces nothing yet.

## What it runs on

| What | Version | Pinned by |
| --- | --- | --- |
| OpenModelica | 1.25.0, its `minimal` image, for arm64 and amd64 | the image index's digest, `sha256:c85938d4dd4cdc15ea2d2af899920907e707ef94243e13603bd347679e5e6a14` |
| TiGwerLib | 0.7.0, MIT, [doi:10.5281/zenodo.15590404](https://doi.org/10.5281/zenodo.15590404) | its archive's sha256, `9ed2c0b2ad6c0ba0d68b49bd0c597fb5a2fb3a61c8a4c0e9c1e8ea9aa9a1b1cb` |
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
rule 1).

## Setting it up

Docker must be running: Docker Desktop on macOS or Windows, Docker Engine
on Linux. Then, from the repository's root:

```bash
python -m research.modelica.openmodelica setup ~/.greenhouse-open/modelica
python -m research.modelica.openmodelica check ~/.greenhouse-open/modelica /tmp/modelica-check
```

`setup` pulls the image, fetches TiGwerLib into `tigwerlib/` and installs
the libraries into `home/`. It can run again: what is there and pinned is
kept. `check` builds TiGwerLib's global model,
`TiGwerLib.Applications.CTIFLGreenhouse.GlobalModels.UsingStatuses.CTIFLGreenhouseBaseModel`,
over the first day of its experiment. It simulates the day with DASSL,
OpenModelica's default solver, at the experiment's tolerance (1e-5) and
interval (300 s). It prints what each step took, and leaves the build,
the results and both logs in its working folder. It first removes what an
earlier check left there, and stops at a step that fails.

Any other command runs in the same container:

```bash
python -m research.modelica.openmodelica run ~/.greenhouse-open/modelica WORKDIR -- omc script.mos
```

The command runs in `WORKDIR`, as the user who runs it. The libraries are
on its `MODELICAPATH`, and TiGwerLib is read-only at `/tigwerlib`. A model
reads its data from the paths it was built with, so it is built and run
with TiGwerLib at that same place.

It has run on macOS and on Linux. Windows has no user ids to give the
container, so there a command runs as the image's own user; that has not
been tried yet.

The [Modelica workflow](../../.github/workflows/modelica.yml) sets it up
and runs the check on GitHub's Linux runners. It runs when this folder,
the lock or the Python changes, and its logs are kept as an artifact.

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

The peak is the container's, from its control group, the page cache
included. The build is the heavy step: it needs about 3 GB in Docker's
virtual machine, and it slows tenfold when the Mac has to swap that
machine's memory out. On 8 GB, it runs best with other large
applications closed, and Docker Desktop quit after it.

A longer run is light in memory but heavy on disk. At 62 MB a day, the
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
