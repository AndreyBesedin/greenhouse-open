"""Flag numbers in package source that nothing names.

A number that encodes a modelling assumption, a rate, a threshold, a range, a
tolerance or a unit conversion gets a name that says what it is (see
docs/engineering.md, "Name the numbers that carry meaning"). This finds the
number literals in the packages' own source that have none.

A literal counts as named when it is assigned to an UPPER_CASE or `Final`
name, is a class field's default, is passed as a keyword argument or is a
parameter's default. Literals that are arithmetic structure rather than
meaning are always allowed: 0, 1, -1, 2 (halves, midpoints), 100
(percentages), exponents and indices. Tests and examples are not checked,
because a literal there is usually the expected value itself.

    python scripts/check_named_constants.py           # every package's source
    python scripts/check_named_constants.py FILE ...  # only these files
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")

STRUCTURAL = frozenset({0, 1, -1, 2, 100})


def package_sources() -> list[Path]:
    return sorted(path for package in PACKAGES for path in (ROOT / package / package).rglob("*.py"))


def unnamed_numbers(source: str) -> list[tuple[int, int | float]]:
    """The line and value of every number literal that nothing names."""
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for outer in ast.walk(tree):
        for inner in ast.iter_child_nodes(outer):
            parents[inner] = outer

    found: list[tuple[int, int | float]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        literal = node.value
        if isinstance(literal, bool) or not isinstance(literal, (int, float)):
            continue
        parent = parents.get(node)
        signed = (
            -literal
            if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.USub)
            else literal
        )
        if signed in STRUCTURAL or _is_named(node, parents):
            continue
        found.append((node.lineno, literal))
    return found


def _is_named(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether something between the literal and its statement names it."""
    child, parent = node, parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.UnaryOp):
            child, parent = parent, parents.get(parent)
            continue
        if (
            isinstance(parent, ast.BinOp)
            and isinstance(parent.op, ast.Pow)
            and child is parent.right
        ):
            return True
        if isinstance(parent, ast.Subscript) and child is parent.slice:
            return True
        if isinstance(parent, (ast.Slice, ast.keyword, ast.arguments)):
            return True
        if isinstance(parent, ast.Assign):
            return all(_is_constant_name(target) for target in parent.targets)
        if isinstance(parent, ast.AnnAssign):
            is_field = isinstance(parents.get(parent), ast.ClassDef)
            is_final = "Final" in ast.unparse(parent.annotation)
            return is_field or is_final or _is_constant_name(parent.target)
        if isinstance(parent, (ast.stmt, ast.Lambda)):
            return False
        child, parent = parent, parents.get(parent)
    return False


def _is_constant_name(target: ast.expr) -> bool:
    return isinstance(target, ast.Name) and target.id.isupper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="default: every package's source")
    args = parser.parse_args(argv)
    files: list[Path] = args.files or package_sources()

    findings = [
        f"{path}:{line}: {value!r} has no name; give it a constant that says what it is"
        for path in files
        for line, value in unnamed_numbers(path.read_text())
    ]
    for finding in findings:
        print(finding)
    if findings:
        print("\nSee docs/engineering.md, 'Name the numbers that carry meaning'.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
