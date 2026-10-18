"""The repository's commands (decision 0039): each `uv run <command>` the
root pyproject declares runs one of `greenhouse_dev.commands.COMMANDS`, and
the documents quote no other."""

import re
import shutil
import sys
import tomllib
from pathlib import Path

import pytest
from greenhouse_dev import commands

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
# Where a newcomer reads the commands.
GUIDES = (
    "README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "docs/demo.md",
    "docs/engineering.md",
    "greenhouse_sim/README.md",
    "greenhouse_sim/web/README.md",
)
# What else `uv run` runs from the workspace's environment.
INSTALLED = {"python", "greenhouse-data", "pre-commit", "pytest"}
_UV_RUN = re.compile(r"\buv run ([a-z][a-z0-9-]*)")


def test_every_command_is_a_script_of_the_workspace_and_every_script_a_command() -> None:
    scripts = PYPROJECT["project"]["scripts"]

    assert sorted(scripts) == sorted(commands.COMMANDS)
    assert set(scripts.values()) == {"greenhouse_dev.commands:main"}


def test_help_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    commands.COMMANDS["help"].run()

    listed = capsys.readouterr().out
    assert all(f"  {name} " in listed for name in commands.COMMANDS)


def test_a_script_runs_the_command_it_is_named_for(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/help"])

    with pytest.raises(SystemExit) as stopped:
        commands.main()

    assert stopped.value.code == 0
    assert "record-demo" in capsys.readouterr().out


def test_a_command_that_cannot_run_yet_says_what_to_do(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # No Node on the path: the viewer's commands say how to get it, in a
    # line, rather than in a traceback.
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/demo"])

    with pytest.raises(SystemExit) as stopped:
        commands.main()

    assert stopped.value.code == 1
    assert capsys.readouterr().err.startswith(f"Node {commands.NODE_NEEDED} and npm are needed")


def test_the_guides_quote_only_commands_that_exist() -> None:
    quoted = {
        (guide, name) for guide in GUIDES for name in _UV_RUN.findall((ROOT / guide).read_text())
    }

    assert quoted
    assert sorted(q for q in quoted if q[1] not in {*commands.COMMANDS, *INSTALLED}) == []


def test_ci_installs_the_tools_the_workspace_pins() -> None:
    # CI installs requirements-dev.txt with pip until it moves to uv; uv is
    # pinned there for CI's lowest-dependencies job alone.
    pinned = {
        line.strip()
        for line in (ROOT / "requirements-dev.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("uv==")
    }

    assert pinned == set(PYPROJECT["dependency-groups"]["dev"])
