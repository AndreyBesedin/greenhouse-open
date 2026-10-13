"""Whether a Dependabot pull request may merge by itself (decision 0033).

A minor or patch update that changes no code merges by itself once every
required check has passed. This decides the first half, from what
`dependabot/fetch-metadata` reports of the update and the files the pull
request changes; GitHub's auto-merge then waits for the checks.

    python scripts/dependabot_auto_merge.py --actor "dependabot[bot]" \
        --dependencies '<updated-dependencies-json>' --files changed.txt

Exits 0 when the update may merge by itself, and 1, with the reasons, when
it waits for a review. Standard library only: the workflow runs it from
`main`, apart from the pull request's own code.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

DEPENDABOT = "dependabot[bot]"
# What Dependabot changes for an update: manifests and lockfiles. Workflows
# are left out: an action's update changes code that CI runs.
MANIFESTS = frozenset(
    {
        "package.json",
        "package-lock.json",
        "requirements-dev.txt",
        "pyproject.toml",
        ".pre-commit-config.yaml",
    }
)
MINOR = "version-update:semver-minor"
PATCH = "version-update:semver-patch"
_MAJOR = re.compile(r"v?(\d+)\.")


def major(version: str) -> int | None:
    """A version's major number, if it has one: `v4.2.0` is 4."""
    found = _MAJOR.match(version.strip())
    return int(found.group(1)) if found else None


def reasons_to_wait(
    actor: str, dependencies: Sequence[dict[str, Any]], files: Sequence[str]
) -> list[str]:
    """Why the update waits for a review; none when it may merge by itself.

    `dependencies` is fetch-metadata's `updated-dependencies-json`, which it
    fills only when every commit is Dependabot's own, verified; `actor` is
    whoever pushed last, and `files` what the pull request changes.
    """
    reasons = []
    if actor != DEPENDABOT:
        reasons.append(f"last pushed by {actor}, not by Dependabot")
    if not dependencies:
        reasons.append("no update reported: a commit that is not Dependabot's, or no metadata")
    for dependency in dependencies:
        name = dependency.get("dependencyName") or "a dependency"
        kind = dependency.get("updateType") or "an update of unknown type"
        before = dependency.get("prevVersion") or "?"
        after = dependency.get("newVersion") or "?"
        if kind not in (MINOR, PATCH):
            reasons.append(f"{name} {before} to {after}: {kind}")
        elif kind == MINOR and major(before) in (0, None):
            # Below 1.0 a minor release may break; a version not known may
            # be one.
            reasons.append(f"{name} {before} to {after}: a minor update below 1.0")
        if dependency.get("maintainerChanges"):
            reasons.append(f"{name}: its maintainers changed")
    others = sorted(path for path in files if PurePosixPath(path).name not in MANIFESTS)
    if others:
        reasons.append("changes more than manifests and lockfiles: " + ", ".join(others))
    if not files:
        reasons.append("changes no file")
    return reasons


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--actor", required=True, help="who pushed last")
    parser.add_argument(
        "--dependencies", default="", help="fetch-metadata's updated-dependencies-json"
    )
    parser.add_argument("--files", type=Path, required=True, help="the changed files, one per line")
    parsed = parser.parse_args(arguments)
    dependencies = json.loads(parsed.dependencies) if parsed.dependencies.strip() else []
    files = [line for line in parsed.files.read_text().splitlines() if line.strip()]

    reasons = reasons_to_wait(parsed.actor, dependencies, files)
    if not reasons:
        print("A minor or patch update that changes no code: it merges once the checks pass.")
        return 0
    print("This update waits for a review:")
    for reason in reasons:
        print(f"  - {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
