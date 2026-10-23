"""A release's versions, changelog and README video, its tag, and the
checks before both (decision 0045).

    uv run release prepare 0.4.0         # on its branch, build/release-0.4.0
    uv run release video https://github.com/user-attachments/assets/<id>
    uv run release tag <pull request>    # the owner, on its merge commit
    uv run release notes 0.4.0           # the GitHub release's notes
    python scripts/release.py verify --tag v0.4.0 --tagged-by <login> --owner <login>

`prepare` moves the three packages to the version, and the simulator's and
the adapters' range of the protocol with them, makes the changelog's
Unreleased entries the version's, dated, and locks. `video` points the
README's demo at a video uploaded to GitHub, captioned with the packages'
version. `tag` checks a merged release pull request and, for the
repository's owner, tags its merge commit and pushes the tag; `verify` is
the same check, which the release workflow makes of a pushed tag before it
publishes the release, and prints `version=<version>` for its next step.
A tag already on the merge commit passes both, so that either can be run
again. Standard library only, with git and the GitHub CLI: the workflow
runs it with a bare Python.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

# Semantic versioning's: ASCII digits, no leading zero.
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_PROJECT_VERSION = re.compile(r'^version = "([^"]*)"$', re.MULTILINE)
_PROTOCOL_RANGE = re.compile(r'"greenhouse-protocol[<>=!~][^"]*"')
_HEADING = re.compile(r"^## ", re.MULTILINE)
_DATED = re.compile(r"^## (\S+) - \d{4}-\d{2}-\d{2}$", re.MULTILINE)
_VIDEO_URL = re.compile(r"^https://github\.com/user-attachments/assets/[0-9a-f-]+$", re.MULTILINE)
_CAPTIONED_VERSION = re.compile(r"\bv\d+\.\d+\.\d+\b")


class Refused(ValueError):
    """The release cannot go on; the message says why."""


@dataclass(frozen=True)
class Merge:
    """A merged release pull request, as GitHub reports it."""

    number: int
    branch: str
    author: str
    merged_by: str
    # The commit its merge put on `main`, and the base it was compared
    # with, from before it.
    commit: str
    base: str

    @classmethod
    def of(cls, pull: Mapping[str, Any]) -> Merge:
        """From GitHub's answer for a pull request (`GET .../pulls/<n>`)."""
        if not pull.get("merged_at"):
            raise Refused(f"#{pull['number']} is not merged")
        return cls(
            number=pull["number"],
            branch=pull["head"]["ref"],
            author=pull["user"]["login"],
            merged_by=pull["merged_by"]["login"],
            commit=pull["merge_commit_sha"],
            base=pull["base"]["sha"],
        )


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


def release_managers(listed: str) -> set[str]:
    """The GitHub logins a release managers' list names, one a line."""
    lines = listed.splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def problems(
    merge: Merge,
    owner: str,
    tagged_by: str,
    *,
    managers: set[str],
    tags: Mapping[str, str],
    root: Path = ROOT,
) -> list[str]:
    """Why `merge` is not tagged and released; none when it is.

    `managers` are the release managers as listed before the pull request,
    which cannot then add its own author; `tags` maps each `v*` tag to the
    commit it tags."""
    version = current_version(root)
    found = []
    if merge.branch != f"{RELEASE_BRANCH}{version}":
        found.append(f"branch {merge.branch} does not release {version}, the packages' version")
    if merge.merged_by != owner:
        found.append(f"merged by {merge.merged_by}: only the repository's owner, {owner}, merges")
    if tagged_by != owner:
        found.append(f"tagged by {tagged_by}: only the repository's owner, {owner}, tags")
    if merge.author != owner and merge.author not in managers:
        found.append(f"opened by {merge.author}, who is neither {owner} nor in {RELEASE_MANAGERS}")
    tagged = tags.get(f"v{version}")
    if tagged is not None and tagged != merge.commit:
        found.append(f"v{version} is already tagged, on {tagged[:12]}")
    released = [tag.removeprefix("v") for tag in tags if _VERSION.fullmatch(tag.removeprefix("v"))]
    later = [tag for tag in released if parse_version(tag) > parse_version(version)]
    if later:
        found.append(f"{version} does not follow {max(later, key=parse_version)}, already tagged")
    expected = protocol_range(version)
    found.extend(
        f"{package} does not depend on the protocol as {expected}"
        for package in PROTOCOL_DEPENDENTS
        if expected not in (root / package / "pyproject.toml").read_text()
    )
    try:
        notes(version, root)
        changelog = (root / CHANGELOG).read_text()
        body, end = _section(changelog, UNRELEASED)
        if changelog[body:end].strip():
            found.append(f"{CHANGELOG}'s Unreleased entries would be left out of the notes")
    except Refused as refused:
        found.append(str(refused))
    return found


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=root, capture_output=True, text=True)


