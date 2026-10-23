"""Nothing in this repository points at code or documents that are not in it,
and nothing looks like a credential.

The packages were first written inside a larger, private codebase. This
keeps them self-contained: no citation of documents that readers cannot
open, no name of a module they cannot import, and no secret that would be
published with the source.
"""

import hashlib
import pathlib
import re
import subprocess
from itertools import pairwise

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".txt",
    ".ini",
    ".json",
    ".yml",
    ".yaml",
    ".cfg",
    ".ts",
    ".tsx",
    ".js",
    ".html",
    ".css",
}

# A path into the repository's own docs/ folder, as cited in prose or a link.
# The lookbehind skips URLs and paths nested under another folder.
DOCS_CITATION = re.compile(r"(?<![\w/.-])docs/[\w./-]*[\w/]")

FORBIDDEN = {
    "a module of the original codebase": re.compile(
        r"\b(application|management|intelligence)\.[a-z_]+\b"
    ),
    "a private repository path": re.compile(r"\bbackend/"),
    "a planning reference": re.compile(r"\b[Pp]lan (10|20|21)\b"),
    "an API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}"),
    "a private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


# Names from the original codebase that must not appear, stored as SHA-256
# digests so that this file does not publish them itself. A name is compared
# lowercased with underscores and hyphens removed, and is also matched across
# two adjacent words, so "some_name", "some-name" and "Some Name" all count.
FORBIDDEN_NAME_DIGESTS = frozenset(
    {
        "15011027ac4a968f3cc56df82589d8d6c5965c3da8314e1d207d03372f937e7f",
        "465366e139400f57814b730f2e3ec4bbfb4550d2bf0c7aca402e3d5ee95b2a91",
        "4c50381754048d5e129707248f26246ffe6de5dfb145befeae22f4f2fcbf4c93",
        "78345b512a7264cbdbe0a253eb7ce3eabb2a5b63be9fb0f93be289cc45b37cad",
        "997b29e824bfb579fe548f68ba531a5ba3dc8eca1e812668ca8a80df715a4176",
        "e35de96842941c7163d734435059abcfcd0ac59bbcd2ee1f6e21b4229794ca1f",
        "f0ffaa6ecc7b604189dd957a993a835cef85eeb9a8540772f06ad36e354a182e",
    }
)


def _normalised(word: str) -> str:
    return word.lower().replace("_", "").replace("-", "")


def _name_digests(line: str) -> set[str]:
    words = re.findall(r"[\w-]+", line)
    candidates = {_normalised(w) for w in words}
    candidates |= {_normalised(a + b) for a, b in pairwise(words)}
    candidates |= {_normalised(part) for w in words for part in w.split("-")}
    return {hashlib.sha256(c.encode()).hexdigest() for c in candidates}


def _text_files() -> list[pathlib.Path]:
    """What would be published: tracked files, and new files git would track.

    Ignored files (tool caches, installed dependencies, build output, test
    reports) are not part of the repository, so they are not checked.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return sorted(
        path
        for path in (ROOT / name for name in listed)
        if path.is_file()
        and path.suffix in TEXT_SUFFIXES
        and path != pathlib.Path(__file__).resolve()
    )


def test_there_is_something_to_check() -> None:
    assert len(_text_files()) > 50


def test_every_cited_document_is_in_this_repository() -> None:
    """The original codebase kept design documents this repository does not
    have. Citing one points readers at something they cannot open, so a cited
    `docs/` path must exist here. What the folder is called does not matter.
    """
    hits = [
        f"  {path.relative_to(ROOT)}:{lineno}: {cited}"
        for path in _text_files()
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1)
        for cited in DOCS_CITATION.findall(line)
        if not (ROOT / cited).exists()
    ]
    assert not hits, "citations of documents that are not in this repository:\n" + "\n".join(hits)


def test_the_document_citation_check_can_fail() -> None:
    """A check that cannot fail is worth nothing."""
    line = "See docs/design/not-in-this-repository.md, docs/engineering.md and https://example.org/docs/x."

    cited = DOCS_CITATION.findall(line)

    assert cited == ["docs/design/not-in-this-repository.md", "docs/engineering.md"]
    assert [c for c in cited if not (ROOT / c).exists()] == [
        "docs/design/not-in-this-repository.md"
    ]


# What the guide for contributors names as a path, from the repository's
# root: a link's target, and each word of an inline code span that is one,
# such as the script in `python greenhouse_sim/tests/test_x.py --update`.
GUIDE_LINK_TARGET = re.compile(r"\]\(([^)\s#]+)")
GUIDE_CODE_SPAN = re.compile(r"`([^`]+)`")
# A fenced block's first and last lines.
GUIDE_FENCE = "```"
REPOSITORY_PATH = re.compile(
    r"(?:greenhouse_(?:sim|protocol|adapters)|scripts|tests|docs|\.github)(?:/[\w./-]*)?"
    r"|[\w-]+\.md"
)


# The recipes for contributors (audit W14): how to add a scenario, a
# layout, a weather, a device, an air or plant model, a viewer panel or an
# API route, each naming the files it touches and the tests to run.
GUIDES_DIR = ROOT / "docs" / "guides"
RECIPES = sorted(path for path in GUIDES_DIR.glob("*.md") if path.name != "README.md")


def _links_in(guide: str) -> list[str]:
    """A guide's links to files, as written: from the guide's folder."""
    return [target for target in GUIDE_LINK_TARGET.findall(guide) if "://" not in target]


def _code_paths_in(guide: str) -> list[str]:
    """The paths a guide's code names, inline or in a fenced block such as
    its commands: from the repository's root."""
    words: list[str] = []
    fenced = False
    for line in guide.splitlines():
        if line.lstrip().startswith(GUIDE_FENCE):
            fenced = not fenced
            continue
        spans = [line] if fenced else GUIDE_CODE_SPAN.findall(line)
        words += [word for span in spans for word in span.split()]
    return [word for word in words if REPOSITORY_PATH.fullmatch(word)]


