"""OpenModelica in its container, set up for the Modelica comparison (item 6
of the research priorities), and checked on TiGwerLib's global model.

    python -m research.modelica.openmodelica setup FOLDER
    python -m research.modelica.openmodelica check FOLDER WORKDIR
    python -m research.modelica.openmodelica run FOLDER WORKDIR -- omc script.mos
    python -m research.modelica.openmodelica verify

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

`verify` checks, without Docker, that every pin is still published as
pinned: the image's digest on Docker Hub, TiGwerLib's archive on Zenodo,
and each library at its commit in OpenModelica's package index, with that
commit's archive. They are not ours, so they can go away or move.

Running a container is `greenhouse_sim.containers`'s. What is here is
OpenModelica's: its image, the libraries and where the container sees
them, and TiGwerLib's model. Like that module, it needs Python's standard
library alone. Nothing in the packages imports this, and nothing it
fetches is committed (decision 0063, rule 1).
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from greenhouse_sim.containers import (
    ImageNotPublished,
    Measured,
    Mount,
    docker_run,
    docker_running,
    run_measured,
    verify_published,
)

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

# TiGwerLib 0.7.0, MIT, doi:10.5281/zenodo.15590404: its archive, where
# Zenodo publishes it, and the archive's sha256.
TIGWERLIB_URL: Final = "https://zenodo.org/api/records/15590404/files/TiGwerLib_0_7_0.zip/content"
TIGWERLIB_ARCHIVE: Final = "TiGwerLib_0_7_0.zip"
TIGWERLIB_SHA256: Final = "9ed2c0b2ad6c0ba0d68b49bd0c597fb5a2fb3a61c8a4c0e9c1e8ea9aa9a1b1cb"
# How long Zenodo and the package index may take to answer, in seconds.
FETCH_TIMEOUT_S: Final = 120


@dataclass(frozen=True)
class Library:
    """A Modelica library as OpenModelica's package manager installs it: the
    version its index names, and the commit it installs that version from,
    which it records beside the library."""

    name: str
    version: str
    commit: str


# OpenModelica's package index: for each library and version, the commit
# its package manager installs, and that commit's archive.
PACKAGE_INDEX: Final = "https://libraries.openmodelica.org/index/v1/index.json"

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

# What a check builds and simulates in its working folder, and then reads.
# A check removes an earlier check's first, so that a step failing now
# cannot pass on them; each step's log goes the same way.
CHECK_OUTPUTS: Final = (MODEL, f"{MODEL}_res.mat")


class OpenModelicaUnavailable(RuntimeError):
    """Docker is not running, so OpenModelica's container cannot be."""


class PinRefused(RuntimeError):
    """What was fetched, installed or published is not what is pinned here."""


class CheckFailed(RuntimeError):
    """A step of the check did not finish."""


def set_up_openmodelica(folder: Path) -> None:
    """Pulls the image, fetches TiGwerLib and installs its libraries."""
    _require_docker()
    (folder / "home").mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "pull", "--quiet", IMAGE], check=True)
    archive = _fetch_tigwerlib(folder)
    extracted = folder / "tigwerlib"
    if not (extracted / "TiGwerLib" / "package.mo").is_file():
        shutil.rmtree(extracted, ignore_errors=True)
        with zipfile.ZipFile(archive) as unpacked:
            unpacked.extractall(extracted)
    _install_libraries(folder)


def check_global_model(
    folder: Path, workdir: Path, solver: str = SOLVER
) -> tuple[Measured, Measured]:
    """Builds TiGwerLib's global model over its experiment's first day in
    `workdir`, and simulates the day with `solver`."""
    _require_docker()
    workdir.mkdir(parents=True, exist_ok=True)
    for output in CHECK_OUTPUTS:
        (workdir / output).unlink(missing_ok=True)
    (workdir / "build.mos").write_text(_build_script(), encoding="utf-8")
    build = _measured_step(folder, workdir, "build", "omc", "build.mos")
    if not (workdir / MODEL).is_file():
        raise CheckFailed(f"the model did not build: see {workdir / 'build.log'}")
    simulate = _measured_step(
        folder, workdir, "simulate", f"./{MODEL}", f"-s={solver}", "-lv=LOG_STATS"
    )
    log = (workdir / "simulate.log").read_text(encoding="utf-8", errors="replace")
    if "The simulation finished successfully." not in log:
        raise CheckFailed(f"the day was not simulated: see {workdir / 'simulate.log'}")
    return build, simulate


def verify_pins() -> None:
    """Refuses the pins unless each is still published as pinned: the
    image's digest, TiGwerLib's archive, and each library at its commit in
    the package index, with that commit's archive."""
    try:
        verify_published(IMAGE)
    except ImageNotPublished as error:
        raise PinRefused(str(error)) from error
    with tempfile.TemporaryDirectory() as folder:
        _fetch_tigwerlib(Path(folder))
    _verify_package_index(_json(PACKAGE_INDEX))


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
    commands.add_parser("verify")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "verify":
            verify_pins()
            sys.stdout.write(
                "published as pinned: the image's digest, TiGwerLib's archive, "
                "and each library at its commit\n"
            )
            return 0
        if arguments.command == "setup":
            set_up_openmodelica(arguments.folder)
            sys.stdout.write(f"set up in {arguments.folder}\n")
            return 0
        if arguments.command == "run":
            given = arguments.argv[1:] if arguments.argv[:1] == ["--"] else arguments.argv
            if not given:
                parser.error("run needs a command")
            _require_docker()
            return subprocess.run(_command(arguments.folder, arguments.workdir, *given)).returncode
        build, simulate = check_global_model(arguments.folder, arguments.workdir, arguments.solver)
    except (OpenModelicaUnavailable, PinRefused, CheckFailed) as error:
        raise SystemExit(str(error)) from error
    results = arguments.workdir / f"{MODEL}_res.mat"
    sys.stdout.write(
        f"build: {_described(build)}\n"
        f"simulate, one day with {arguments.solver}: {_described(simulate)}, "
        f"results {results.stat().st_size / 1e6:.0f} MB\n"
    )
    return 0


