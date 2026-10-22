"""What `scripts/check.py` checks for a change: the root's part alone for
documentation, every part otherwise (docs/engineering.md)."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from scripts import check

ROOT = Path(__file__).resolve().parents[1]
EVERY_PART = list(check.PARTS)
# The documents' folder, spelled so that the publishable test does not take
# these tests' paths, in repositories of their own, for citations.
DOCS = "docs"


def test_documentation_alone_needs_the_root_part() -> None:
    paths = [
        "README.md",
        "docs/engineering.md",
        f"{DOCS}/roadmap/diagram.png",
        "greenhouse_sim/web/README.md",
        ".github/pull_request_template.md",
        "LICENSE",
        "NOTICE",
    ]

    assert check.parts_for(paths) == ["root"]


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        "greenhouse_sim/greenhouse_sim/api/routes.py",
        "greenhouse_sim/web/src/App.tsx",
        "greenhouse_sim/docs/notes.txt",
        "docs.py",
        "uv.lock",
    ],
)
def test_anything_else_needs_every_part(path: str) -> None:
    assert check.parts_for(["README.md", path]) == EVERY_PART


def test_a_change_not_known_needs_every_part() -> None:
    assert check.parts_for(None) == EVERY_PART
    assert check.parts_for([]) == EVERY_PART


def _repository(path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A new repository, which `check` reads changes from. A git hook runs
    with `GIT_DIR` and its kin set to its own repository, and pre-commit's
    pre-push hook names the refs it pushes: neither may reach these tests."""
    for name in [name for name in os.environ if name.startswith(("GIT_", "PRE_COMMIT_"))]:
        monkeypatch.delenv(name)
    path.mkdir()
    subprocess.run(("git", "init", "-q", "-b", "main"), cwd=path, check=True)
    monkeypatch.setattr(check, "ROOT", path)
    return path


def _commit(repo: Path) -> str:
    subprocess.run(("git", "add", "-A"), cwd=repo, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.org",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "change",
        ),
        cwd=repo,
        check=True,
    )
    return subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _plan(capsys: pytest.CaptureFixture[str], *arguments: str) -> dict[str, object]:
    assert check.main(["--plan", *arguments]) == 0
    lines = capsys.readouterr().out.splitlines()
    return {name: json.loads(value) for name, value in (line.split("=", 1) for line in lines)}


def test_a_change_to_documentation_is_planned_as_the_root_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repository(tmp_path / "repo", monkeypatch)
    (repo / "tool.py").write_text("x = 1\n")
    (repo / "README.md").write_text("# A tool\n")
    base = _commit(repo)
    (repo / "README.md").write_text("# A tool, described\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide with spaces.md").write_text("How to use it.\n")
    head = _commit(repo)

    assert check.changed_paths(base, head) == ["README.md", f"{DOCS}/guide with spaces.md"]
    assert _plan(capsys, "--changed", base, head) == {
        "parts": ["root"],
        "documentation_only": True,
    }


def test_code_moved_under_docs_is_not_documentation_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repository(tmp_path / "repo", monkeypatch)
    (repo / "tool.py").write_text("def tool() -> int:\n    return 1\n" * 20)
    base = _commit(repo)
    (repo / "docs").mkdir()
    subprocess.run(("git", "mv", "tool.py", f"{DOCS}/tool.py"), cwd=repo, check=True)
    head = _commit(repo)

    assert sorted(check.changed_paths(base, head) or []) == [f"{DOCS}/tool.py", "tool.py"]
    assert _plan(capsys, "--changed", base, head)["parts"] == EVERY_PART


def test_a_change_git_cannot_name_is_checked_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repository(tmp_path / "repo", monkeypatch)
    (repo / "README.md").write_text("# A tool\n")
    head = _commit(repo)

    assert check.changed_paths("no-such-commit", head) is None
    assert _plan(capsys, "--changed", "no-such-commit", head) == {
        "parts": EVERY_PART,
        "documentation_only": False,
    }


def test_a_push_is_planned_from_the_refs_pre_commit_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repository(tmp_path / "repo", monkeypatch)
    (repo / "tool.py").write_text("x = 1\n")
    base = _commit(repo)
    (repo / "CHANGELOG.md").write_text("## Unreleased\n")
    head = _commit(repo)

    # A new branch's first commit, or a run by hand: no refs named.
    assert _plan(capsys, "--pushed")["parts"] == EVERY_PART

    monkeypatch.setenv("PRE_COMMIT_FROM_REF", base)
    monkeypatch.setenv("PRE_COMMIT_TO_REF", head)
    assert _plan(capsys, "--pushed")["parts"] == ["root"]


def test_ci_checks_every_part_when_its_plan_is_missing() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    fallback = re.search(r"fromJSON\(needs\.changes\.outputs\.parts \|\| '(\[[^']*\])'\)", workflow)

    assert fallback, "ci.yml's repository checks name no parts for a missing plan"
    assert json.loads(fallback.group(1)) == EVERY_PART
