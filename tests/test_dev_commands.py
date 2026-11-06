"""The repository's commands (decision 0039): each `uv run <command>` the
root pyproject declares runs one of `greenhouse_dev.commands.COMMANDS`, and
the documents quote no other."""

import io
import json
import re
import shutil
import sys
import tomllib
import urllib.error
import urllib.request
from collections.abc import Sequence
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


@pytest.fixture(autouse=True)
def started(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """What a command would have become: never the command itself, which
    would replace the test's process."""
    became: list[list[str]] = []
    monkeypatch.setattr(commands, "_become", lambda command, *a, **k: became.append(command))
    return became


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
    monkeypatch.setattr(shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/viewer"])

    with pytest.raises(SystemExit) as stopped:
        commands.main()

    assert stopped.value.code == 1
    assert capsys.readouterr().err.startswith(f"Node {commands.NODE_NEEDED} and npm are needed")


NPM = "/workspace/.venv/bin/npm"


class _Machine:
    """The Node a machine's path has, as `uv run setup` sees it, and what
    setup runs on it: installing Node puts the latest release on the path."""

    def __init__(self, node: str, installs: int = 0) -> None:
        self.node = node
        self.installs = installs
        self.ran: list[list[str]] = []

    def run(self, command: Sequence[str], *args: object, **kwargs: object) -> int:
        self.ran.append(list(command))
        if "nodeenv" in command:
            if self.installs:
                return self.installs
            self.node = f"v{commands.NODE_NEEDED}.22.2"
        return 0


@pytest.fixture
def machine(monkeypatch: pytest.MonkeyPatch) -> _Machine:
    machine = _Machine(node="")
    monkeypatch.setattr(commands, "_run", machine.run)
    monkeypatch.setattr(commands, "_node_found", lambda: machine.node)
    monkeypatch.setattr(commands, "_which", lambda name: f"/workspace/.venv/bin/{name}")
    monkeypatch.setattr(commands, "_latest_node", lambda major: f"{major}.22.2")
    return machine


@pytest.mark.parametrize("found", ["", f"v{commands.NODE_NEEDED - 2}.23.1"])
def test_setup_installs_node_in_the_workspace_when_the_path_has_none_or_an_older_one(
    machine: _Machine, found: str
) -> None:
    machine.node = found

    assert commands.COMMANDS["setup"].run() == 0

    install, *rest = machine.ran
    assert install == [
        sys.executable,
        "-m",
        "nodeenv",
        f"--python-virtualenv={sys.prefix}",
        "--prebuilt",
        f"--node={commands.NODE_NEEDED}.22.2",
    ]
    # The rest runs with the npm just installed.
    assert [command[:2] for command in rest[:2]] == [[NPM, "ci"], [NPM, "exec"]]


def test_setup_keeps_the_paths_node_when_it_is_the_one_needed(machine: _Machine) -> None:
    machine.node = f"v{commands.NODE_NEEDED + 1}.0.0"

    assert commands.COMMANDS["setup"].run() == 0

    assert [command[:2] for command in machine.ran[:2]] == [[NPM, "ci"], [NPM, "exec"]]


def test_setup_stops_when_node_cannot_be_installed(machine: _Machine) -> None:
    machine.node, machine.installs = f"v{commands.NODE_NEEDED - 2}.23.1", 3

    assert commands.COMMANDS["setup"].run() == 3

    assert [command[2] for command in machine.ran] == ["nodeenv"]


def _releases(monkeypatch: pytest.MonkeyPatch, versions: Sequence[str]) -> None:
    listed = json.dumps([{"version": version, "lts": False} for version in versions]).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: io.BytesIO(listed))


def test_the_latest_node_of_a_version_is_its_highest_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Node's list starts with a pre-release, which stops nodeenv 1.11, and
    # its patch numbers outgrow one digit.
    _releases(
        monkeypatch,
        ["v27.0.0-alpha.0.0.0", "v26.13.0", "v24.9.0", "v24.22.2", "v24.22.1", "v2.4.0"],
    )

    assert commands._latest_node(24) == "24.22.2"
    with pytest.raises(commands.Unready, match="lists no release of Node 25"):
        commands._latest_node(25)


def test_setup_says_what_to_do_when_nodes_releases_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreachable(url: str, timeout: float) -> io.BytesIO:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)

    with pytest.raises(commands.Unready, match=f"install Node {commands.NODE_NEEDED} from"):
        commands._latest_node(commands.NODE_NEEDED)


