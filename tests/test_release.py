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

    with pytest.raises(Refused, match="no changelog entry since the last release"):
        release.prepare("0.4.0", DAY, root)
    with pytest.raises(Refused, match="no changelog entry since the last release"):
        release.prepare("0.4.0", DAY, root, [_merged(7, "CI only", "none")])


def _merged(number: int, title: str, entry: str | None, **fields: Any) -> release.Merged:
    """A pull request merged, its description giving `entry` under the
    changelog's section, or no such section if None."""
    body = "## What changed?\n\nSomething.\n"
    if entry is not None:
        body += (
            f"\n{release.CHANGELOG_SECTION}\n\n<!-- One or two sentences, or none. -->\n"
            f"{entry}\n\n## Verification\n\n- [x] Tests\n"
        )
    return release.Merged(number=number, title=title, body=body, **fields)


def test_prepare_takes_the_entries_the_pull_requests_merged_give(root: Path) -> None:
    """After those written under Unreleased, in the order merged, each
    ending with its number; none from one that needs none, from a bot's, or
    from one whose own diff wrote its entry in the changelog."""
    merged = [
        _merged(10, "A fan", "`greenhouse-sim`: a fan that turns."),
        _merged(11, "CI", "None."),
        _merged(12, "Bump", None, bot=True),
        _merged(13, "Written in the file", None, files=("CHANGELOG.md", "x.py")),
        _merged(
            14,
            "Two things",
            "- `greenhouse-protocol`: a record.\n  Its schema too.\n- the viewer: a panel.",
        ),
        _merged(15, "Long", "`greenhouse-sim`: a change\nsaid on two lines."),
    ]

    release.prepare("0.4.0", DAY, root, merged)

    section = (root / "CHANGELOG.md").read_text().split("## 0.4.0 - 2026-11-02\n\n", 1)[1]
    assert section.split("\n\n## 0.3.0", 1)[0] == (
        "- A heater that heats.\n"
        "- A vent that opens.\n"
        "- `greenhouse-sim`: a fan that turns. (#10)\n"
        "- `greenhouse-protocol`: a record.\n  Its schema too. (#14)\n"
        "- the viewer: a panel. (#14)\n"
        "- `greenhouse-sim`: a change\n  said on two lines. (#15)"
    )


def test_prepare_waits_for_every_pull_request_merged_to_give_an_entry_or_none(
    root: Path,
) -> None:
    before = {path: path.read_text() for path in root.rglob("*") if path.is_file()}
    merged = [
        _merged(20, "Given", "A thing."),
        _merged(21, "Silent", None),
        _merged(22, "Empty", ""),
    ]

    with pytest.raises(Refused, match="#21 Silent; #22 Empty"):
        release.prepare("0.4.0", DAY, root, merged)

    assert {path: path.read_text() for path in root.rglob("*") if path.is_file()} == before
    entries, missing = release.unreleased(root, merged)
    assert entries.endswith("- A thing. (#20)")
    assert missing == ["#21 Silent", "#22 Empty"]


def test_a_pull_request_merged_before_decision_0056_needs_no_section(root: Path) -> None:
    """Its entry, if it needed one, was written under Unreleased: only one
    merged from then on is waited for."""
    before = release.Merged.of(
        {
            "number": 30,
            "title": "Before",
            "body": "## What changed?\n\nSomething.\n",
            "author": {"is_bot": False},
            "mergedAt": "2026-10-24T21:07:48Z",
        }
    )
    merged = [before, _merged(31, "From then", None, merged_at=release.DESCRIPTIONS_FROM)]

    entries, missing = release.unreleased(root, merged)

    assert before.before_descriptions
    assert missing == ["#31 From then"]
    assert "#30" not in entries


@pytest.mark.parametrize(
    ("body", "entry"),
    [
        ("## Changelog\n\nA thing.\n\n## Review\n", "A thing."),
        ("## Changelog\r\n\r\n<!-- guidance -->\r\nnone\r\n", "none"),
        ("## Changelog\n<!-- guidance, unterminated", ""),
        ("## What changed?\n\nNo section.\n", None),
        ("## Changelogs\n\nNot the section.\n", None),
    ],
)
def test_a_pull_requests_entry_is_what_its_description_gives_under_its_section(
    body: str, entry: str | None
) -> None:
    assert release.changelog_entry(body) == entry