def _paths_named_in(guide: str) -> list[str]:
    return _links_in(guide) + _code_paths_in(guide)


@pytest.mark.parametrize(
    "guide",
    [ROOT / "AGENTS.md", GUIDES_DIR / "README.md", *RECIPES],
    ids=lambda path: str(path.relative_to(ROOT)),
)
def test_each_guide_for_contributors_names_files_that_exist(guide: pathlib.Path) -> None:
    text = guide.read_text()
    missing = [link for link in _links_in(text) if not (guide.parent / link).exists()]
    missing += [path for path in _code_paths_in(text) if not (ROOT / path).exists()]

    assert _paths_named_in(text)
    assert missing == []


def test_the_guide_path_check_reads_fenced_commands() -> None:
    guide = (
        "Run:\n\n```bash\n"
        "uv run pytest greenhouse_sim/tests/test_gone.py \\\n"
        "  tests/test_x.py\n"
        "```\n"
    )

    assert _code_paths_in(guide) == ["greenhouse_sim/tests/test_gone.py", "tests/test_x.py"]


def test_there_are_recipes_and_each_names_a_test_to_run() -> None:
    assert RECIPES
    for recipe in RECIPES:
        named = _code_paths_in(recipe.read_text())
        assert any("/tests/" in path or "/e2e/" in path for path in named), recipe.name


def test_the_guides_index_lists_every_recipe() -> None:
    listed = set(_links_in((GUIDES_DIR / "README.md").read_text()))

    assert {recipe.name for recipe in RECIPES} <= listed


def test_the_guide_path_check_reads_links_and_paths_in_commands() -> None:
    guide = (
        "See [the rules](CONTRIBUTING.md), [a site](https://example.org/a.md) and"
        " [a part](#part); run `python greenhouse_sim/tests/test_x.py --update`,"
        " keep `greenhouse_protocol` apart, set `greenhouse_id`, and `npm ci` first."
    )

    assert _paths_named_in(guide) == [
        "CONTRIBUTING.md",
        "greenhouse_sim/tests/test_x.py",
        "greenhouse_protocol",
    ]


def test_no_file_uses_a_name_from_the_original_codebase() -> None:
    hits = [
        f"  {path.relative_to(ROOT)}:{lineno}"
        for path in _text_files()
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1)
        if _name_digests(line) & FORBIDDEN_NAME_DIGESTS
    ]
    assert not hits, "names from the original codebase:\n" + "\n".join(hits)


@pytest.mark.parametrize("what", sorted(FORBIDDEN))
def test_no_file_mentions(what: str) -> None:
    pattern = FORBIDDEN[what]
    hits = [
        f"  {path.relative_to(ROOT)}:{lineno}: {line.strip()[:100]}"
        for path in _text_files()
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1)
        if pattern.search(line)
    ]
    assert not hits, f"{what}:\n" + "\n".join(hits)
