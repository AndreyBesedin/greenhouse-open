"""The command line ends a failure it knows, in the data or the network, in one
line and an exit code, not a traceback."""

from pathlib import Path

import httpx
import pytest

from greenhouse_adapters import cli
from greenhouse_adapters.manifests import ArtifactManifest, load_manifest
from greenhouse_adapters.profiles import PROFILES, Profile
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_adapters.wur.datasets import WUR_DATASETS

DATASET = "agc4-2023"


def _first_tiny_artifact(data_dir: Path) -> tuple[ArtifactManifest, Path]:
    """The first artifact `prepare --profile tiny` resolves, and where."""
    manifest = load_manifest(WUR_DATASETS[DATASET].id)
    kinds = PROFILES[Profile.TINY].artifact_kinds
    artifact = next(a for a in manifest.artifacts if a.kind in kinds)
    path = DataDirectory(data_dir).raw(manifest) / artifact.name
    path.parent.mkdir(parents=True)
    return artifact, path


def _prepare(data_dir: Path) -> int:
    return cli.main(["prepare", "wur", DATASET, "--profile", "tiny", "--data-dir", str(data_dir)])


def test_a_local_copy_that_fails_its_checksum_is_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, path = _first_tiny_artifact(tmp_path)
    path.write_bytes(b"not the artifact")

    assert _prepare(tmp_path) == 1
    out = capsys.readouterr().out
    assert "error" in out
    assert "delete it and re-fetch" in out


def test_an_artifact_that_is_not_an_archive_is_one_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact, path = _first_tiny_artifact(tmp_path)
    path.write_bytes(b"not a zip archive")
    # as the resolver records a verification, so that the build opens it
    status = path.stat()
    path.with_name(path.name + ".md5-verified").write_text(
        f"{artifact.md5} {status.st_size} {status.st_ino} {status.st_mtime_ns}\n"
    )

    assert _prepare(tmp_path) == 1
    assert capsys.readouterr().err.startswith("greenhouse-data: error: ")


def test_an_unreachable_provider_is_one_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unreachable(dataset_uuid: str) -> dict[str, object]:
        raise httpx.ConnectError("name or service not known")

    monkeypatch.setattr(cli, "fetch_dataset_metadata", unreachable)

    assert cli.main(["inventory", "wur", DATASET]) == 1
    assert capsys.readouterr().err == "greenhouse-data: error: name or service not known\n"


def test_a_failure_in_the_commands_own_code_keeps_its_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(dataset_uuid: str) -> dict[str, object]:
        raise AttributeError("a bug, not the data")

    monkeypatch.setattr(cli, "fetch_dataset_metadata", broken)

    with pytest.raises(AttributeError):
        cli.main(["inventory", "wur", DATASET])


def test_inventory_does_not_write_into_an_installed_package(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fetched(dataset_uuid: str) -> dict[str, object]:
        raise AssertionError("nothing is fetched for a write that is refused")

    monkeypatch.setattr(cli, "manifests_in_a_checkout", lambda: False)
    monkeypatch.setattr(cli, "fetch_dataset_metadata", fetched)

    assert cli.main(["inventory", "wur", DATASET, "--write"]) == 1
    error = capsys.readouterr().err
    assert error.startswith("greenhouse-data: error: --write updates the manifests of a source")
    assert error.count("\n") == 1
