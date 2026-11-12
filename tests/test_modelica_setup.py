"""The OpenModelica setup holds what it fetches and installs to its pins
(research/modelica), without Docker: what a run in its container is given,
an archive refused unless its sha256 is pinned, a library refused unless it
was installed from its pinned commit, a check failing on what fails in it
rather than passing on what an earlier check left, and the README naming
every pin.
"""

import hashlib
import io
import json
import os
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pytest

from research.modelica import openmodelica as om

README = Path(om.__file__).with_name("README.md")


def test_a_run_is_its_users_with_the_folders_home_and_tigwerlib_read_only(
    tmp_path: Path,
) -> None:
    # A model built in one run reads TiGwerLib's data in the next from the
    # paths it was built with, so TiGwerLib is always at the same place.
    folder, work = tmp_path / "folder", tmp_path / "work"
    argv = om.command(folder, work, "omc", "build.mos")
    assert argv[:3] == ["docker", "run", "--rm"]
    assert argv[argv.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
    assert argv[argv.index("--env") + 1] == f"HOME={om.HOME}"
    volumes = [argv[at + 1] for at, given in enumerate(argv) if given == "--volume"]
    assert volumes == [
        f"{folder.resolve() / 'home'}:{om.HOME}",
        f"{folder.resolve() / 'tigwerlib'}:/tigwerlib:ro",
        f"{work.resolve()}:/work",
    ]
    assert argv[-3:] == [om.IMAGE, "omc", "build.mos"]


def test_a_run_on_windows_is_the_images_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Windows has no user ids to give the container.
    monkeypatch.delattr(os, "getuid")
    monkeypatch.delattr(os, "getgid")
    argv = om.command(tmp_path / "folder", tmp_path / "work", "omc", "build.mos")
    assert "--user" not in argv
    assert argv[argv.index("--env") + 1] == f"HOME={om.HOME}"


def test_an_archive_is_refused_unless_its_sha256_is_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = om.Archive(
        url="https://example.invalid/a.zip",
        name="a.zip",
        sha256=hashlib.sha256(b"pinned").hexdigest(),
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"other"))
    with pytest.raises(om.Refused, match="sha256"):
        om.fetch(archive, tmp_path)
    assert not (tmp_path / "a.zip").exists()

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"pinned"))
    assert om.fetch(archive, tmp_path).read_bytes() == b"pinned"

    # A copy that is there, as pinned, is not downloaded again.
    def offline(url: str, timeout: float) -> io.BytesIO:
        raise AssertionError(f"downloaded {url} again")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    assert om.fetch(archive, tmp_path).read_bytes() == b"pinned"


def test_a_library_is_refused_unless_installed_from_its_pinned_commit(tmp_path: Path) -> None:
    for library in om.LIBRARIES:
        installed = tmp_path / f"{library.name} {library.version}"
        installed.mkdir()
        (installed / "openmodelica.metadata.json").write_text(
            json.dumps({"sha": library.commit, "version": library.version})
        )
    om.verify_installed(tmp_path)

    moved = om.LIBRARIES[-1]
    metadata = tmp_path / f"{moved.name} {moved.version}" / "openmodelica.metadata.json"
    metadata.write_text(json.dumps({"sha": "0" * 40, "version": moved.version}))
    with pytest.raises(om.Refused, match=f"{moved.name} {moved.version} was installed from 0+,"):
        om.verify_installed(tmp_path)

    metadata.unlink()
    with pytest.raises(om.Refused, match=f"{moved.name} {moved.version} is not installed"):
        om.verify_installed(tmp_path)


def test_a_check_fails_on_its_own_steps_not_on_what_an_earlier_one_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, work = tmp_path / "folder", tmp_path / "work"
    monkeypatch.setattr(om, "_require_docker", lambda: None)

    def left_by_an_earlier_check() -> None:
        work.mkdir(exist_ok=True)
        (work / om.MODEL).write_text("built earlier")
        (work / f"{om.MODEL}_res.mat").write_text("simulated earlier")
        (work / "simulate.log").write_text("The simulation finished successfully.\n")

    def ran(status: int) -> Callable[..., subprocess.CompletedProcess[bytes]]:
        return lambda argv, check: subprocess.CompletedProcess(argv, status)

    # The container does not start: Docker exits with 125 and writes nothing.
    left_by_an_earlier_check()
    monkeypatch.setattr(subprocess, "run", ran(125))
    with pytest.raises(om.Failed, match="the build step exited with status 125: see Docker's"):
        om.check(folder, work)

    # omc exits cleanly and builds nothing.
    left_by_an_earlier_check()
    monkeypatch.setattr(subprocess, "run", ran(0))
    with pytest.raises(om.Failed, match="the model did not build"):
        om.check(folder, work)


def test_the_readme_names_every_pin() -> None:
    readme = README.read_text(encoding="utf-8")
    digest = om.IMAGE.partition("@")[2]
    pins = [digest, om.TIGWERLIB.sha256, *(library.commit for library in om.LIBRARIES)]
    assert [pin for pin in pins if pin not in readme] == []
