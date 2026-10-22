"""A release's versions, changelog and README video, and the checks before
its tag (decision 0045).

    uv run release prepare 0.4.0         # on its branch, build/release-0.4.0
    uv run release video https://github.com/user-attachments/assets/<id>
    uv run release notes 0.4.0           # the GitHub release's notes
    python scripts/release.py verify --branch build/release-0.4.0 \\
        --author <login> --merged-by <login> --owner <login>

`prepare` moves the three packages to the version, and the simulator's and
the adapters' range of the protocol with them, makes the changelog's
Unreleased entries the version's, dated, and locks. `video` points the
README's demo at a video uploaded to GitHub, captioned with the packages'
version. `verify` is what the release workflow checks of a merged release
pull request before it tags its merge commit, and prints `version=<version>`
for the workflow's next steps. Standard library only: the workflow runs it
with a bare Python.
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")
# The packages that depend on the protocol, at the version released with it.
PROTOCOL_DEPENDENTS = ("greenhouse_sim", "greenhouse_adapters")
CHANGELOG = Path("CHANGELOG.md")
README = Path("README.md")
# Who may open a release pull request besides the repository's owner.
RELEASE_MANAGERS = Path(".github/release-managers")
RELEASE_BRANCH = "build/release-"
UNRELEASED = "## Unreleased"
DEMO = "## Demo"
# The first line of every GitHub release's notes, above the changelog's.
NOTES_INTRO = "Not on PyPI yet: install from a clone, see the README."

_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_PROJECT_VERSION = re.compile(r'^version = "([^"]*)"$', re.MULTILINE)
_PROTOCOL_RANGE = re.compile(r'"greenhouse-protocol[<>=!~][^"]*"')
_HEADING = re.compile(r"^## ", re.MULTILINE)
_DATED = re.compile(r"^## (\S+) - \d{4}-\d{2}-\d{2}$", re.MULTILINE)
_VIDEO_URL = re.compile(r"^https://github\.com/user-attachments/assets/[0-9a-f-]+$", re.MULTILINE)
_CAPTIONED_VERSION = re.compile(r"\bv\d+\.\d+\.\d+\b")


class Refused(ValueError):
    """The release cannot go on; the message says why."""


def parse_version(text: str) -> tuple[int, int, int]:
    found = _VERSION.fullmatch(text)
    if found is None:
        raise Refused(f"{text!r} is not a version: three numbers, such as 0.4.0")
    major, minor, patch = (int(number) for number in found.groups())
    return major, minor, patch


def protocol_range(version: str) -> str:
    """The range of the protocol released with `version`: up to the next
    version that may break it, the next minor below 1.0 and the next major
    from 1.0 on."""
    major, minor, _ = parse_version(version)
    ceiling = f"0.{minor + 1}" if major == 0 else f"{major + 1}"
    return f'"greenhouse-protocol>={version},<{ceiling}"'


def current_version(root: Path = ROOT) -> str:
    """The version the three packages share; refused when they differ."""
    versions = {
        package: _PROJECT_VERSION.findall((root / package / "pyproject.toml").read_text())
        for package in PACKAGES
    }
    shared: set[str] = {found[0] for found in versions.values() if len(found) == 1}
    if len(shared) != 1 or any(len(found) != 1 for found in versions.values()):
        raise Refused(f"the packages do not share one version: {versions}")
    return shared.pop()


def _section(text: str, heading: str) -> tuple[int, int]:
    """Where the body of the `## ` section under `heading` starts and ends."""
    start = text.find(f"\n{heading}\n")
    if start < 0:
        raise Refused(f"no {heading!r} section")
    body = start + len(heading) + 2
    following = _HEADING.search(text, body)
    return body, following.start() if following else len(text)


def _replace_once(text: str, pattern: re.Pattern[str], new: str, where: Path) -> str:
    replaced, count = pattern.subn(new, text)
    if count != 1:
        raise Refused(f"{where}: expected one match of {pattern.pattern!r}, found {count}")
    return replaced


def prepare(version: str, date: datetime.date, root: Path = ROOT) -> list[Path]:
    """Moves the packages and the changelog to `version`, released on
    `date`, and gives the files it changed."""
    current = current_version(root)
    if parse_version(version) <= parse_version(current):
        raise Refused(f"{version} does not follow {current}, the packages' version")
    changelog = (root / CHANGELOG).read_text()
    if f"\n## {version} - " in changelog:
        raise Refused(f"{CHANGELOG} already has a section for {version}")
    body, end = _section(changelog, UNRELEASED)
    entries = changelog[body:end].strip()
    if not entries:
        raise Refused(f"{CHANGELOG}'s Unreleased section is empty: nothing to release")
    edits = {
        CHANGELOG: (
            f"{changelog[:body]}\n## {version} - {date.isoformat()}\n\n{entries}\n\n"
            f"{changelog[end:]}"
        )
    }
    for package in PACKAGES:
        path = Path(package) / "pyproject.toml"
        text = _replace_once(
            (root / path).read_text(), _PROJECT_VERSION, f'version = "{version}"', path
        )
        if package in PROTOCOL_DEPENDENTS:
            text = _replace_once(text, _PROTOCOL_RANGE, protocol_range(version), path)
        edits[path] = text
    for path, text in edits.items():
        (root / path).write_text(text)
    return sorted(edits)


def set_video(url: str, root: Path = ROOT) -> str:
    """Points the README's demo at `url`, its caption at the packages'
    version, and gives that version."""
    if _VIDEO_URL.fullmatch(url) is None:
        raise Refused(f"{url!r} is not a video uploaded to GitHub (github.com/user-attachments)")
    version = current_version(root)
    readme = (root / README).read_text()
    body, end = _section(readme, DEMO)
    demo = _replace_once(readme[body:end], _VIDEO_URL, url, README)
    demo = _CAPTIONED_VERSION.sub(f"v{version}", demo)
    (root / README).write_text(readme[:body] + demo + readme[end:])
    return version


def notes(version: str, root: Path = ROOT) -> str:
    """The GitHub release's notes: the changelog's section for `version`."""
    changelog = (root / CHANGELOG).read_text()
    dated = next((found for found in _DATED.finditer(changelog) if found[1] == version), None)
    if dated is None:
        raise Refused(f"{CHANGELOG} has no dated section for {version}")
    following = _HEADING.search(changelog, dated.end())
    entries = changelog[dated.end() : following.start() if following else None].strip()
    return f"{NOTES_INTRO}\n\n{entries}\n"


def release_managers(root: Path = ROOT) -> set[str]:
    """The GitHub logins listed as release managers, one a line."""
    lines = (root / RELEASE_MANAGERS).read_text().splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def problems(
    branch: str,
    author: str,
    merged_by: str,
    owner: str,
    tags: Sequence[str],
    root: Path = ROOT,
) -> list[str]:
    """Why a merged release pull request is not tagged; none when it is."""
    version = current_version(root)
    found = []
    if branch != f"{RELEASE_BRANCH}{version}":
        found.append(f"branch {branch} does not release {version}, the packages' version")
    if merged_by != owner:
        found.append(f"merged by {merged_by}: only the repository's owner, {owner}, releases")
    if author != owner and author not in release_managers(root):
        found.append(f"opened by {author}, who is neither {owner} nor in {RELEASE_MANAGERS}")
    if f"v{version}" in tags:
        found.append(f"v{version} is already tagged")
    released = [tag.removeprefix("v") for tag in tags if _VERSION.fullmatch(tag.removeprefix("v"))]
    later = [tag for tag in released if parse_version(tag) > parse_version(version)]
    if later:
        found.append(f"{version} does not follow {max(later, key=parse_version)}, already tagged")
    for package in PROTOCOL_DEPENDENTS:
        if protocol_range(version) not in (root / package / "pyproject.toml").read_text():
            found.append(f"{package} does not depend on the protocol as {protocol_range(version)}")
    try:
        notes(version, root)
        _section((root / CHANGELOG).read_text(), UNRELEASED)
    except Refused as refused:
        found.append(str(refused))
    return found


def _tags(root: Path) -> list[str]:
    listed = subprocess.run(
        ["git", "tag", "--list", "v*"], cwd=root, check=True, capture_output=True, text=True
    )
    return listed.stdout.split()


def _lock(root: Path) -> None:
    print("$ uv lock", flush=True)
    subprocess.run(["uv", "lock"], cwd=root, check=True)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    preparing = commands.add_parser("prepare", help="versions, protocol range, changelog, lock")
    preparing.add_argument("version")
    preparing.add_argument("--date", type=datetime.date.fromisoformat, help="default: today")
    commands.add_parser("video", help="the README's demo video").add_argument("url")
    commands.add_parser("notes", help="the GitHub release's notes").add_argument("version")
    verifying = commands.add_parser("verify", help="a merged release pull request, to tag")
    for option in ("--branch", "--author", "--merged-by", "--owner"):
        verifying.add_argument(option, required=True)
    args = parser.parse_args(arguments)
    try:
        if args.command == "prepare":
            changed = prepare(args.version, args.date or datetime.date.today(), ROOT)
            print("Changed: " + ", ".join(str(path) for path in changed))
            _lock(ROOT)
        elif args.command == "video":
            print(f"README.md plays {args.url}, captioned v{set_video(args.url, ROOT)}")
        elif args.command == "notes":
            print(notes(args.version, ROOT), end="")
        else:
            tags = _tags(ROOT)
            found = problems(args.branch, args.author, args.merged_by, args.owner, tags, ROOT)
            if found:
                print("Not released:\n" + "\n".join(f"- {line}" for line in found), file=sys.stderr)
                return 1
            print(f"version={current_version(ROOT)}")
    except Refused as refused:
        print(f"Refused: {refused}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
