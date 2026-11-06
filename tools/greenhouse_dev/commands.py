"""A command for each task, run from a clone as `uv run <command>`.

`uv run` installs Python 3.14 and the Python packages before it runs any of
them; `uv run setup` installs what it cannot: Node, when the machine's is
missing or too old, the viewer's packages, Playwright's Chromium and the git
hooks. Each command works from the
repository's root, whichever directory it is called from, with the
workspace's Python, and passes what follows its name on:
`uv run demo --no-browser`, `uv run check --fast`.

Each is a console script of the root `pyproject.toml`, under the name
`COMMANDS` gives it, and each script runs `main`, which finds the command
by the script's name.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from greenhouse_dev import demo_video

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "greenhouse_sim" / "web"
SCRIPTS = ROOT / "scripts"
# The Node the viewer's `.nvmrc` names (decision 0008).
NODE_NEEDED = int((WEB / ".nvmrc").read_text().strip())
# Node's releases, each with its version, from which `uv run setup` takes the
# latest of the version needed when it installs Node, and how long it waits.
NODE_RELEASES = "https://nodejs.org/dist/index.json"
NODE_RELEASES_TIMEOUT_S = 30
# Where `uv run record-demo` finds the video Playwright recorded.
DEMO_VIDEOS = WEB / "test-results" / "demo"
# The simulator's version, which the demo's video is named for.
SIMULATOR_PYPROJECT = ROOT / "greenhouse_sim" / "pyproject.toml"


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


def _which(name: str) -> str | None:
    """`name`'s path on the workspace's path, where the Node `uv run setup`
    installs comes before the machine's."""
    return shutil.which(name, path=_environment()["PATH"])


def _node_found() -> str:
    """The version of the Node the workspace's path has, such as `v24.11.0`,
    or "" when it has no Node and npm."""
    node = _which("node")
    if node is None or _which("npm") is None:
        return ""
    return subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()


def _node() -> str:
    """npm's path, once Node is found at the version the viewer needs."""
    version = _node_found()
    if not version:
        raise Unready(
            f"Node {NODE_NEEDED} and npm are needed for the viewer: "
            "`uv run setup` installs them in the workspace."
        )
    if int(version.lstrip("v").split(".")[0] or 0) < NODE_NEEDED:
        raise Unready(
            f"Node {NODE_NEEDED} or newer is needed for the viewer; the path's is {version}: "
            "`uv run setup` installs it in the workspace."
        )
    return str(_which("npm"))


def _latest_node(major: int) -> str:
    """The latest release of Node `major`, such as `24.11.0`. nodeenv would
    find it from `--node=24` itself, but nodeenv 1.11 stops at the first
    pre-release Node's list holds, such as `v27.0.0-alpha.0.0.0`."""
    try:
        with urllib.request.urlopen(NODE_RELEASES, timeout=NODE_RELEASES_TIMEOUT_S) as answer:
            releases = json.load(answer)
    except (OSError, ValueError) as failed:
        raise Unready(
            f"Node's releases could not be read from {NODE_RELEASES} ({failed}): install "
            f"Node {NODE_NEEDED} from https://nodejs.org, or run `uv run setup` again."
        ) from None
    release = re.compile(rf"v{major}\.(\d+)\.(\d+)")
    found = [
        (int(matched[1]), int(matched[2]))
        for entry in releases
        if (matched := release.fullmatch(str(entry.get("version", ""))))
    ]
    if not found:
        raise Unready(f"{NODE_RELEASES} lists no release of Node {major}.")
    minor, patch = max(found)
    return f"{major}.{minor}.{patch}"


def _install_node() -> int:
    """Installs the Node the viewer needs, the latest of its major version,
    into the workspace's environment (decision 0069): its `bin`, which
    `uv run` puts first on the path, for the workspace's commands alone."""
    version = _latest_node(NODE_NEEDED)
    print(
        f"Node {NODE_NEEDED} is not on the path ({_node_found() or 'no Node'}): installing "
        f"Node {version} in the workspace's environment, {sys.prefix}, for its commands alone."
    )
    return _run(
        [
            sys.executable,
            "-m",
            "nodeenv",
            f"--python-virtualenv={sys.prefix}",
            "--prebuilt",
            f"--node={version}",
        ]
    )


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
    """What follows the command's name, without a `--` before it: `uv run`
    passes `uv run browser-tests -- e2e/x.spec.ts` on as it is written, and
    the npm script each viewer command runs puts its own `--` first, so a
    second would reach the tool as an argument."""
    arguments = sys.argv[1:]
    return arguments[1:] if arguments[:1] == ["--"] else arguments


