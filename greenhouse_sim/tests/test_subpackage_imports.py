"""The simulator's subpackages tangle no further (decision 0037).

Until its layers are drawn, the pairs of subpackages that import each other
are the ones listed here: a new pair fails, and a pair that is untangled
leaves the list, which only shrinks. A top-level module counts as a
subpackage of its own.
"""

import ast
import pathlib
from collections.abc import Iterable, Iterator

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "greenhouse_sim"

# Each pair imports the other, in one module or another, today.
TANGLED: frozenset[tuple[str, str]] = frozenset(
    {
        ("biology", "core"),
        ("biology", "world"),
        ("cfd", "scenarios"),
        ("cfd", "services"),
        ("climate", "core"),
        ("climate", "weather"),
        ("core", "scenarios"),
        ("solar", "weather"),
    }
)


def _imported_modules(source: str) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            # `from greenhouse_sim import solar` imports a subpackage by name.
            if node.module == "greenhouse_sim":
                modules.update(f"greenhouse_sim.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def _subpackage(module: str) -> str | None:
    parts = module.split(".")
    return parts[1] if parts[0] == "greenhouse_sim" and len(parts) > 1 else None


def _imports_between(sources: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
    """(subpackage, the subpackage it imports) for each of a subpackage's
    sources, every import counted, inside a function or for types only."""
    return {
        (subpackage, imported)
        for subpackage, source in sources
        for module in _imported_modules(source)
        if (imported := _subpackage(module)) is not None and imported != subpackage
    }


def _tangled(imports: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(a, b) for a, b in imports if a < b and (b, a) in imports}


def _package_sources() -> Iterator[tuple[str, str]]:
    for path in sorted(PACKAGE.rglob("*.py")):
        subpackage = path.relative_to(PACKAGE).parts[0].removesuffix(".py")
        yield subpackage, path.read_text()


def test_no_new_pair_of_subpackages_imports_each_other() -> None:
    tangled = _tangled(_imports_between(_package_sources()))

    assert not tangled - TANGLED, (
        f"newly tangled, each importing the other: {sorted(tangled - TANGLED)}"
    )
    assert not TANGLED - tangled, (
        f"untangled, so take them off TANGLED: {sorted(TANGLED - tangled)}"
    )


def test_the_shared_vocabulary_imports_nothing_else_of_the_simulator() -> None:
    imports = _imports_between(_package_sources())

    assert sorted(imported for subpackage, imported in imports if subpackage == "domain") == []


def test_the_simulator_imports_itself_by_absolute_names_which_the_check_reads() -> None:
    relative = [
        f"{path.relative_to(PACKAGE)}:{node.lineno}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ImportFrom) and node.level > 0
    ]

    assert relative == []


def test_the_check_finds_a_pair_whatever_the_import_looks_like() -> None:
    sources = [
        ("climate", "def f() -> None:\n    from greenhouse_sim.solar.sky import Sky\n"),
        (
            "solar",
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    import greenhouse_sim.climate.day\n",
        ),
        ("weather", "from greenhouse_sim.solar import sky\nimport numpy\n"),
        ("domain", "from greenhouse_sim.domain.kinds import Kind\n"),
        ("biology", "from greenhouse_sim import weather\n"),
    ]

    imports = _imports_between(sources)

    assert imports == {
        ("biology", "weather"),
        ("climate", "solar"),
        ("solar", "climate"),
        ("weather", "solar"),
    }
    assert _tangled(imports) == {("climate", "solar")}