def test_a_pull_requests_last_section_ends_where_reviewable_appends_its_own() -> None:
    body = (
        "## Changelog\n\nnone\n\n<!-- Reviewable:start -->\n- - -\n"
        "This change is [<img src=x>](https://reviewable.io/reviews/o/r/1)\n"
        "<!-- Reviewable:end -->\n"
    )

    assert release.changelog_entry(body) == "none"


@pytest.mark.parametrize(
    ("entry", "none"),
    [
        ("none", True),
        ("None.", True),
        ("None: documentation only.", True),
        ("none (examples only)", True),
        ("none: docs only (a decision record and the roadmap).", True),
        ("None of the defaults change: a fan turns.", False),
        ("`greenhouse-sim`: a fan that turns.", False),
    ],
)
def test_none_is_given_alone_or_with_its_reason(entry: str, none: bool) -> None:
    assert release.gives_none(entry) is none


@pytest.mark.parametrize(
    ("body", "bot", "branch", "said"),
    [
        ("## Changelog\n\nA thing.\n", False, "feat/x", []),
        ("## Changelog\n\nnone\n", False, "ci/x", []),
        ("## What changed?\n", False, "feat/x", ["has no '## Changelog' section"]),
        ("## Changelog\n\n<!-- An entry, or none. -->\n", False, "feat/x", ["is empty"]),
        ("", True, "dependabot/pip/x", []),
        ("", False, "build/release-0.5.0", []),
    ],
)
def test_a_pull_requests_description_gives_its_entry_or_none(
    body: str, bot: bool, branch: str, said: list[str]
) -> None:
    found = release.description_problems(body, bot=bot, branch=branch)

    assert len(found) == len(said)
    assert all(part in problem for part, problem in zip(said, found, strict=True))


def test_check_description_reads_the_pull_request_from_ci(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PR_BODY", "## What changed?\n\nA thing.\n")
    monkeypatch.setenv("PR_IS_BOT", "false")
    monkeypatch.setenv("PR_BRANCH", "feat/x")
    assert release.main(["check-description"]) == 1
    assert "no '## Changelog' section" in capsys.readouterr().err

    monkeypatch.setenv("PR_BODY", "## Changelog\n\nnone\n")
    assert release.main(["check-description"]) == 0


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


def test_the_pull_requests_merged_since_the_last_release_are_those_after_its_tag(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Of those GitHub lists as merged since the tag's day: the ones whose
    merge commit is in the checkout's history and not in the tag's, in the
    order they were merged."""
    before = commit(repository, "merged before the release")
    git(repository, "tag", "v0.3.0")
    first = commit(repository, "merged after it")
    second = commit(repository, "merged after that")
    listed: list[dict[str, Any]] = [
        {"number": 3, "mergeCommit": {"oid": second}, "mergedAt": "2026-10-25T12:00:00Z"},
        {"number": 1, "mergeCommit": {"oid": before}, "mergedAt": "2026-10-24T09:00:00Z"},
        {"number": 2, "mergeCommit": {"oid": first}, "mergedAt": "2026-10-25T10:00:00Z"},
        {"number": 4, "mergeCommit": {"oid": "f" * 40}, "mergedAt": "2026-10-25T11:00:00Z"},
        {"number": 5, "mergeCommit": None, "mergedAt": "2026-10-25T13:00:00Z"},
    ]
    asked: list[tuple[str, ...]] = []

    def gh(*arguments: str) -> list[dict[str, Any]]:
        asked.append(arguments)
        return [
            {"title": f"#{pull['number']}", "body": "", "author": {"is_bot": False}, **pull}
            for pull in listed
        ]

    monkeypatch.setattr(release, "_gh", gh)

    assert [pull.number for pull in release.merged_since_release(repository)] == [2, 3]
    (arguments,) = asked
    assert "merged:>=" + git(repository, "show", "-s", "--format=%cs", "v0.3.0") in arguments
