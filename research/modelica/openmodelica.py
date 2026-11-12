"""OpenModelica in its container, set up for the Modelica comparison (item 6
of the research priorities), and checked on TiGwerLib's global model.

    python -m research.modelica.openmodelica setup FOLDER
    python -m research.modelica.openmodelica check FOLDER WORKDIR
    python -m research.modelica.openmodelica run FOLDER WORKDIR -- omc script.mos

`setup` makes FOLDER hold everything the comparison runs on, apart from
the repository:
- OpenModelica 1.25.0's image, pulled by digest;
- TiGwerLib 0.7.0, fetched from its Zenodo record and checked by its
  sha256, in `FOLDER/tigwerlib`;
- the libraries TiGwerLib uses, installed into `FOLDER/home` by
  OpenModelica's package manager, each refused unless it was installed
  from the commit pinned here.

`run` runs a command in the container, in WORKDIR, with that home as the
user's and TiGwerLib read-only at `/tigwerlib`. A model built
there reads its data from the paths it was built with, so it finds them
again when it runs. `check` builds TiGwerLib's global model over the first
day of its experiment in WORKDIR, simulates that day, and prints the time
and the peak memory each step took.

Nothing in the packages imports this, and nothing it fetches is committed
(decision 0063, rule 1).
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# The release TiGwerLib 0.7.0 was tested with, by digest as well as by tag:
# the image index's, which holds an arm64 and an amd64 image.
IMAGE: Final = (
    "openmodelica/openmodelica:v1.25.0-minimal"
    "@sha256:c85938d4dd4cdc15ea2d2af899920907e707ef94243e13603bd347679e5e6a14"
)

# Where the container sees the folder's parts and the working directory.
HOME: Final = "/omhome"
TIGWERLIB_MOUNT: Final = "/tigwerlib"
WORK: Final = "/work"


@dataclass(frozen=True)
class Archive:
    """A file fetched from its publisher and checked by its sha256."""

    url: str
    name: str
    sha256: str


# TiGwerLib 0.7.0, MIT, doi:10.5281/zenodo.15590404.
TIGWERLIB: Final = Archive(
    url="https://zenodo.org/api/records/15590404/files/TiGwerLib_0_7_0.zip/content",
    name="TiGwerLib_0_7_0.zip",
    sha256="9ed2c0b2ad6c0ba0d68b49bd0c597fb5a2fb3a61c8a4c0e9c1e8ea9aa9a1b1cb",
)


@dataclass(frozen=True)
class Library:
    """A Modelica library as OpenModelica's package manager installs it: the
    version its index names, and the commit it installs that version from,
    which it records beside the library."""

    name: str
    version: str
    commit: str


# What TiGwerLib's `uses` asks for: the Modelica Standard Library 4.0.0, as
# OpenModelica's maintenance branch of it, with the two libraries that come
# from the same commit, and the Buildings library 9.1.0. Its `uses` also
# names Dymola's DymolaCommands and DataFiles, which OpenModelica does not
# have and nothing in TiGwerLib refers to.
_STANDARD_LIBRARY: Final = "bbdadca3e90d73e42b9c86e184e8a5fb2a8120a8"
LIBRARIES: Final = (
    Library("Modelica", "4.0.0+maint.om", _STANDARD_LIBRARY),
    Library("ModelicaServices", "4.0.0+maint.om", _STANDARD_LIBRARY),
    Library("Complex", "4.0.0+maint.om", _STANDARD_LIBRARY),
    Library("Buildings", "9.1.0", "d34a259960ca12b2126ef188f2d20fc8148eafb2"),
)

# TiGwerLib's global model, and its experiment: it starts at 29,030,400 s,
# with a result every 300 s, at a tolerance of 1e-5.
MODEL: Final = (
    "TiGwerLib.Applications.CTIFLGreenhouse.GlobalModels.UsingStatuses.CTIFLGreenhouseBaseModel"
)
START_S: Final = 29_030_400
DAY_S: Final = 86_400
INTERVAL_S: Final = 300
TOLERANCE: Final = 1e-5
# OpenModelica's default solver. The experiment names Dymola's Cvode, with
# which OpenModelica's run stops in its first second (the README).
SOLVER: Final = "dassl"
SOLVERS: Final = ("dassl", "cvode", "ida")


class Unavailable(RuntimeError):
    """Docker is not running, so OpenModelica's container cannot be."""


