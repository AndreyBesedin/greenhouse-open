"""Gate higher-risk pull requests on an explicit manual self-review.

The repository is currently maintained by one developer, so GitHub's normal
"required human approval" mechanism is not useful: a pull request author
cannot approve their own pull request. This check keeps the fast path fast and
adds deliberate friction only when a diff crosses clear risk boundaries.

The acknowledgement is the ticked item in the pull request's description. A
Dependabot pull request has no template to tick, and someone else opened it,
so there a maintainer's approval of its latest commit is the acknowledgement
(decision 0034). The workflow passes its reviews in `PR_REVIEWS`, a file of
one JSON object a line: `user`, `state`, `commit_id`, `author_association`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOTS = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")
MANUAL_REVIEW_MARKER = "- [x] I manually reviewed the complete diff"
# The acknowledgement: the template's item ticked, where GitHub draws it as a
# task item. That is a line of its own, indented by at most the three spaces
# CommonMark allows a list item (four start an indented code block), and not
# inside anything GitHub does not render as Markdown. The gate's own hint
# prints the ticked item, so a pasted failure log must not count.
_ACKNOWLEDGED = re.compile(r"^ {0,3}- \[[xX]\] I manually reviewed the complete diff", re.MULTILINE)
# What GitHub does not render as Markdown: an HTML comment, which an
# unterminated `<!--` extends to the end; a fenced code block, opened by three
# or more backticks or tildes and closed by a fence of the same kind, or the
# end; and an inline code span, within a line, closed by a run of backticks
# as long as the one that opened it. Whichever opens first in the description
# wins, as in the renderer, so a `<!--` quoted in code opens no comment, and
# a fence is tried before a code span where both could start.
_NOT_RENDERED = re.compile(
    r"<!--.*?(?:-->|\Z)"
    r"|^ {0,3}(?P<fence>`{3,}|~{3,}).*?(?:^ {0,3}(?P=fence)[^\n]*$|\Z)"
    r"|(?P<span>`+)(?:(?!(?P=span))[^\n])+?(?P=span)(?!`)",
    re.DOTALL | re.MULTILINE,
)
DEPENDABOT = "dependabot[bot]"
# Who may acknowledge a pull request by approving it: the repository's owner,
# its organisation's members and its collaborators, not any GitHub user.
MAINTAINERS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
# The review states that are a verdict; a comment, or a review still
# pending, leaves the reviewer's verdict as it was.
VERDICTS = frozenset({"APPROVED", "CHANGES_REQUESTED", "DISMISSED"})

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

# Files that hold a boundary: the repository's own checks, the tests that
# hold its package and truth boundaries, and where ground truth is kept apart
# from observations, or leaves the simulator, and where a client's uploads
# are taken in, from the socket to the checkpoint.
SENSITIVE_FILES = {
    ".pre-commit-config.yaml",
    "requirements-dev.txt",
    "tests/test_dependencies.py",
    "tests/test_publishable.py",
    "greenhouse_sim/tests/test_sensor_observations.py",
    "greenhouse_sim/greenhouse_sim/core/engine.py",
    "greenhouse_sim/greenhouse_sim/ground_truth.py",
    "greenhouse_sim/greenhouse_sim/sensors/generation.py",
    "greenhouse_sim/greenhouse_sim/sensors/air.py",
    "greenhouse_sim/greenhouse_sim/core/rng.py",
    "greenhouse_sim/greenhouse_sim/evaluation/sensor_truth.py",
    "greenhouse_sim/greenhouse_sim/services/sensors.py",
    "greenhouse_sim/greenhouse_sim/services/checkpoints.py",
    "greenhouse_sim/greenhouse_sim/api/server.py",
    "greenhouse_sim/greenhouse_sim/api/routes.py",
}
# Folders whose every file is a boundary: the scripts that check and merge
# pull requests, this gate among them.
SENSITIVE_FOLDERS = ("scripts/",)
# Data the simulator keeps and compares its runs with: replacing it is not
# counted in lines, which a regenerated file has thousands of or, gzipped,
# none, but always asks for a review.
KEPT_DATA_FOLDERS = (
    "greenhouse_sim/greenhouse_sim/cfd/results/",
    "greenhouse_sim/greenhouse_sim/scenarios/openings/",
    "greenhouse_sim/greenhouse_sim/weather/recorded/",
    "greenhouse_sim/tests/fixtures/",
    "greenhouse_sim/tests/golden/",
    "greenhouse_sim/web/public/fields/",
    "greenhouse_sim/web/public/scenes/",
)


def _git(*args: str, repo: Path = ROOT) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _changed_files(base: str, head: str, repo: Path = ROOT) -> list[str]:
    """Every path the change touches, a moved file under both its names.

    Rename detection would report only the destination, so a file moved out
    of a sensitive folder would not be seen leaving it."""
    output = _git("diff", "--no-renames", "--name-only", f"{base}...{head}", repo=repo)
    return [line for line in output.splitlines() if line]


def _changed_code_lines(base: str, head: str, repo: Path = ROOT) -> int:
    """The lines to review. Here renames are detected, so a file moved as it
    is counts no lines; its path then reads `{old => new}/name`."""
    output = _git("diff", "-M", "--numstat", f"{base}...{head}", repo=repo)
    total = 0
    for line in output.splitlines():
        additions, deletions, path = line.split("\t", 2)
        file_path = Path(path)
        if file_path.name in GENERATED_OR_LOCK_FILES or _kept_data(path):
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
        if Path(path).suffix in CODE_SUFFIXES
        and Path(path).name not in GENERATED_OR_LOCK_FILES
        and not _kept_data(path)
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

    sensitive = sorted(
        path for path in files if path in SENSITIVE_FILES or path.startswith(SENSITIVE_FOLDERS)
    )
    if sensitive:
        reasons.append("sensitive repository boundary changed: " + ", ".join(sensitive))

    kept = sorted(path for path in files if _kept_data(path))
    if kept:
        reasons.append("kept simulation data changed: " + ", ".join(kept))

    return reasons


def _kept_data(path: str) -> bool:
    return path.startswith(KEPT_DATA_FOLDERS)


def acknowledged(body: str) -> bool:
    """Whether a pull request's description ticks the manual-review item
    where GitHub renders it: on a line of its own, outside an HTML comment
    and outside a fenced code block."""
    return _ACKNOWLEDGED.search(_NOT_RENDERED.sub("", body)) is not None


def approved(reviews: Iterable[dict[str, Any]], head: str) -> bool:
    """Whether a maintainer's latest verdict approves the `head` commit.

    `reviews` come in the order they were submitted. An approval of an
    earlier commit does not cover a later push, and a later request for
    changes, or the approval's dismissal, withdraws it.
    """
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        if review["state"] in VERDICTS:
            latest[review["user"]] = review
    return any(
        review["state"] == "APPROVED"
        and review["commit_id"] == head
        and review["author_association"] in MAINTAINERS
        for review in latest.values()
    )


def _reviews(path: str) -> list[dict[str, Any]]:
    if not path or not Path(path).exists():
        return []
    lines = Path(path).read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


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
    if acknowledged(pr_body):
        print("Manual self-review acknowledgement found.")
        return 0

    if os.environ.get("PR_AUTHOR") == DEPENDABOT:
        if approved(_reviews(os.environ.get("PR_REVIEWS", "")), args.head):
            print("A maintainer approved its latest commit.")
            return 0
        print("\nReview the complete diff, then approve the pull request's latest commit.\n")
        return 1

    print(
        "\nReview the complete diff, then check this item in the pull request body:\n"
        f"  {MANUAL_REVIEW_MARKER}\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