def _tags(root: Path) -> dict[str, str]:
    """Each `v*` tag and the commit it tags, an annotated tag's peeled."""
    listing = "--format=%(refname:short) %(*objectname) %(objectname)"
    listed = _git(root, "for-each-ref", listing, "refs/tags/v*")
    if listed.returncode:
        raise Refused(f"the tags cannot be read: {listed.stderr.strip()}")
    # A lightweight tag has no peeled commit: its own object is the commit.
    return {name: commit for name, commit, *_ in map(str.split, listed.stdout.splitlines())}


def managers_at(revision: str, root: Path = ROOT) -> set[str]:
    """The release managers listed at `revision`; none where it has no list."""
    shown = _git(root, "show", f"{revision}:{RELEASE_MANAGERS.as_posix()}")
    return release_managers(shown.stdout) if shown.returncode == 0 else set()


def _gh(*arguments: str) -> Any:
    """The GitHub CLI's JSON answer, for the repository of the checkout."""
    answered = subprocess.run(["gh", *arguments], capture_output=True, text=True)
    if answered.returncode:
        raise Refused(f"gh {' '.join(arguments)}: {answered.stderr.strip()}")
    return json.loads(answered.stdout)


def pull_request(number: int) -> Merge:
    return Merge.of(_gh("api", f"repos/{{owner}}/{{repo}}/pulls/{number}"))


def merged_as(commit: str) -> Merge:
    """The pull request whose merge made `commit`."""
    pulls = _gh("api", f"repos/{{owner}}/{{repo}}/commits/{commit}/pulls")
    numbers = [pull["number"] for pull in pulls if pull.get("merge_commit_sha") == commit]
    if not numbers:
        raise Refused(f"no pull request was merged as {commit[:12]}")
    return pull_request(numbers[0])


def _head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _report(found: list[str]) -> int:
    print("Not released:\n" + "\n".join(f"- {line}" for line in found), file=sys.stderr)
    return 1


def tag(number: int, root: Path = ROOT) -> int:
    """Tags the merge of release pull request `number`, checked out at
    `root`, and pushes the tag, for the repository's owner."""
    merge = pull_request(number)
    if _head(root) != merge.commit:
        raise Refused(f"check out #{number}'s merge first: git switch --detach {merge.commit}")
    _git(root, "fetch", "--quiet", "--tags", "origin")
    owner = _gh("api", "repos/{owner}/{repo}")["owner"]["login"]
    tags = _tags(root)
    found = problems(
        merge,
        owner,
        _gh("api", "user")["login"],
        managers=managers_at(merge.base, root),
        tags=tags,
        root=root,
    )
    if found:
        return _report(found)
    version = current_version(root)
    name = f"v{version}"
    if name not in tags:
        message = f"greenhouse-open {version}. See CHANGELOG.md."
        for step in (["tag", "--annotate", name, "--message", message], ["push", "origin", name]):
            done = _git(root, *step)
            if done.returncode:
                raise Refused(f"git {' '.join(step)}: {done.stderr.strip()}")
    print(f"{name} tags {merge.commit[:12]}, #{number}'s merge; the Release workflow publishes it.")
    return 0


def _lock(root: Path) -> None:
    print("$ uv lock", flush=True)
    subprocess.run(["uv", "lock"], cwd=root, check=True)


def _today() -> datetime.date:
    """Today, where the release is made: the local date, read from an aware
    clock."""
    return datetime.datetime.now(datetime.UTC).astimezone().date()


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    preparing = commands.add_parser("prepare", help="versions, protocol range, changelog, lock")
    preparing.add_argument("version")
    preparing.add_argument("--date", type=datetime.date.fromisoformat, help="default: today")
    commands.add_parser("video", help="the README's demo video").add_argument("url")
    commands.add_parser("notes", help="the GitHub release's notes").add_argument("version")
    tagging = commands.add_parser("tag", help="tag a merged release pull request, as the owner")
    tagging.add_argument("pull_request", type=int)
    verifying = commands.add_parser("verify", help="a pushed tag, before its release")
    for option in ("--tag", "--tagged-by", "--owner"):
        verifying.add_argument(option, required=True)
    args = parser.parse_args(arguments)
    try:
        if args.command == "prepare":
            changed = prepare(args.version, args.date or _today(), ROOT)
            print("Changed: " + ", ".join(str(path) for path in changed))
            _lock(ROOT)
        elif args.command == "video":
            print(f"README.md plays {args.url}, captioned v{set_video(args.url, ROOT)}")
        elif args.command == "notes":
            print(notes(args.version, ROOT), end="")
        elif args.command == "tag":
            return tag(args.pull_request, ROOT)
        else:
            merge = merged_as(_head(ROOT))
            managers = managers_at(merge.base, ROOT)
            found = problems(
                merge, args.owner, args.tagged_by, managers=managers, tags=_tags(ROOT), root=ROOT
            )
            version = current_version(ROOT)
            if args.tag != f"v{version}":
                found.append(f"tag {args.tag} does not name {version}, the packages' version")
            if found:
                return _report(found)
            print(f"version={version}")
    except Refused as refused:
        print(f"Refused: {refused}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
