"""Check that every API is only an interface to its services.

An API (a package's `api` subpackage) reaches the rest of its package only
through that package's services (its `services` subpackage), and services
never know how they are reached: they import neither the API nor a transport
(see docs/engineering.md, "APIs", and decision 0021). This finds the imports
that break either rule, in every package of the repository, so a new API
falls under it as soon as it exists.

    python scripts/check_api_layers.py           # every package's API and services
    python scripts/check_api_layers.py FILE ...  # only these files
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")
API = "api"
SERVICES = "services"
# Modules that carry requests and responses: a service never needs them.
TRANSPORTS = frozenset(
    {"http", "socketserver", "wsgiref", "fastapi", "starlette", "flask", "aiohttp"}
)


def layer_sources() -> list[Path]:
    """Every module of every package's API and services."""
    return sorted(
        path
        for package in PACKAGES
        for layer in (API, SERVICES)
        for path in (ROOT / package / package / layer).rglob("*.py")
    )


def _layer(path: Path) -> tuple[str, str] | None:
    """The package and layer a module belongs to, if it is in one."""
    parts = path.resolve().relative_to(ROOT).parts
    if len(parts) >= 3 and parts[0] in PACKAGES and parts[1] == parts[0]:
        if parts[2] in (API, SERVICES):
            return parts[0], parts[2]
    return None


def _imported(source: str) -> list[tuple[int, str]]:
    """The line and module name of every absolute import in a module."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
    return found


def layer_violations(source: str, package: str, layer: str) -> list[tuple[int, str]]:
    """The line and an explanation of every import in a module of `package`'s
    `layer` (`api` or `services`) that its layer may not make."""
    own = f"{package}.{API}"
    services = f"{package}.{SERVICES}"
    violations = []
    for line, name in _imported(source):
        top = name.split(".")[0]
        if layer == API:
            reaches_inward = top in PACKAGES and not (
                name == own
                or name.startswith(f"{own}.")
                or name == services
                or name.startswith(f"{services}.")
            )
            if reaches_inward:
                violations.append((line, f"the API imports {name}; it may reach only {services}"))
        elif name == own or name.startswith(f"{own}."):
            violations.append((line, f"a service imports {name}; services never know the API"))
        elif top in TRANSPORTS:
            violations.append((line, f"a service imports {name}; services know no transport"))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="default: every API and service")
    args = parser.parse_args(argv)
    files: list[Path] = args.files or layer_sources()

    findings = []
    for path in files:
        where = _layer(path)
        if where is None:
            continue
        package, layer = where
        findings += [
            f"{path}:{line}: {why}"
            for line, why in layer_violations(path.read_text(), package, layer)
        ]
    for finding in findings:
        print(finding)
    if findings:
        print("\nSee docs/engineering.md, 'APIs'.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
