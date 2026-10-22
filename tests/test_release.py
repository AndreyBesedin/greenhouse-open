"""A release's versions, changelog and README video (`scripts/release.py`,
decision 0045), on a copy of the files it edits, and on the repository's
own."""

import datetime
import re
from pathlib import Path

import pytest

from scripts import release
from scripts.release import Refused

OWNER = "owner"
DAY = datetime.date(2026, 11, 2)
VIDEO = "https://github.com/user-attachments/assets/0be8188e-db84-47b0-9fbe-fec118c530b8"
NEW_VIDEO = "https://github.com/user-attachments/assets/11111111-2222-4333-8444-555555555555"
CHANGELOG = """# Changelog

Intro.

## Unreleased

- A heater that heats.
- A vent that opens.

## 0.3.0 - 2026-10-21

What 0.3.0 holds.

- An entry of 0.3.0.

## 0.2.0 - 2026-10-19

- An entry of 0.2.0.
"""
README = f"""# greenhouse-open

## Demo

Greenhouse Open v0.2.0 — Greenhouse Simulation

{VIDEO}

## Why a shared format

Since v0.1.0, and https://github.com/user-attachments/assets/aaaaaaaa-0000 elsewhere.
"""


def pyproject(name: str, version: str, protocol: str | None) -> str:
    depends = f'    "greenhouse-protocol{protocol}",\n' if protocol else ""
    return (
        f'[project]\nname = "{name}"\nversion = "{version}"\ndependencies = [\n{depends}]\n\n'
        '[tool.ruff]\ntarget-version = "py314"\n'
    )


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """The files a release edits, at 0.3.0."""
    for package in release.PACKAGES:
        protocol = ">=0.3.0,<0.4" if package in release.PROTOCOL_DEPENDENTS else None
        (tmp_path / package).mkdir()
        (tmp_path / package / "pyproject.toml").write_text(
            pyproject(package.replace("_", "-"), "0.3.0", protocol)
        )
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    (tmp_path / "README.md").write_text(README)
    (tmp_path / ".github").mkdir()
    (tmp_path / release.RELEASE_MANAGERS).write_text("# Release managers.\n\nmanager\n")
    return tmp_path


def test_prepare_moves_the_packages_and_dates_the_unreleased_entries(root: Path) -> None:
    changed = release.prepare("0.4.0", DAY, root)

    assert release.current_version(root) == "0.4.0"
    for package in release.PROTOCOL_DEPENDENTS:
        assert (
            '"greenhouse-protocol>=0.4.0,<0.5"' in (root / package / "pyproject.toml").read_text()
        )
    changelog = (root / "CHANGELOG.md").read_text()
    assert changelog.startswith(
        "# Changelog\n\nIntro.\n\n## Unreleased\n\n## 0.4.0 - 2026-11-02\n\n"
        "- A heater that heats.\n- A vent that opens.\n\n## 0.3.0 - 2026-10-21\n"
    )
    assert changelog.endswith(CHANGELOG.split("## 0.3.0", 1)[1])
    assert set(changed) == {
        Path("CHANGELOG.md"),
        *(Path(package) / "pyproject.toml" for package in release.PACKAGES),
    }


@pytest.mark.parametrize("version", ["0.3.0", "0.2.9", "0.4", "v0.4.0"])
def test_prepare_refuses_a_version_that_does_not_follow(root: Path, version: str) -> None:
    with pytest.raises(Refused):
        release.prepare(version, DAY, root)

    assert release.current_version(root) == "0.3.0"


def test_prepare_refuses_when_nothing_is_unreleased(root: Path) -> None:
    changelog = root / "CHANGELOG.md"
    changelog.write_text(CHANGELOG.replace("- A heater that heats.\n- A vent that opens.\n\n", ""))

    with pytest.raises(Refused, match="Unreleased section is empty"):
        release.prepare("0.4.0", DAY, root)


def test_prepare_changes_nothing_when_a_package_is_behind(root: Path) -> None:
    behind = root / "greenhouse_adapters" / "pyproject.toml"
    behind.write_text(behind.read_text().replace('version = "0.3.0"', 'version = "0.2.0"'))
    before = (root / "CHANGELOG.md").read_text()

    with pytest.raises(Refused, match="do not share one version"):
        release.prepare("0.4.0", DAY, root)

    assert (root / "CHANGELOG.md").read_text() == before


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("0.4.0", '"greenhouse-protocol>=0.4.0,<0.5"'),
        ("0.4.2", '"greenhouse-protocol>=0.4.2,<0.5"'),
        ("1.2.3", '"greenhouse-protocol>=1.2.3,<2"'),
    ],
)
def test_the_protocol_range_ends_at_the_next_version_that_may_break_it(
    version: str, expected: str
) -> None:
    assert release.protocol_range(version) == expected