class Refused(RuntimeError):
    """What was fetched or installed is not what is pinned here."""


class Failed(RuntimeError):
    """A step of the check did not finish."""


@dataclass(frozen=True)
class Step:
    """What a step in the container took."""

    seconds: float
    peak_bytes: int | None


def command(folder: Path, workdir: Path, *argv: str) -> list[str]:
    """The `docker run` that runs `argv` in OpenModelica's container: in
    `workdir`, as the user who runs it, with `folder`'s home and TiGwerLib."""
    return [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--env",
        f"HOME={HOME}",
        "--volume",
        f"{folder.resolve() / 'home'}:{HOME}",
        "--volume",
        f"{folder.resolve() / 'tigwerlib'}:{TIGWERLIB_MOUNT}:ro",
        "--volume",
        f"{workdir.resolve()}:{WORK}",
        "--workdir",
        WORK,
        IMAGE,
        *argv,
    ]


def setup(folder: Path) -> None:
    """Pulls the image, fetches TiGwerLib and installs its libraries."""
    _require_docker()
    (folder / "home").mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "pull", "--quiet", IMAGE], check=True)
    fetch(TIGWERLIB, folder)
    extracted = folder / "tigwerlib"
    if not (extracted / "TiGwerLib" / "package.mo").is_file():
        shutil.rmtree(extracted, ignore_errors=True)
        with zipfile.ZipFile(folder / TIGWERLIB.name) as archive:
            archive.extractall(extracted)
    _install(folder)


def fetch(archive: Archive, folder: Path) -> Path:
    """`archive` in `folder`, downloaded unless a copy is there, and refused
    unless its sha256 is the one pinned."""
    path = folder / archive.name
    if not path.is_file() or _sha256(path) != archive.sha256:
        partial = path.with_suffix(".part")
        with urllib.request.urlopen(archive.url, timeout=120) as response:
            partial.write_bytes(response.read())
        partial.replace(path)
    found = _sha256(path)
    if found != archive.sha256:
        path.unlink()
        raise Refused(f"{archive.name}'s sha256 is {found}, not {archive.sha256}")
    return path


def verify_installed(libraries: Path) -> None:
    """Refuses the libraries installed in `libraries` unless each is
    installed, from the commit pinned here."""
    for library in LIBRARIES:
        metadata = libraries / f"{library.name} {library.version}" / "openmodelica.metadata.json"
        if not metadata.is_file():
            raise Refused(f"{library.name} {library.version} is not installed")
        commit = json.loads(metadata.read_text(encoding="utf-8")).get("sha")
        if commit != library.commit:
            raise Refused(
                f"{library.name} {library.version} was installed from {commit}, "
                f"not {library.commit}: set up a folder of its own"
            )


