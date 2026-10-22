"""Run the repository's canonical Python checks.

Keep local development and CI on the same command so that a green local run
means something. The fast mode excludes tests explicitly marked slow and is
suitable for pre-push use.

A change to documentation alone needs only the root's checks, which hold the
documents to their citations and publishability; `--changed` and `--pushed`
check what a change needs, and `--plan` says it for CI's jobs. The standard
library only: CI plans with the runner's own Python.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")
# What `--only` names: a package, or the cross-package checks at the root.
# CI runs each in a job of its own, at once.
PARTS = {"protocol": PACKAGES[0], "sim": PACKAGES[1], "adapters": PACKAGES[2], "root": "."}
# The simulator's tests run in a process per core (pytest-xdist), each file
# in one of them, so that a file's fixtures and the runs its tests share
# are worked out once. The other packages' tests take seconds.
PARALLEL = {"greenhouse_sim": ("-n", "auto", "--dist", "loadfile")}
# What documentation is: no package's tests, nor the viewer's or the
# browser's, read it. `fnmatch`'s `*` crosses directories, so `*.md` is
# every Markdown file, a package's README included.
DOCUMENTATION = ("*.md", "docs/*", "LICENSE", "NOTICE")


def is_documentation(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in DOCUMENTATION)


def parts_for(paths: Sequence[str] | None) -> list[str]:
    """The parts a change to these paths needs: the root's alone for
    documentation, every part otherwise, and when the paths are not known."""
    if paths and all(is_documentation(path) for path in paths):
        return ["root"]
    return list(PARTS)


def changed_paths(base: str, head: str) -> list[str] | None:
    """The paths changed from where `head`'s history left `base`'s to `head`,
    or None when git cannot tell. A rename is its two paths, so that code
    moved under `docs/` is not documentation alone."""
    result = subprocess.run(
        ("git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return [path for path in result.stdout.split("\0") if path]


def pushed_paths() -> list[str] | None:
    """The paths the commits being pushed change, as pre-commit names them
    to a pre-push hook; None when it names none, as for a new branch's first
    commit or a run by hand."""
    base = os.environ.get("PRE_COMMIT_FROM_REF")
    head = os.environ.get("PRE_COMMIT_TO_REF")
    if not base or not head:
        return None
    return changed_paths(base, head)


def _run(*command: str, cwd: Path = ROOT) -> None:
    print(f"\n$ {' '.join(command)}  # {cwd.relative_to(ROOT) or '.'}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _pytest_args(*, fast: bool, package: str = ".") -> tuple[str, ...]:
    command = ("pytest", "-q", *PARALLEL.get(package, ()))
    if fast:
        return (*command, "-m", "not slow")
    return command


def _check(directory: str, *, fast: bool) -> None:
    """Lint, type-check and test a package's directory, or the root's
    cross-package tests, examples, scripts and commands (`.`)."""
    if directory == ".":
        _run("ruff", "check", "tests", "examples", "scripts", "tools")
        _run("ruff", "format", "--check", "tests", "examples", "scripts", "tools")
        _run("mypy")
        _run(*_pytest_args(fast=fast))
        return
    package_dir = ROOT / directory
    _run("ruff", "check", ".", cwd=package_dir)
    _run("ruff", "format", "--check", ".", cwd=package_dir)
    _run("mypy", cwd=package_dir)
    _run(*_pytest_args(fast=fast, package=directory), cwd=package_dir)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip tests marked slow; intended for the pre-push hook",
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--only",
        choices=PARTS,
        help="check one package, or the cross-package checks (root), as a CI job does",
    )
    scope.add_argument(
        "--changed",
        nargs=2,
        metavar=("BASE", "HEAD"),
        help="check what the change from BASE to HEAD needs: the root alone for documentation",
    )
    scope.add_argument(
        "--pushed",
        action="store_true",
        help="check what the commits being pushed need, as pre-commit names them",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="print the parts to check, as GitHub step outputs, and check nothing",
    )
    args = parser.parse_args(arguments)

    if args.only:
        parts = [args.only]
    elif args.changed:
        parts = parts_for(changed_paths(*args.changed))
    elif args.pushed:
        parts = parts_for(pushed_paths())
    else:
        parts = list(PARTS)
    documentation_only = args.only is None and parts == ["root"]
    if args.plan:
        print(f"parts={json.dumps(parts)}")
        print(f"documentation_only={json.dumps(documentation_only)}")
        return 0
    if documentation_only:
        print("Documentation only: the root's checks alone.", flush=True)
    for part in parts:
        _check(PARTS[part], fast=args.fast)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