def test_the_demos_recording_says_it_needs_ffmpeg_before_it_records(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The cut needs ffmpeg once the walk-through has played, minutes later:
    # without it, nothing is recorded.
    found = shutil.which
    ran: list[Sequence[str]] = []

    def run(command: Sequence[str], *args: object, **kwargs: object) -> int:
        ran.append(command)
        return 0

    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, path=None: None if name == "ffmpeg" else found(name, path=path),
    )
    monkeypatch.setattr(commands, "_run", run)
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/record-demo"])

    with pytest.raises(SystemExit) as stopped:
        commands.main()

    assert stopped.value.code == 1
    assert capsys.readouterr().err.startswith("ffmpeg cuts the demo's video")
    assert ran == []


@pytest.mark.parametrize(
    ("given", "playwright_gets"),
    [
        # A spec named runs alone, with or without the `--` written before it.
        (["--", "e2e/camera.spec.ts"], ["--no-deps", "e2e/camera.spec.ts"]),
        (["e2e/camera.spec.ts", "--workers=1"], ["--no-deps", "e2e/camera.spec.ts", "--workers=1"]),
        (["--no-deps", "e2e/camera.spec.ts"], ["--no-deps", "e2e/camera.spec.ts"]),
        # No spec named: every stage, in order, as CI's lanes run them.
        ([], []),
        (["--", "--list"], ["--list"]),
    ],
)
def test_the_browser_tests_pass_on_what_they_are_given_and_run_a_spec_named_alone(
    monkeypatch: pytest.MonkeyPatch,
    started: list[list[str]],
    given: list[str],
    playwright_gets: list[str],
) -> None:
    monkeypatch.setattr(commands, "_viewer", lambda: "npm")
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/browser-tests", *given])

    with pytest.raises(SystemExit):
        commands.main()

    assert started == [["npm", "run", "e2e", "--", *playwright_gets]]


def test_a_command_takes_what_follows_a_dash_dash_as_its_arguments(
    monkeypatch: pytest.MonkeyPatch, started: list[list[str]]
) -> None:
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/demo", "--", "--no-browser"])

    with pytest.raises(SystemExit):
        commands.main()

    assert [command[1:] for command in started] == [
        [str(commands.SCRIPTS / "demo.py"), "--no-browser"]
    ]


def test_the_demos_help_needs_no_viewer(
    monkeypatch: pytest.MonkeyPatch, started: list[list[str]]
) -> None:
    # As `uv run help` suggests, on a clone with neither Node nor the
    # viewer's packages yet: the launcher reads `--help` before it checks
    # what it needs.
    monkeypatch.setattr(shutil, "which", lambda name, path=None: None)
    monkeypatch.setattr(sys, "argv", ["/workspace/.venv/bin/demo", "--help"])

    with pytest.raises(SystemExit):
        commands.main()

    assert [command[1:] for command in started] == [[str(commands.SCRIPTS / "demo.py"), "--help"]]


def test_the_guides_quote_only_commands_that_exist() -> None:
    quoted = {
        (guide, name) for guide in GUIDES for name in _UV_RUN.findall((ROOT / guide).read_text())
    }

    assert quoted
    assert sorted(q for q in quoted if q[1] not in {*commands.COMMANDS, *INSTALLED}) == []


def test_ci_installs_python_with_uv_from_the_lock() -> None:
    # pip would install whatever its index has today, not what uv.lock pins.
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    with_pip = [
        workflow.name
        for workflow in workflows
        for line in workflow.read_text().splitlines()
        if "pip install" in line and "uv pip install" not in line
    ]

    assert with_pip == []
    assert "uv sync --locked" in (ROOT / ".github" / "workflows" / "ci.yml").read_text()


def _path_filters(workflow: str) -> list[list[str]]:
    """Each `paths:` list among a workflow's triggers."""
    lines = workflow.splitlines()
    filters: list[list[str]] = []
    for at, line in enumerate(lines):
        if line.strip() != "paths:":
            continue
        entries: list[str] = []
        for item in lines[at + 1 :]:
            entry = item.strip()
            if entry.startswith("#"):
                continue
            if not entry.startswith("- "):
                break
            entries.append(entry.removeprefix("- ").strip('"'))
        filters.append(entries)
    return filters


def test_a_workflow_run_on_some_paths_runs_when_what_it_runs_on_changes() -> None:
    # What a workflow that syncs from the lock tests moves with the lock and
    # the Python, as the CFD results may.
    runs_on = {"uv.lock", ".python-version"}
    filtered = [
        (workflow.name, paths)
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        if "uv sync" in workflow.read_text()
        for paths in _path_filters(workflow.read_text())
    ]

    assert filtered
    assert [name for name, paths in filtered if not runs_on <= {*paths}] == []