def _mounts(folder: Path) -> list[Mount]:
    """The folder's home, as the container's user's, and TiGwerLib,
    read-only, where a model built in one run finds its data in the next."""
    return [
        Mount(folder / "home", HOME),
        Mount(folder / "tigwerlib", TIGWERLIB_MOUNT, read_only=True),
    ]


def _command(folder: Path, workdir: Path, *argv: str) -> list[str]:
    """The `docker run` that runs `argv` in OpenModelica's container, in
    `workdir`, with `folder`'s home and TiGwerLib."""
    return docker_run(
        IMAGE,
        argv,
        mounts=[*_mounts(folder), Mount(workdir, WORK)],
        workdir=WORK,
        environment={"HOME": HOME},
    )


def _measured_step(folder: Path, workdir: Path, name: str, *argv: str) -> Measured:
    """Runs a step of the check, its output in `<name>.log`, and fails
    unless it exits cleanly."""
    step = run_measured(
        IMAGE,
        argv,
        workdir=Mount(workdir, WORK),
        name=name,
        mounts=_mounts(folder),
        environment={"HOME": HOME},
    )
    if step.status != 0:
        log = workdir / f"{name}.log"
        # Without a log, the container did not start: Docker said why.
        where = f"see {log}" if log.is_file() else "see Docker's message above"
        raise CheckFailed(f"the {name} step exited with status {step.status}: {where}")
    return step


def _require_docker() -> None:
    if not docker_running():
        raise OpenModelicaUnavailable("Docker is not installed, or not running")


def _fetch_tigwerlib(folder: Path) -> Path:
    """TiGwerLib's archive in `folder`, downloaded unless a copy is there,
    and refused unless its sha256 is the one pinned. One archive, checked
    by the sha256 its record gives: the adapters' storage is for datasets,
    by their manifests."""
    path = folder / TIGWERLIB_ARCHIVE
    if not path.is_file() or _sha256(path) != TIGWERLIB_SHA256:
        partial = path.with_suffix(".part")
        with urllib.request.urlopen(TIGWERLIB_URL, timeout=FETCH_TIMEOUT_S) as response:
            partial.write_bytes(response.read())
        partial.replace(path)
    found = _sha256(path)
    if found != TIGWERLIB_SHA256:
        path.unlink()
        raise PinRefused(f"{TIGWERLIB_ARCHIVE}'s sha256 is {found}, not {TIGWERLIB_SHA256}")
    return path


def _install_libraries(folder: Path) -> None:
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
    _verify_installed_libraries(folder / "home" / ".openmodelica" / "libraries")


def _verify_installed_libraries(libraries: Path) -> None:
    """Refuses the libraries installed in `libraries` unless each is
    installed, from the commit pinned here."""
    for library in LIBRARIES:
        metadata = libraries / f"{library.name} {library.version}" / "openmodelica.metadata.json"
        if not metadata.is_file():
            raise PinRefused(f"{library.name} {library.version} is not installed")
        commit = json.loads(metadata.read_text(encoding="utf-8")).get("sha")
        if commit != library.commit:
            raise PinRefused(
                f"{library.name} {library.version} was installed from {commit}, "
                f"not {library.commit}: set up a folder of its own"
            )


def _verify_package_index(index: dict[str, Any]) -> None:
    """Refuses OpenModelica's package index unless it still offers each
    library at its version, from the commit pinned here, and that commit's
    archive is still there."""
    archives = []
    for library in LIBRARIES:
        offered = index["libs"].get(library.name, {}).get("versions", {}).get(library.version)
        if offered is None:
            raise PinRefused(f"the package index no longer offers {library.name} {library.version}")
        if offered.get("sha") != library.commit:
            raise PinRefused(
                f"the package index offers {library.name} {library.version} "
                f"from {offered.get('sha')}, not {library.commit}"
            )
        archives.append(offered["zipfile"])
    # The standard library's three share one archive.
    for archive in dict.fromkeys(archives):
        request = urllib.request.Request(archive, method="HEAD")
        try:
            urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S).close()
        except urllib.error.HTTPError as error:
            raise PinRefused(f"{archive} is no longer there ({error.code})") from error


def _omc_script(folder: Path, name: str, *calls: str) -> None:
    """Runs `calls` in omc, in `folder`, stopping at the first that fails."""
    lines = [f"if not {call} then print(getErrorString()); exit(1); end if;" for call in calls]
    (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(_command(folder, folder, "omc", name), check=True)


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


def _described(step: Measured) -> str:
    memory = "unknown" if step.peak_bytes is None else f"{step.peak_bytes / 2**30:.1f} GiB"
    return f"{step.seconds:.0f} s, peak memory {memory}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_S) as response:
        return json.loads(response.read())


if __name__ == "__main__":
    sys.exit(main())
