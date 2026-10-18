"""Run the repository's canonical Python checks.

Keep local development and CI on the same command so that a green local run
means something. The fast mode excludes tests explicitly marked slow and is
suitable for pre-push use.
"""

from __future__ import annotations

import argparse
import subprocess
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip tests marked slow; intended for the pre-push hook",
    )
    parser.add_argument(
        "--only",
        choices=PARTS,
        help="check one package, or the cross-package checks (root), as a CI job does",
    )
    args = parser.parse_args()

    for part in [args.only] if args.only else PARTS:
        _check(PARTS[part], fast=args.fast)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
