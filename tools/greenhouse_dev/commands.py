"""A command for each task, run from a clone as `uv run <command>`.

`uv run` installs Python 3.14 and the Python packages before it runs any of
them; `uv run setup` installs what it cannot: the viewer's packages,
Playwright's Chromium and the git hooks. Each command works from the
repository's root, whichever directory it is called from, with the
workspace's Python, and passes what follows its name on:
`uv run demo --no-browser`, `uv run check --fast`.

Each is a console script of the root `pyproject.toml`, under the name
`COMMANDS` gives it, and each script runs `main`, which finds the command
by the script's name.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "greenhouse_sim" / "web"
SCRIPTS = ROOT / "scripts"
# The Node the viewer's `.nvmrc` names (decision 0008).
NODE_NEEDED = int((WEB / ".nvmrc").read_text().strip())
# Where `uv run record-demo` finds the video Playwright recorded.
DEMO_VIDEOS = WEB / "test-results" / "demo"


class Unready(RuntimeError):
    """Something a command needs is missing; the message says what to do."""


def _environment(**extra: str) -> dict[str, str]:
    """This process's environment, with the workspace's tools first on the
    path, whether or not the command was started by `uv run`, and with
    `PYTHON` naming the workspace's Python for the viewer's browser tests,
    which serve the simulator from it."""
    tools = str(Path(sys.executable).parent)
    path = os.pathsep.join([tools, os.environ.get("PATH", "")])
    return dict(os.environ, PATH=path, PYTHON=sys.executable, **extra)


def _node() -> str:
    """npm's path, once Node is found at the version the viewer needs."""
    node, npm = shutil.which("node"), shutil.which("npm")
    if node is None or npm is None:
        raise Unready(
            f"Node {NODE_NEEDED} and npm are needed for the viewer: https://nodejs.org, "
            f"or `nvm install {NODE_NEEDED}`."
        )
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    major = int(version.lstrip("v").split(".")[0] or 0)
    if major < NODE_NEEDED:
        raise Unready(f"Node {NODE_NEEDED} or newer is needed for the viewer; this is {version}.")
    return npm


def _viewer() -> str:
    """npm's path, once the viewer's packages are installed."""
    npm = _node()
    if not (WEB / "node_modules").is_dir():
        raise Unready("The viewer's packages are not installed yet: uv run setup")
    return npm


def _run(command: Sequence[str], cwd: Path = ROOT) -> int:
    """Runs a step of a command that has several, and gives its exit code."""
    print(f"\n$ {' '.join(command)}", flush=True)
    return subprocess.run(list(command), cwd=cwd, env=_environment()).returncode


def _become(command: Sequence[str], cwd: Path = ROOT, env: Mapping[str, str] | None = None) -> int:
    """Replaces this process with `command`, so that Ctrl+C and the exit
    code are its own; returns only if it cannot start."""
    os.chdir(cwd)
    os.execvpe(command[0], list(command), dict(env or _environment()))


def _arguments() -> list[str]:
    return sys.argv[1:]


def _setup() -> int:
    npm = _node()
    steps: list[tuple[list[str], Path]] = [
        ([npm, "ci"], WEB),
        ([npm, "exec", "--", "playwright", "install", "chromium"], WEB),
    ]
    # The hooks are the repository's, shared by its worktrees, and run the
    # Python that installed them: installed from a worktree, they would stop
    # working once it is removed.
    if (ROOT / ".git").is_dir():
        hooks = ["--hook-type", "pre-commit", "--hook-type", "pre-push"]
        steps.append(([sys.executable, "-m", "pre_commit", "install", *hooks], ROOT))
    elif (ROOT / ".git").is_file():
        print("A worktree: the git hooks are the main checkout's, from its `uv run setup`.")
    for command, cwd in steps:
        code = _run(command, cwd)
        if code:
            return code
    print(
        "\nReady. `uv run demo` opens the reference greenhouse; `uv run help` lists the rest.\n"
        "On Linux, Chromium may ask for system libraries: "
        "`npx playwright install-deps chromium` in greenhouse_sim/web installs them (sudo).",
    )
    return 0


def _start() -> int:
    _viewer()
    return _become([sys.executable, str(SCRIPTS / "demo.py"), "--start-page", *_arguments()])


def _demo() -> int:
    _viewer()
    return _become([sys.executable, str(SCRIPTS / "demo.py"), *_arguments()])


def _record_demo() -> int:
    code = _run([_viewer(), "run", "demo:record", "--", *_arguments()], WEB)
    videos = sorted(DEMO_VIDEOS.rglob("*.webm"), key=lambda video: video.stat().st_mtime)
    if code == 0 and videos:
        print(f"\nThe video: {videos[-1]}")
    return code


def _api() -> int:
    return _become([sys.executable, "-m", "greenhouse_sim.api", *_arguments()])


def _viewer_server() -> int:
    return _become([_viewer(), "run", "dev", "--", *_arguments()], WEB)


def _check() -> int:
    return _become([sys.executable, str(SCRIPTS / "check.py"), *_arguments()])


def _viewer_checks() -> int:
    npm = _viewer()
    for script in ("lint", "typecheck", "coverage", "build"):
        code = _run([npm, "run", script], WEB)
        if code:
            return code
    return 0


def _browser_tests() -> int:
    return _become([_viewer(), "run", "e2e", "--", *_arguments()], WEB)


def _help() -> int:
    width = max(len(name) for name in COMMANDS)
    print("uv run <command> [arguments], from a clone of greenhouse-open:\n")
    for name, command in COMMANDS.items():
        print(f"  {name.ljust(width)}  {command.summary}")
    print("\nArguments after a command's name go to what it runs: uv run demo --help.")
    return 0


@dataclass(frozen=True)
class Command:
    run: Callable[[], int]
    summary: str


# Each command's name, as `uv run` takes it, in the order `uv run help`
# lists them.
COMMANDS: dict[str, Command] = {
    "help": Command(_help, "list these commands"),
    "setup": Command(
        _setup, "install what uv does not: the viewer's packages, Chromium and the git hooks"
    ),
    "demo": Command(_demo, "the simulator and its viewer, open on the reference greenhouse"),
    "start": Command(_start, "the simulator and its viewer, open on the viewer's start page"),
    "api": Command(_api, "the simulator's local API alone, on port 8765"),
    "viewer": Command(_viewer_server, "the viewer's development server alone, on port 5173"),
    "check": Command(_check, "the repository's Python checks, as CI runs them; --fast as a push"),
    "viewer-checks": Command(_viewer_checks, "the viewer's lint, type check, unit tests and build"),
    "browser-tests": Command(_browser_tests, "the viewer's browser tests, against the simulator"),
    "record-demo": Command(_record_demo, "record the demo's walk-through as a video"),
}


def main() -> None:
    """Runs the command a console script is named for, or, as
    `python -m greenhouse_dev.commands <command>`, the one named first."""
    name = Path(sys.argv[0]).stem
    if name not in COMMANDS:
        name, *rest = sys.argv[1:] or ["help"]
        sys.argv = [name, *rest]
    if name not in COMMANDS:
        print(f"No command {name!r}.", file=sys.stderr)
        _help()
        raise SystemExit(2)
    try:
        raise SystemExit(COMMANDS[name].run())
    except Unready as reason:
        print(reason, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