def check(folder: Path, workdir: Path, solver: str = SOLVER) -> tuple[Step, Step]:
    """Builds TiGwerLib's global model over its experiment's first day in
    `workdir`, and simulates the day with `solver`."""
    _require_docker()
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "build.mos").write_text(_build_script(), encoding="utf-8")
    build = _step(folder, workdir, "build", "omc", "build.mos")
    if not (workdir / MODEL).is_file():
        raise Failed(f"the model did not build: see {workdir / 'build.log'}")
    simulate = _step(folder, workdir, "simulate", f"./{MODEL}", f"-s={solver}", "-lv=LOG_STATS")
    log = (workdir / "simulate.log").read_text(encoding="utf-8", errors="replace")
    if "The simulation finished successfully." not in log:
        raise Failed(f"the day was not simulated: see {workdir / 'simulate.log'}")
    return build, simulate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup").add_argument("folder", type=Path)
    checking = commands.add_parser("check")
    checking.add_argument("folder", type=Path)
    checking.add_argument("workdir", type=Path)
    checking.add_argument("--solver", choices=SOLVERS, default=SOLVER)
    running = commands.add_parser("run")
    running.add_argument("folder", type=Path)
    running.add_argument("workdir", type=Path)
    running.add_argument("argv", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "setup":
            setup(arguments.folder)
            sys.stdout.write(f"set up in {arguments.folder}\n")
            return 0
        if arguments.command == "run":
            given = arguments.argv[1:] if arguments.argv[:1] == ["--"] else arguments.argv
            if not given:
                parser.error("run needs a command")
            _require_docker()
            return subprocess.run(command(arguments.folder, arguments.workdir, *given)).returncode
        build, simulate = check(arguments.folder, arguments.workdir, arguments.solver)
    except (Unavailable, Refused, Failed) as error:
        raise SystemExit(str(error)) from error
    results = arguments.workdir / f"{MODEL}_res.mat"
    sys.stdout.write(
        f"build: {_described(build)}\n"
        f"simulate, one day with {arguments.solver}: {_described(simulate)}, "
        f"results {results.stat().st_size / 1e6:.0f} MB\n"
    )
    return 0


def _require_docker() -> None:
    if shutil.which("docker") is None:
        raise Unavailable("Docker is not installed")
    found = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        check=False,
    )
    if found.returncode != 0:
        raise Unavailable("Docker is not running")


def _install(folder: Path) -> None:
    """Installs the libraries from OpenModelica's package index, and checks
    what was installed."""
    _omc_script(
        folder,
        "install.mos",
        "updatePackageIndex()",
        *(
            f'installPackage({library.name}, "{library.version}", exactMatch=true)'
            for library in LIBRARIES
        ),
    )
    verify_installed(folder / "home" / ".openmodelica" / "libraries")


def _omc_script(folder: Path, name: str, *calls: str) -> None:
    """Runs `calls` in omc, in `folder`, stopping at the first that fails."""
    lines = [f"if not {call} then print(getErrorString()); exit(1); end if;" for call in calls]
    (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(command(folder, folder, "omc", name), check=True)


def _build_script() -> str:
    return (
        f'if not loadModel(Modelica, {{"4.0.0"}}) then print(getErrorString()); exit(1); end if;\n'
        f'if not loadModel(Buildings, {{"9.1.0"}}) then print(getErrorString()); exit(1); end if;\n'
        f'if not loadFile("{TIGWERLIB_MOUNT}/TiGwerLib/package.mo") then '
        f"print(getErrorString()); exit(1); end if;\n"
        f"buildModel({MODEL}, startTime={START_S}, stopTime={START_S + DAY_S}, "
        f"numberOfIntervals={DAY_S // INTERVAL_S}, tolerance={TOLERANCE});\n"
        f"print(getErrorString());\n"
    )


def _step(folder: Path, workdir: Path, name: str, *argv: str) -> Step:
    """Runs `argv` in the container, its output in `<name>.log`, and keeps
    the container's peak memory, where its control group gives it."""
    wrapped = (
        f'"$@" > {name}.log 2>&1; status=$?; '
        f"cat /sys/fs/cgroup/memory.peak > {name}.peak 2>/dev/null; exit $status"
    )
    started = time.monotonic()
    subprocess.run(command(folder, workdir, "sh", "-c", wrapped, "sh", *argv), check=False)
    seconds = time.monotonic() - started
    peak = workdir / f"{name}.peak"
    text = peak.read_text(encoding="utf-8").strip() if peak.is_file() else ""
    return Step(seconds, int(text) if text.isdigit() else None)


def _described(step: Step) -> str:
    memory = "unknown" if step.peak_bytes is None else f"{step.peak_bytes / 2**30:.1f} GiB"
    return f"{step.seconds:.0f} s, peak memory {memory}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
