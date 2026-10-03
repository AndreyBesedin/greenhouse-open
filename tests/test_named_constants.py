"""Package source names the numbers that carry meaning.

The check lives in `scripts/check_named_constants.py`, which also runs as a
pre-commit hook on staged files. Running it here means CI enforces it too.
"""

import pytest

from scripts.check_named_constants import package_sources, unnamed_numbers


def test_package_source_names_its_numbers() -> None:
    findings = [
        f"  {path}:{line}: {value!r}"
        for path in package_sources()
        for line, value in unnamed_numbers(path.read_text())
    ]
    assert not findings, "unnamed numbers in package source:\n" + "\n".join(findings)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Unnamed: buried in arithmetic, a comparison, or a local variable.
        ("factor = 1.0 - 0.6 * stress\n", [(1, 0.6)]),
        ("if progress >= 0.85:\n    pass\n", [(1, 0.85)]),
        ("drift = -0.6 * x\n", [(1, 0.6)]),
        ("def f() -> None:\n    threshold: float = 0.6\n", [(2, 0.6)]),
        ("rng.uniform(0.85, 1.15)\n", [(1, 0.85), (1, 1.15)]),
        # Named: a constant, a field default, a keyword or a parameter default.
        ("RATE = 0.6\n", []),
        ("RATE: Final = 0.6\n", []),
        ("BYTES = 1024 * 1024\n", []),
        ("RANGE = (0.85, 1.15)\n", []),
        ("class C:\n    bounds: tuple[float, float] = (18.0, 32.0)\n", []),
        ("def f(scale: float = 0.6) -> float:\n    return scale\n", []),
        ("rng.normal(loc=0.0, scale=0.6)\n", []),
        # Structure: identities, halves, percentages, exponents, indices.
        ("middle = (low + high) / 2\n", []),
        ("percent = 100.0 * part / whole\n", []),
        ("mass = k * diameter**3\n", []),
        ("third = parts[3]\nrest = parts[4:]\n", []),
    ],
)
def test_what_counts_as_named(source: str, expected: list[tuple[int, float]]) -> None:
    assert unnamed_numbers(source) == expected