def test_the_readme_plays_the_new_video_captioned_with_the_version(root: Path) -> None:
    release.prepare("0.4.0", DAY, root)

    assert release.set_video(NEW_VIDEO, root) == "0.4.0"

    readme = (root / "README.md").read_text()
    assert "Greenhouse Open v0.4.0 — Greenhouse Simulation\n\n" + NEW_VIDEO + "\n" in readme
    assert VIDEO not in readme
    # Outside the demo's section, nothing moves.
    assert README.split("## Why", 1)[1] == readme.split("## Why", 1)[1]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video.mp4",
        "https://github.com/AndreyBesedin/greenhouse-open/releases/download/v0.3.0/demo.mp4",
        f"{NEW_VIDEO} ",
    ],
)
def test_the_readme_plays_only_a_video_uploaded_to_github(root: Path, url: str) -> None:
    with pytest.raises(Refused, match="not a video uploaded to GitHub"):
        release.set_video(url, root)

    assert (root / "README.md").read_text() == README


def test_the_notes_are_the_versions_changelog_section(root: Path) -> None:
    assert release.notes("0.3.0", root) == (
        f"{release.NOTES_INTRO}\n\nWhat 0.3.0 holds.\n\n- An entry of 0.3.0.\n"
    )
    assert release.notes("0.2.0", root).endswith("\n\n- An entry of 0.2.0.\n")
    with pytest.raises(Refused, match="no dated section for 0.4.0"):
        release.notes("0.4.0", root)


def released(root: Path) -> Path:
    release.prepare("0.4.0", DAY, root)
    return root


@pytest.mark.parametrize("author", [OWNER, "manager"])
def test_a_release_the_owner_merged_is_tagged(root: Path, author: str) -> None:
    found = release.problems(
        "build/release-0.4.0", author, OWNER, OWNER, ["v0.1.0", "v0.3.0"], released(root)
    )

    assert found == []


@pytest.mark.parametrize(
    ("branch", "author", "merged_by", "tags", "problem"),
    [
        ("build/release-0.4.0", OWNER, "manager", [], "only the repository's owner, owner"),
        ("build/release-0.4.0", "someone", OWNER, [], "opened by someone, who is neither"),
        ("build/release-0.3.9", OWNER, OWNER, [], "does not release 0.4.0"),
        ("build/release-0.4.0", OWNER, OWNER, ["v0.4.0"], "v0.4.0 is already tagged"),
        ("build/release-0.4.0", OWNER, OWNER, ["v0.5.0"], "does not follow 0.5.0"),
    ],
)
def test_a_release_is_not_tagged(
    root: Path, branch: str, author: str, merged_by: str, tags: list[str], problem: str
) -> None:
    found = release.problems(branch, author, merged_by, OWNER, tags, released(root))

    assert len(found) == 1 and problem in found[0]


def test_a_release_whose_protocol_range_was_left_behind_is_not_tagged(root: Path) -> None:
    released(root)
    behind = root / "greenhouse_sim" / "pyproject.toml"
    behind.write_text(behind.read_text().replace(">=0.4.0,<0.5", ">=0.3.0,<0.4"))

    found = release.problems("build/release-0.4.0", OWNER, OWNER, OWNER, [], root)

    assert found == [
        'greenhouse_sim does not depend on the protocol as "greenhouse-protocol>=0.4.0,<0.5"'
    ]


def test_verify_prints_the_version_for_the_workflow(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(release, "ROOT", released(root))
    monkeypatch.setattr(release, "_tags", lambda root: ["v0.1.0", "v0.3.0"])
    arguments = ["--branch", "build/release-0.4.0", "--author", OWNER, "--owner", OWNER]

    assert release.main(["verify", *arguments, "--merged-by", OWNER]) == 0
    assert capsys.readouterr().out == "version=0.4.0\n"
    assert release.main(["verify", *arguments, "--merged-by", "manager"]) == 1
    assert "only the repository's owner" in capsys.readouterr().err


def test_the_repositorys_packages_are_released_together() -> None:
    """The protocol range a release would be checked against holds now:
    0.2.0's release once left it at 0.1."""
    version = release.current_version()

    for package in release.PROTOCOL_DEPENDENTS:
        text = (release.ROOT / package / "pyproject.toml").read_text()
        assert release.protocol_range(version) in text
    assert release.notes(version).startswith(release.NOTES_INTRO)
    assert all(re.fullmatch(r"[A-Za-z0-9-]+", login) for login in release.release_managers())
