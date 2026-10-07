"""The simulator's shared vocabulary lives in `greenhouse_sim.domain`, which
depends on nothing else of the simulator; any kind, category or stage that
more than one of its packages uses lives there too, except a contract's own
vocabulary, which stays with its contract."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "greenhouse_sim"
DOMAIN = "domain"
ENUM_BASES = frozenset({"Enum", "StrEnum", "IntEnum"})
# A contract's vocabulary, shared by what speaks it: the scene's entity kinds,
# which the scene contract publishes, and a live run's commands, which its
# service takes and its API reads.
CONTRACTS = frozenset({"SceneEntityKind", "LiveCommand"})


def _modules() -> dict[Path, ast.Module]:
    return {path: ast.parse(path.read_text()) for path in PACKAGE.rglob("*.py")}


def _area(path: Path) -> str:
    """The part of the simulator a module belongs to: its top-level
    subpackage, or the module itself for one at the top."""
    return path.relative_to(PACKAGE).parts[0].removesuffix(".py")


def _enums(modules: dict[Path, ast.Module]) -> dict[str, str]:
    """Every enum defined in the simulator, by name, with the area that
    defines it."""
    return {
        node.name: _area(path)
        for path, tree in modules.items()
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id in ENUM_BASES for base in node.bases)
    }


def _imports(tree: ast.Module) -> list[tuple[str, list[str]]]:
    return [
        (node.module, [alias.name for alias in node.names])
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    ]


def test_the_domain_depends_on_nothing_else_of_the_simulator() -> None:
    for path, tree in _modules().items():
        if _area(path) != DOMAIN:
            continue
        for module, _ in _imports(tree):
            assert not module.startswith("greenhouse_sim.") or module.startswith(
                "greenhouse_sim.domain"
            ), f"{path.name} imports {module}"


def test_every_kind_shared_between_parts_of_the_simulator_lives_in_the_domain() -> None:
    modules = _modules()
    enums = _enums(modules)
    shared_outside = sorted(
        f"{path.relative_to(PACKAGE)} imports {name} from {enums[name]}"
        for path, tree in modules.items()
        for _, names in _imports(tree)
        for name in names
        if name in enums and enums[name] not in {DOMAIN, _area(path)} and name not in CONTRACTS
    )

    assert shared_outside == []


def test_the_check_sees_the_domains_kinds_and_a_contracts() -> None:
    enums = _enums(_modules())

    assert enums["OrganKind"] == enums["OpeningKind"] == enums["FruitStatus"] == DOMAIN
    assert enums["SceneEntityKind"] == "scene"
