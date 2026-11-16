"""The OpenModelica setup holds what it fetches and installs to its pins
(research/modelica), without Docker: where a run in its container finds
the libraries and TiGwerLib, an archive refused unless its sha256 is
pinned, a library refused unless it was installed from its pinned commit,
the pins refused unless they are still published as pinned, a check
failing on what fails in it rather than passing on what an earlier check
left, and the README naming every pin. How a container is run is
`greenhouse_sim.containers`'s, and tested there.
"""

import hashlib
import io
import json
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from research.modelica import openmodelica as om

README = Path(om.__file__).with_name("README.md")


def test_a_run_has_the_folders_home_and_tigwerlib_read_only(tmp_path: Path) -> None:
    # A model built in one run reads TiGwerLib's data in the next from the
    # paths it was built with, so TiGwerLib is always at the same place.
    folder, work = tmp_path / "folder", tmp_path / "work"
    argv = om._command(folder, work, "omc", "build.mos")
    assert argv[argv.index("--env") + 1] == f"HOME={om.HOME}"
    volumes = [argv[at + 1] for at, given in enumerate(argv) if given == "--volume"]
    assert volumes == [
        f"{folder.resolve() / 'home'}:{om.HOME}",
        f"{folder.resolve() / 'tigwerlib'}:/tigwerlib:ro",
        f"{work.resolve()}:/work",
    ]
    assert argv[argv.index("--workdir") + 1] == "/work"
    assert argv[-3:] == [om.IMAGE, "omc", "build.mos"]


def test_an_archive_is_refused_unless_its_sha256_is_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = om.ZenodoFile(1, "a b.zip", "0" * 32, hashlib.sha256(b"pinned").hexdigest())
    assert archive.url == "https://zenodo.org/api/records/1/files/a%20b.zip/content"
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"other"))
    with pytest.raises(om.PinRefused, match="sha256"):
        om._fetch(archive, tmp_path)
    assert not (tmp_path / archive.name).exists()

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"pinned"))
    assert om._fetch(archive, tmp_path).read_bytes() == b"pinned"

    # A copy that is there, as pinned, is not downloaded again.
    def offline(url: str, timeout: float) -> io.BytesIO:
        raise AssertionError(f"downloaded {url} again")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    assert om._fetch(archive, tmp_path).read_bytes() == b"pinned"


def test_a_library_is_refused_unless_installed_from_its_pinned_commit(tmp_path: Path) -> None:
    for library in om.LIBRARIES:
        installed = tmp_path / f"{library.name} {library.version}"
        installed.mkdir()
        (installed / "openmodelica.metadata.json").write_text(
            json.dumps({"sha": library.commit, "version": library.version})
        )
    om._verify_installed_libraries(tmp_path)

    moved = om.LIBRARIES[-1]
    metadata = tmp_path / f"{moved.name} {moved.version}" / "openmodelica.metadata.json"
    metadata.write_text(json.dumps({"sha": "0" * 40, "version": moved.version}))
    with pytest.raises(om.PinRefused, match=f"{moved.name} {moved.version} was installed from 0+,"):
        om._verify_installed_libraries(tmp_path)

    metadata.unlink()
    with pytest.raises(om.PinRefused, match=f"{moved.name} {moved.version} is not installed"):
        om._verify_installed_libraries(tmp_path)


