"""A release's versions, changelog and README video (`scripts/release.py`,
decision 0045), on a copy of the files it edits, and on the repository's
own."""

import datetime
import os
import re
import subprocess
from pathlib import Path
from typing import Any

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


@pytest.mark.parametrize(
    "version", ["0.3.0", "0.2.9", "0.4", "v0.4.0", "00.4.0", "0.04.0", "0.\u0664.0"]
)
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
    with pytest.raises(Refused, match=r"no dated section for 0\.4\.0"):
        release.notes("0.4.0", root)


def released(root: Path) -> Path:
    release.prepare("0.4.0", DAY, root)
    return root


MERGE = "a" * 40
EARLIER = "b" * 40
TAGGED = {"v0.1.0": "c" * 40, "v0.3.0": EARLIER}


def pull(**change: Any) -> dict[str, Any]:
    """GitHub's answer for release pull request #7, merged by the owner."""
    answer = {
        "number": 7,
        "merged_at": "2026-11-02T10:00:00Z",
        "head": {"ref": "build/release-0.4.0"},
        "user": {"login": OWNER},
        "merged_by": {"login": OWNER},
        "merge_commit_sha": MERGE,
        "base": {"sha": EARLIER},
    }
    return answer | change


def merged(
    root: Path,
    tagged_by: str = OWNER,
    tags: dict[str, str] = TAGGED,
    **change: Any,
) -> list[str]:
    """Why release pull request #7, merged as 0.4.0's, would not be tagged."""
    merge = release.Merge.of(pull(**change))
    return release.problems(merge, OWNER, tagged_by, managers={"manager"}, tags=tags, root=root)


@pytest.mark.parametrize("author", [OWNER, "manager"])
def test_a_release_the_owner_merged_is_tagged(root: Path, author: str) -> None:
    assert merged(released(root), user={"login": author}) == []


def test_a_release_already_tagged_on_its_merge_is_checked_again(root: Path) -> None:
    # The workflow, after the owner's tag, or a run of either again.
    assert merged(released(root), tags={**TAGGED, "v0.4.0": MERGE}) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"merged_by": {"login": "manager"}}, "merged by manager: only the repository's owner"),
        ({"tagged_by": "manager"}, "tagged by manager: only the repository's owner"),
        ({"user": {"login": "someone"}}, "opened by someone, who is neither"),
        ({"head": {"ref": "build/release-0.3.9"}}, "does not release 0.4.0"),
        ({"tags": {**TAGGED, "v0.4.0": EARLIER}}, f"v0.4.0 is already tagged, on {EARLIER[:12]}"),
        ({"tags": {**TAGGED, "v0.5.0": EARLIER}}, "does not follow 0.5.0"),
    ],
)
def test_a_release_is_not_tagged(root: Path, change: dict[str, Any], problem: str) -> None:
    found = merged(released(root), **change)

    assert len(found) == 1 and problem in found[0]


def test_a_pull_request_not_merged_is_not_released() -> None:
    with pytest.raises(Refused, match="#7 is not merged"):
        release.Merge.of(pull(merged_at=None, merged_by=None))


def test_a_release_whose_protocol_range_was_left_behind_is_not_tagged(root: Path) -> None:
    released(root)
    behind = root / "greenhouse_sim" / "pyproject.toml"
    behind.write_text(behind.read_text().replace(">=0.4.0,<0.5", ">=0.3.0,<0.4"))

    assert merged(root) == [
        'greenhouse_sim does not depend on the protocol as "greenhouse-protocol>=0.4.0,<0.5"'
    ]


def test_a_release_with_entries_left_under_unreleased_is_not_tagged(root: Path) -> None:
    # Merged in after the release was prepared: its notes would leave it out.
    changelog = released(root) / "CHANGELOG.md"
    late = "## Unreleased\n\n- A change merged since.\n"
    changelog.write_text(changelog.read_text().replace("## Unreleased\n", late, 1))

    assert merged(root) == ["CHANGELOG.md's Unreleased entries would be left out of the notes"]


