import re
import subprocess
from pathlib import Path

from scripts.dependabot_auto_merge import DEPENDABOT, MINOR, PATCH, main, major, reasons_to_wait

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".github" / "dependabot.yml"
VIEWER = ["greenhouse_sim/web/package.json", "greenhouse_sim/web/package-lock.json"]
MAJOR = "version-update:semver-major"


def update(name: str, kind: str, before: str, after: str, **more: object) -> dict[str, object]:
    return {
        "dependencyName": name,
        "updateType": kind,
        "prevVersion": before,
        "newVersion": after,
        "maintainerChanges": False,
        **more,
    }


def test_a_minor_update_of_the_viewer_merges_by_itself() -> None:
    assert reasons_to_wait(DEPENDABOT, [update("vite", MINOR, "8.3.2", "8.4.0")], VIEWER) == []


def test_a_group_of_minor_and_patch_updates_merges_by_itself() -> None:
    group = [
        update("vitest", MINOR, "5.0.3", "5.1.0"),
        update("@vitest/coverage-v8", MINOR, "5.0.3", "5.1.0"),
        update("react", PATCH, "19.3.0", "19.3.1"),
    ]
    assert reasons_to_wait(DEPENDABOT, group, VIEWER) == []


def test_a_patch_update_below_1_0_merges_by_itself() -> None:
    assert reasons_to_wait(DEPENDABOT, [update("three", PATCH, "0.186.1", "0.186.2")], VIEWER) == []


def test_a_minor_update_below_1_0_waits() -> None:
    reasons = reasons_to_wait(DEPENDABOT, [update("three", MINOR, "0.186.1", "0.187.0")], VIEWER)
    assert reasons == ["three 0.186.1 to 0.187.0: a minor update below 1.0"]


def test_a_minor_update_from_an_unknown_version_waits() -> None:
    reasons = reasons_to_wait(DEPENDABOT, [update("vite", MINOR, "", "8.4.0")], VIEWER)
    assert reasons == ["vite ? to 8.4.0: a minor update below 1.0"]


def test_a_major_update_waits_and_holds_its_group() -> None:
    group = [
        update("react", PATCH, "19.3.0", "19.3.1"),
        update("vite", MAJOR, "8.3.2", "9.0.0"),
    ]
    assert reasons_to_wait(DEPENDABOT, group, VIEWER) == [f"vite 8.3.2 to 9.0.0: {MAJOR}"]


def test_an_update_of_unknown_type_waits() -> None:
    reasons = reasons_to_wait(DEPENDABOT, [update("vite", "", "8.3.2", "8.4.0")], VIEWER)
    assert reasons == ["vite 8.3.2 to 8.4.0: an update of unknown type"]


def test_no_update_reported_waits() -> None:
    """fetch-metadata reports nothing when a commit is not Dependabot's."""
    assert reasons_to_wait(DEPENDABOT, [], VIEWER) == [
        "no update reported: a commit that is not Dependabot's, or no metadata"
    ]


def test_a_push_by_anyone_else_waits() -> None:
    reasons = reasons_to_wait("someone", [update("vite", MINOR, "8.3.2", "8.4.0")], VIEWER)
    assert reasons == ["last pushed by someone, not by Dependabot"]


def test_changed_maintainers_wait() -> None:
    changed = update("vite", PATCH, "8.3.2", "8.3.3", maintainerChanges=True)
    assert reasons_to_wait(DEPENDABOT, [changed], VIEWER) == ["vite: its maintainers changed"]


def test_a_change_beyond_manifests_and_lockfiles_waits() -> None:
    files = [*VIEWER, "greenhouse_sim/web/src/main.tsx", ".github/workflows/ci.yml"]
    reasons = reasons_to_wait(DEPENDABOT, [update("vite", MINOR, "8.3.2", "8.4.0")], files)
    assert reasons == [
        "changes more than manifests and lockfiles: "
        ".github/workflows/ci.yml, greenhouse_sim/web/src/main.tsx"
    ]


def test_every_manifest_kind_counts_as_one() -> None:
    files = [
        *VIEWER,
        "requirements-dev.txt",
        "greenhouse_sim/pyproject.toml",
        ".pre-commit-config.yaml",
    ]
    assert reasons_to_wait(DEPENDABOT, [update("pytest", PATCH, "9.1.1", "9.1.2")], files) == []


def test_a_version_s_major() -> None:
    assert major("v4.2.0") == 4
    assert major("0.186.1") == 0
    assert major("3.1.5.20260827") == 3
    assert major("") is None
    assert major("latest") is None


def test_the_command_answers_by_its_exit_code(tmp_path: Path) -> None:
    files = tmp_path / "files.txt"
    files.write_text("\n".join(VIEWER) + "\n")
    vite = '[{"dependencyName": "vite", "updateType": "%s", "prevVersion": "8.3.2"}]'

    def answer(dependencies: str) -> int:
        return main(["--actor", DEPENDABOT, "--dependencies", dependencies, "--files", str(files)])

    assert answer(vite % MINOR) == 0
    assert answer(vite % MAJOR) == 1
    assert answer("") == 1


def _watched() -> set[str]:
    """The directories `.github/dependabot.yml` names, read as text: the
    repository's checks have no YAML parser of their own."""
    text = CONFIG.read_text()
    return set(re.findall(r"(?:directory: |[\[,] ?)(/[\w/.-]*)", text))


def test_every_manifest_is_watched() -> None:
    """A new package or viewer must take an entry in the configuration, or
    its dependencies are never updated."""
    tracked = subprocess.run(
        ["git", "ls-files", "*package.json", "*pyproject.toml", "*requirements*.txt"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    directories = {"/" + str(Path(path).parent).removeprefix(".") for path in tracked}
    directories = {directory.rstrip("/") or "/" for directory in directories}
    assert directories - _watched() == set()


def test_every_watched_directory_exists() -> None:
    missing = sorted(d for d in _watched() if not (ROOT / d.lstrip("/")).is_dir())
    assert not missing, f"directories Dependabot watches that no longer exist: {missing}"
