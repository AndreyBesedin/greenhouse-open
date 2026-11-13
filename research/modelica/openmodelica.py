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
- the dataset of Sourisseau et al. (2026), the paper TiGwerLib's global
  model was published with: its measurements and its model's outputs,
  fetched the same way, in `FOLDER`;
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
pinned: the image's digest on Docker Hub, each archive on Zenodo with the
checksum Zenodo published for it, and each library at its commit in
OpenModelica's package index, with that commit's archive. They are not
ours, so they can go away or move.

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
import urllib.error
import urllib.parse
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

ZENODO_RECORDS: Final = "https://zenodo.org/api/records"
# How long Zenodo and the package index may take to answer, in seconds.
FETCH_TIMEOUT_S: Final = 120


@dataclass(frozen=True)
class ZenodoFile:
    """A file of a Zenodo record: the md5 Zenodo published for it, which
    says it is still the file it was, and the sha256 pinned here, which a
    copy is checked by."""

    record: int
    name: str
    md5: str
    sha256: str

    @property
    def url(self) -> str:
        return f"{ZENODO_RECORDS}/{self.record}/files/{urllib.parse.quote(self.name)}/content"


# TiGwerLib 0.7.0, MIT, doi:10.5281/zenodo.15590404.
TIGWERLIB: Final = ZenodoFile(
    record=15590404,
    name="TiGwerLib_0_7_0.zip",
    md5="019f1aa5f5735fc42bc348246e3d6a20",
    sha256="9ed2c0b2ad6c0ba0d68b49bd0c597fb5a2fb3a61c8a4c0e9c1e8ea9aa9a1b1cb",
)
# The dataset of Sourisseau et al. (2026), doi:10.1371/journal.pone.0340619,
# CC BY 4.0, doi:10.5281/zenodo.17554203: the greenhouse's measurements
# and the global model's outputs, the data behind each of its figures.
SOURISSEAU_DATASET: Final = ZenodoFile(
    record=17554203,
    name="Supplementary_Information_v0.zip",
    md5="d0e4486fa1041fac5e6e47673b6c95d3",
    sha256="5462cecc6874262f18136971a8ec7c6db33374c8ff2cadb8f9309a61ece8e480",
)


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

# What a build and a simulation leave in their working folder, and are
# then read by. Each removes an earlier one's first, so that a step failing
# now cannot pass on them; each step's log goes the same way.
BUILT: Final = MODEL
RESULTS: Final = (f"{MODEL}_res.mat", f"{MODEL}_res.csv")
# What OpenModelica's simulation writes when it has run to its end.
FINISHED: Final = "The simulation finished successfully."


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
    archive = _fetch(TIGWERLIB, folder)
    _fetch(SOURISSEAU_DATASET, folder)
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
    build = build_global_model(folder, workdir, START_S + DAY_S)
    return build, simulate_global_model(folder, workdir, solver)


def build_global_model(
    folder: Path,
    workdir: Path,
    stop_s: int,
    *,
    variables: str | None = None,
    output_format: str = "mat",
) -> Measured:
    """Builds TiGwerLib's global model in `workdir`, from its experiment's
    start to `stop_s`, with a result at each of its intervals: of every
    variable, or of those whose names match `variables`, a regular
    expression."""
    _require_docker()
    workdir.mkdir(parents=True, exist_ok=True)
    for output in (BUILT, *RESULTS):
        (workdir / output).unlink(missing_ok=True)
    script = _build_script(stop_s, variables=variables, output_format=output_format)
    (workdir / "build.mos").write_text(script, encoding="utf-8")
    build = _measured_step(folder, workdir, "build", "omc", "build.mos")
    if not (workdir / BUILT).is_file():
        raise CheckFailed(f"the model did not build: see {workdir / 'build.log'}")
    return build


def simulate_global_model(folder: Path, workdir: Path, solver: str = SOLVER) -> Measured:
    """Simulates the model built in `workdir` with `solver`, its results at
    its intervals alone, not at its events too."""
    for output in RESULTS:
        (workdir / output).unlink(missing_ok=True)
    simulate = _measured_step(
        folder, workdir, "simulate", f"./{BUILT}", f"-s={solver}", "-noEventEmit", "-lv=LOG_STATS"
    )
    log = (workdir / "simulate.log").read_text(encoding="utf-8", errors="replace")
    if FINISHED not in log:
        raise CheckFailed(f"the model was not simulated to its end: see {workdir / 'simulate.log'}")
    return simulate


def verify_pins() -> None:
    """Refuses the pins unless each is still published as pinned: the
    image's digest, each archive with the checksum Zenodo published for it,
    and each library at its commit in the package index, with that commit's
    archive."""
    try:
        verify_published(IMAGE)
    except ImageNotPublished as error:
        raise PinRefused(str(error)) from error
    for archive in (TIGWERLIB, SOURISSEAU_DATASET):
        _verify_on_zenodo(archive)
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
                "published as pinned: the image's digest, each archive, "
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
    results = arguments.workdir / RESULTS[0]
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


def _fetch(archive: ZenodoFile, folder: Path) -> Path:
    """`archive` in `folder`, downloaded unless a copy is there, and refused
    unless its sha256 is the one pinned. Two archives, a library and a
    paper's data: the adapters' storage is for datasets the adapters read,
    by their manifests."""
    path = folder / archive.name
    if not path.is_file() or _sha256(path) != archive.sha256:
        partial = path.with_suffix(".part")
        with urllib.request.urlopen(archive.url, timeout=FETCH_TIMEOUT_S) as response:
            partial.write_bytes(response.read())
        partial.replace(path)
    found = _sha256(path)
    if found != archive.sha256:
        path.unlink()
        raise PinRefused(f"{archive.name}'s sha256 is {found}, not {archive.sha256}")
    return path


def _verify_on_zenodo(archive: ZenodoFile) -> None:
    """Refuses `archive` unless its record still lists it with the md5
    Zenodo published for it: a record's files do not change, a new version
    is a new record, so this downloads none of them."""
    try:
        record = _json(f"{ZENODO_RECORDS}/{archive.record}")
    except urllib.error.HTTPError as error:
        raise PinRefused(f"Zenodo no longer has record {archive.record} ({error.code})") from error
    listed = {entry["key"]: entry.get("checksum") for entry in record.get("files", [])}
    if archive.name not in listed:
        raise PinRefused(f"Zenodo's record {archive.record} no longer lists {archive.name}")
    if listed[archive.name] != f"md5:{archive.md5}":
        raise PinRefused(
            f"Zenodo lists {archive.name} with {listed[archive.name]}, not md5:{archive.md5}"
        )


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


def _build_script(stop_s: int, *, variables: str | None, output_format: str) -> str:
    kept = "" if variables is None else f', variableFilter="{variables}"'
    return (
        f'if not loadModel(Modelica, {{"4.0.0"}}) then print(getErrorString()); exit(1); end if;\n'
        f'if not loadModel(Buildings, {{"9.1.0"}}) then print(getErrorString()); exit(1); end if;\n'
        f'if not loadFile("{TIGWERLIB_MOUNT}/TiGwerLib/package.mo") then '
        f"print(getErrorString()); exit(1); end if;\n"
        f"buildModel({MODEL}, startTime={START_S}, stopTime={stop_s}, "
        f"numberOfIntervals={(stop_s - START_S) // INTERVAL_S}, tolerance={TOLERANCE}, "
        f'outputFormat="{output_format}"{kept});\n'
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