class _Published(io.BytesIO):
    """A response from where a pin is published."""

    def __init__(self, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        super().__init__(body)
        self.headers = headers or {}


def _index() -> dict[str, Any]:
    """OpenModelica's package index as it offers the pinned libraries."""
    libs: dict[str, Any] = {}
    for library in om.LIBRARIES:
        libs.setdefault(library.name, {"versions": {}})["versions"][library.version] = {
            "sha": library.commit,
            "zipfile": f"https://github.com/archive/{library.commit}.zip",
        }
    return {"libs": libs}


def _record(archive: om.ZenodoFile, md5: str) -> dict[str, Any]:
    """A Zenodo record, as its API lists its files."""
    return {"files": [{"key": archive.name, "checksum": f"md5:{md5}"}]}


def test_the_pins_are_refused_unless_still_published_as_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = _index()
    records = {a.record: _record(a, a.md5) for a in (om.TIGWERLIB, om.SOURISSEAU_DATASET)}
    gone: set[str] = set()

    def urlopen(request: str | urllib.request.Request, timeout: float) -> _Published:
        url = request if isinstance(request, str) else request.full_url
        if any(url.startswith(prefix) for prefix in gone):
            raise urllib.error.HTTPError(url, 404, "Not Found", Message(), None)
        if url.startswith("https://auth.docker.io/"):
            return _Published(json.dumps({"token": "anonymous"}).encode())
        if url.startswith("https://registry-1.docker.io/"):
            return _Published(headers={"Docker-Content-Digest": om.IMAGE.partition("@")[2]})
        if url == om.PACKAGE_INDEX:
            return _Published(json.dumps(index).encode())
        if url.startswith(f"{om.ZENODO_RECORDS}/"):
            return _Published(json.dumps(records[int(url.rpartition("/")[2])]).encode())
        if url.startswith("https://github.com/archive/"):
            return _Published()
        raise AssertionError(f"asked for {url}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    om.verify_pins()

    # The image gone from Docker Hub; the ways it can be are the shared
    # module's to test.
    gone.add("https://registry-1.docker.io/")
    with pytest.raises(om.PinRefused, match=r"Docker Hub no longer serves .* \(404\)"):
        om.verify_pins()
    gone.clear()

    # An archive gone from its record, or listed with another checksum.
    dataset = om.SOURISSEAU_DATASET
    records[dataset.record] = {"files": []}
    with pytest.raises(om.PinRefused, match=f"no longer lists {re.escape(dataset.name)}"):
        om.verify_pins()
    records[dataset.record] = _record(dataset, "f" * 32)
    with pytest.raises(om.PinRefused, match=f"with md5:f+, not md5:{dataset.md5}"):
        om.verify_pins()
    gone.add(f"{om.ZENODO_RECORDS}/{dataset.record}")
    with pytest.raises(om.PinRefused, match=rf"no longer has record {dataset.record} \(404\)"):
        om.verify_pins()
    gone.clear()
    records[dataset.record] = _record(dataset, dataset.md5)

    # A library's version moved to another commit, as a maintenance branch can.
    moved = om.LIBRARIES[0]
    named = re.escape(f"{moved.name} {moved.version}")
    index["libs"][moved.name]["versions"][moved.version]["sha"] = "1" * 40
    with pytest.raises(om.PinRefused, match=f"offers {named} from 1+, not"):
        om.verify_pins()

    # A library's version no longer offered.
    del index["libs"][moved.name]["versions"][moved.version]
    with pytest.raises(om.PinRefused, match=f"no longer offers {named}"):
        om.verify_pins()

    # A commit's archive gone.
    index = _index()
    gone.add(f"https://github.com/archive/{om.LIBRARIES[-1].commit}.zip")
    with pytest.raises(om.PinRefused, match=r"is no longer there \(404\)"):
        om.verify_pins()


def test_a_check_fails_on_its_own_steps_not_on_what_an_earlier_one_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, work = tmp_path / "folder", tmp_path / "work"
    monkeypatch.setattr(om, "docker_running", lambda: True)

    def left_by_an_earlier_check() -> None:
        work.mkdir(exist_ok=True)
        (work / om.MODEL).write_text("built earlier")
        (work / f"{om.MODEL}_res.mat").write_text("simulated earlier")
        (work / "build.log").write_text("built earlier\n")
        (work / "simulate.log").write_text("The simulation finished successfully.\n")

    def ran(status: int) -> Callable[..., subprocess.CompletedProcess[bytes]]:
        return lambda argv, check: subprocess.CompletedProcess(argv, status)

    # The container does not start: Docker exits with 125 and writes nothing.
    left_by_an_earlier_check()
    monkeypatch.setattr(subprocess, "run", ran(125))
    with pytest.raises(om.CheckFailed, match="the build step exited with status 125: see Docker's"):
        om.check_global_model(folder, work)

    # The model built, and its simulation stopped before its end.
    left_by_an_earlier_check()

    def built(argv: list[str], check: bool) -> subprocess.CompletedProcess[bytes]:
        if "build.mos" in argv:
            (work / om.BUILT).write_text("built now")
        else:
            (work / "simulate.log").write_text("integration stopped\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", built)
    with pytest.raises(om.CheckFailed, match="not simulated to its end"):
        om.check_global_model(folder, work)

    # omc exits cleanly and builds nothing.
    left_by_an_earlier_check()
    monkeypatch.setattr(subprocess, "run", ran(0))
    with pytest.raises(om.CheckFailed, match="the model did not build"):
        om.check_global_model(folder, work)


def test_the_readme_names_every_pin() -> None:
    readme = README.read_text(encoding="utf-8")
    digest = om.IMAGE.partition("@")[2]
    archives = (om.TIGWERLIB, om.SOURISSEAU_DATASET)
    pins = [
        digest,
        *(archive.sha256 for archive in archives),
        *(archive.md5 for archive in archives),
        *(library.commit for library in om.LIBRARIES),
    ]
    assert [pin for pin in pins if pin not in readme] == []
