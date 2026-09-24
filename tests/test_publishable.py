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

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".ini", ".json", ".yml", ".yaml", ".cfg"}
SKIPPED_PARTS = {"__pycache__", ".venv", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".git"}

FORBIDDEN = {
    "a private design document": re.compile(r"docs/(design|archive)/"),
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
    candidates |= {_normalised(a + b) for a, b in zip(words, words[1:], strict=False)}
    candidates |= {_normalised(part) for w in words for part in w.split("-")}
    return {hashlib.sha256(c.encode()).hexdigest() for c in candidates}


def _text_files() -> list[pathlib.Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in TEXT_SUFFIXES
        and not SKIPPED_PARTS & set(path.parts)
        and path != pathlib.Path(__file__).resolve()
    )


def test_there_is_something_to_check() -> None:
    assert len(_text_files()) > 50


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