def _setup() -> int:
    try:
        npm = _node()
    except Unready:
        code = _install_node()
        if code:
            return code
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


# The demo's launcher checks Node, the viewer's packages and the ports
# itself, once it has read its arguments: `uv run demo --help` answers
# before the viewer is installed.
def _start() -> int:
    return _become([sys.executable, str(SCRIPTS / "demo.py"), "--start-page", *_arguments()])


def _demo() -> int:
    return _become([sys.executable, str(SCRIPTS / "demo.py"), *_arguments()])


def _ffmpeg() -> str:
    """ffmpeg's path: it cuts the demo's video (`greenhouse_dev.demo_video`)."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise Unready(
            "ffmpeg cuts the demo's video and is not on the path: `brew install ffmpeg`, "
            "`sudo apt install ffmpeg`, or https://ffmpeg.org/download.html."
        )
    return ffmpeg


def _record_demo() -> int:
    ffmpeg = _ffmpeg()
    code = _run([_viewer(), "run", "demo:record", "--", *_arguments()], WEB)
    videos = sorted(DEMO_VIDEOS.rglob("*.webm"), key=lambda video: video.stat().st_mtime)
    if code or not videos:
        return code or 1
    version = tomllib.loads(SIMULATOR_PYPROJECT.read_text())["project"]["version"]
    print(f"\nThe recording: {videos[-1]}")
    try:
        video, first_frame = demo_video.cut(ffmpeg, videos[-1], version)
    except demo_video.Uncut as failed:
        raise Unready(str(failed)) from None
    print(f"The video, cut for the README: {video}\nIts first frame, its preview: {first_frame}")
    return 0


def _api() -> int:
    return _become([sys.executable, "-m", "greenhouse_sim.api", *_arguments()])


def _viewer_server() -> int:
    return _become([_viewer(), "run", "dev", "--", *_arguments()], WEB)


def _check() -> int:
    return _become([sys.executable, str(SCRIPTS / "check.py"), *_arguments()])


def _release() -> int:
    return _become([sys.executable, str(SCRIPTS / "release.py"), *_arguments()])


def _viewer_checks() -> int:
    npm = _viewer()
    for script in ("lint", "typecheck", "coverage", "build"):
        code = _run([npm, "run", script], WEB)
        if code:
            return code
    return 0


# Playwright runs a project's dependencies whole, whatever files are named,
# and each stage of the browser tests depends on the one before
# (`playwright.config.ts`): a spec named runs alone only without them.
NO_DEPENDENCIES = "--no-deps"


def _browser_tests() -> int:
    arguments = _arguments()
    if any(argument.endswith(".spec.ts") for argument in arguments) and (
        NO_DEPENDENCIES not in arguments
    ):
        arguments = [NO_DEPENDENCIES, *arguments]
    return _become([_viewer(), "run", "e2e", "--", *arguments], WEB)


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
        _setup,
        "install what uv does not: Node if needed, the viewer's packages, Chromium, the git hooks",
    ),
    "demo": Command(_demo, "the simulator and its viewer, open on the reference greenhouse"),
    "start": Command(_start, "the simulator and its viewer, open on the viewer's start page"),
    "api": Command(_api, "the simulator's local API alone, on port 8765"),
    "viewer": Command(_viewer_server, "the viewer's development server alone, on port 5173"),
    "check": Command(_check, "the repository's Python checks, as CI runs them; --fast as a push"),
    "viewer-checks": Command(_viewer_checks, "the viewer's lint, type check, unit tests and build"),
    "browser-tests": Command(_browser_tests, "the viewer's browser tests, against the simulator"),
    "record-demo": Command(
        _record_demo, "record the demo's walk-through as a video, cut for the README"
    ),
    "release": Command(_release, "prepare a release's versions, changelog and README video"),
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