def git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments), cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository of its own. A git hook runs with `GIT_DIR` and its kin
    set to the repository it runs in, which would carry these commands
    there (tests/test_pr_risk.py)."""
    for name in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(name)
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "config", "user.email", "t@example.com")
    return tmp_path


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def test_the_managers_are_read_as_listed_before_the_release(repository: Path) -> None:
    before_any = commit(repository, "no list yet")
    listed = repository / release.RELEASE_MANAGERS
    listed.parent.mkdir()
    listed.write_text("# Release managers.\nmanager\n")
    base = commit(repository, "a manager")
    # The release pull request adds its own author: not a manager by it.
    listed.write_text("# Release managers.\nmanager\nsomeone\n")
    commit(repository, "build: release 0.4.0")

    assert release.managers_at(base, repository) == {"manager"}
    assert release.managers_at("HEAD", repository) == {"manager", "someone"}
    assert release.managers_at(before_any, repository) == set()


def test_the_tags_are_read_with_the_commits_they_tag(repository: Path) -> None:
    first = commit(repository, "first")
    git(repository, "tag", "--annotate", "v0.1.0", "--message", "0.1.0")
    second = commit(repository, "second")
    git(repository, "tag", "v0.2.0")
    git(repository, "tag", "other")

    assert release._tags(repository) == {"v0.1.0": first, "v0.2.0": second}


def answering(answers: dict[str, Any]) -> Any:
    """`release._gh`, answering each `gh` call from `answers`."""

    def gh(*arguments: str) -> Any:
        return answers[" ".join(arguments)]

    return gh


def test_verify_prints_the_version_of_the_tag_pushed(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(release, "ROOT", released(root))
    monkeypatch.setattr(release, "_head", lambda root: MERGE)
    monkeypatch.setattr(release, "_tags", lambda root: {**TAGGED, "v0.4.0": MERGE})
    monkeypatch.setattr(release, "managers_at", lambda revision, root: set())
    pulls = f"api repos/{{owner}}/{{repo}}/commits/{MERGE}/pulls"
    monkeypatch.setattr(
        release,
        "_gh",
        answering(
            {
                pulls: [{"number": 6, "merge_commit_sha": EARLIER}, pull()],
                "api repos/{owner}/{repo}/pulls/7": pull(),
            }
        ),
    )
    verify = ["verify", "--owner", OWNER, "--tagged-by", OWNER]

    assert release.main([*verify, "--tag", "v0.4.0"]) == 0
    assert capsys.readouterr().out == "version=0.4.0\n"
    assert release.main([*verify, "--tag", "v0.4.1"]) == 1
    assert "tag v0.4.1 does not name 0.4.0" in capsys.readouterr().err


@pytest.fixture
def merged_release(
    root: Path, repository: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Release pull request #7 merged in a repository of its own, which
    pushes to a bare `origin`; its base lists the managers."""
    base = commit(repository, "the managers")
    released(repository)
    merge = commit(repository, "Merge pull request #7")
    origin = repository.with_name(f"{repository.name}-origin")
    git(repository, "init", "-q", "--bare", str(origin))
    git(repository, "remote", "add", "origin", str(origin))
    git(repository, "push", "-q", "origin", "main")
    monkeypatch.setattr(release, "ROOT", repository)
    answer = pull(merge_commit_sha=merge, base={"sha": base})
    monkeypatch.setattr(
        release,
        "_gh",
        answering(
            {
                "api repos/{owner}/{repo}/pulls/7": answer,
                "api repos/{owner}/{repo}": {"owner": {"login": OWNER}},
                "api user": {"login": OWNER},
            }
        ),
    )
    return repository, origin


def test_the_owner_tags_the_merge_and_pushes_the_tag(merged_release: tuple[Path, Path]) -> None:
    repository, origin = merged_release

    assert release.main(["tag", "7"]) == 0

    merge = git(repository, "rev-parse", "HEAD")
    assert git(origin, "rev-parse", "v0.4.0^{commit}") == merge
    assert git(origin, "cat-file", "-t", "v0.4.0") == "tag"
    # Once tagged, the same command again changes nothing.
    assert release.main(["tag", "7"]) == 0
    assert git(origin, "rev-parse", "v0.4.0^{commit}") == merge


def test_a_release_manager_does_not_tag(
    merged_release: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, origin = merged_release
    answers = release._gh
    monkeypatch.setattr(
        release, "_gh", lambda *a: {"login": "manager"} if a == ("api", "user") else answers(*a)
    )

    assert release.main(["tag", "7"]) == 1

    assert "tagged by manager: only the repository's owner" in capsys.readouterr().err
    assert git(origin, "tag", "--list") == ""


def test_a_release_is_tagged_only_from_its_merge(
    merged_release: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    repository, origin = merged_release
    git(repository, "switch", "-q", "--detach", "HEAD~1")

    assert release.main(["tag", "7"]) == 1

    assert "check out #7's merge first" in capsys.readouterr().err
    assert git(origin, "tag", "--list") == ""


def test_the_repositorys_packages_are_released_together() -> None:
    """The protocol range a release would be checked against holds now:
    0.2.0's release once left it at 0.1."""
    version = release.current_version()

    for package in release.PROTOCOL_DEPENDENTS:
        text = (release.ROOT / package / "pyproject.toml").read_text()
        assert release.protocol_range(version) in text
    assert release.notes(version).startswith(release.NOTES_INTRO)
    listed = release.release_managers((release.ROOT / release.RELEASE_MANAGERS).read_text())
    assert all(re.fullmatch(r"[A-Za-z0-9-]+", login) for login in listed)
