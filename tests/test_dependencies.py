"""Each open package imports only what it declares.

A package here may import the standard library, itself, and the
distributions listed in its own `pyproject.toml` - nothing else. That one
rule keeps the open core publishable: an import of a package that is not a
declared dependency, including anything that only exists in some
application consuming these packages, fails here before it fails for a user who
installed the package on its own.
"""

import ast
import pathlib
import re
import sys
import tomllib

import pytest

OPEN = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")

# Distributions whose import name differs from their normalised name.
IMPORT_NAMES: dict[str, str] = {}


def _declared(package: str) -> set[str]:
    project = tomllib.loads((OPEN / package / "pyproject.toml").read_text())["project"]
    names = set()
    for requirement in project.get("dependencies", []):
        distribution = re.match(r"[A-Za-z0-9_.-]+", requirement)
        assert distribution, requirement
        normalised = distribution.group(0).lower().replace("-", "_")
        names.add(IMPORT_NAMES.get(normalised, normalised))
    return names


def _imports(package: str) -> set[tuple[str, int, str]]:
    found = set()
    for path in (OPEN / package / package).rglob("*.py"):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                found.add(
                    (
                        path.relative_to(OPEN).as_posix(),
                        node.lineno,
                        module.split(".")[0],
                    )
                )
    return found


@pytest.mark.parametrize("package", PACKAGES)
def test_a_package_imports_only_the_standard_library_itself_and_its_dependencies(
    package: str,
) -> None:
    allowed = {package, *_declared(package), *sys.stdlib_module_names}
    undeclared = sorted(item for item in _imports(package) if item[2] not in allowed)
    assert not undeclared, f"{package} imports undeclared packages:\n" + "\n".join(
        f"  {path}:{lineno} imports {name}" for path, lineno, name in undeclared
    )


def test_the_protocol_depends_on_no_other_open_package() -> None:
    """The protocol is what every other package builds on, so it builds on
    none of them."""
    assert not _declared("greenhouse_protocol") & set(PACKAGES)


def test_ground_truth_is_read_only_by_the_simulators_evaluation() -> None:
    """Ground truth leaves the simulator only through its evaluation
    interface, never into what a sensor would see."""
    readers = sorted(
        path
        for path, _, _ in _imports_with_modules("greenhouse_sim")
        if not path.startswith("greenhouse_sim/greenhouse_sim/evaluation/")
    )
    assert not readers, readers


def _imports_with_modules(package: str) -> set[tuple[str, int, str]]:
    """Like `_imports`, but only imports of the ground-truth module."""
    found = set()
    for path in (OPEN / package / package).rglob("*.py"):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("greenhouse_sim.ground_truth")
            ):
                found.add((path.relative_to(OPEN).as_posix(), node.lineno, node.module))
    return found
