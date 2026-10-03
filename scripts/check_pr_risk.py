"""Gate higher-risk pull requests on an explicit manual self-review.

The repository is currently maintained by one developer, so GitHub's normal
"required human approval" mechanism is not useful: a pull request author
cannot approve their own pull request. This check keeps the fast path fast and
adds deliberate friction only when a diff crosses clear risk boundaries.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOTS = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")
MANUAL_REVIEW_MARKER = "- [x] I manually reviewed the complete diff"

CODE_SUFFIXES = {
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".sh",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".html",
}
GENERATED_OR_LOCK_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
}

SENSITIVE_FILES = {
    ".pre-commit-config.yaml",
    "requirements-dev.txt",
    "tests/test_dependencies.py",
    "tests/test_publishable.py",
    "greenhouse_sim/greenhouse_sim/core/engine.py",
    "greenhouse_sim/greenhouse_sim/ground_truth.py",
    "greenhouse_sim/greenhouse_sim/observations.py",
    "greenhouse_sim/greenhouse_sim/core/rng.py",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _changed_files(base: str, head: str) -> list[str]:
    output = _git("diff", "--name-only", f"{base}...{head}")
    return [line for line in output.splitlines() if line]


def _changed_code_lines(base: str, head: str) -> int:
    output = _git("diff", "--numstat", f"{base}...{head}")
    total = 0
    for line in output.splitlines():
        additions, deletions, path = line.split("\t", 2)
        file_path = Path(path)
        if file_path.name in GENERATED_OR_LOCK_FILES:
            continue
        if file_path.suffix not in CODE_SUFFIXES:
            continue
        if additions == "-" or deletions == "-":
            continue
        total += int(additions) + int(deletions)
    return total


def _risk_reasons(files: list[str], changed_code_lines: int) -> list[str]:
    reasons: list[str] = []
    code_files = [
        path
        for path in files
        if Path(path).suffix in CODE_SUFFIXES and Path(path).name not in GENERATED_OR_LOCK_FILES
    ]

    if changed_code_lines > 500:
        reasons.append(f"{changed_code_lines} non-generated code/config lines changed (> 500)")

    if len(code_files) > 15:
        reasons.append(f"{len(code_files)} code/config files changed (> 15)")

    touched_packages = {
        package
        for package in PACKAGE_ROOTS
        if any(path.startswith(f"{package}/") for path in files)
    }
    if len(touched_packages) > 1:
        reasons.append(
            "change spans multiple publishable packages: " + ", ".join(sorted(touched_packages))
        )

    if any(path.startswith("greenhouse_protocol/") for path in files):
        reasons.append("shared protocol/package contract changed")

    if any(path.startswith(".github/") for path in files):
        reasons.append("GitHub CI/review automation changed")

    if any(path.endswith("/pyproject.toml") or path == "pyproject.toml" for path in files):
        reasons.append("package metadata or runtime dependencies may have changed")

    sensitive = sorted(set(files) & SENSITIVE_FILES)
    if sensitive:
        reasons.append("sensitive repository boundary changed: " + ", ".join(sensitive))

    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("head")
    args = parser.parse_args()

    files = _changed_files(args.base, args.head)
    changed_code_lines = _changed_code_lines(args.base, args.head)
    reasons = _risk_reasons(files, changed_code_lines)

    print(f"Changed files: {len(files)}")
    print(f"Changed non-generated code/config lines: {changed_code_lines}")

    if not reasons:
        print("Risk gate: normal change, no manual self-review acknowledgement required.")
        return 0

    print("Risk gate: manual self-review required because:")
    for reason in reasons:
        print(f"  - {reason}")

    pr_body = os.environ.get("PR_BODY", "")
    if MANUAL_REVIEW_MARKER in pr_body:
        print("Manual self-review acknowledgement found.")
        return 0

    print(
        "\nReview the complete diff, then check this item in the pull request body:\n"
        f"  {MANUAL_REVIEW_MARKER}\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
