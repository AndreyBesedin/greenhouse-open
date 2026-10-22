"""The Ruff rules are one set. The root's `ruff.toml` lints the root's
tests, scripts and tools, and each package's `pyproject.toml` its own
directory; they say the same, so that a rule family turned on is on
everywhere (`AUDIT.11`)."""

import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("greenhouse_protocol", "greenhouse_sim", "greenhouse_adapters")


def _root_settings() -> dict[str, Any]:
    return tomllib.loads((ROOT / "ruff.toml").read_text())


@pytest.mark.parametrize("package", PACKAGES)
def test_each_package_lints_as_the_root_does(package: str) -> None:
    root = _root_settings()
    own = tomllib.loads((ROOT / package / "pyproject.toml").read_text())["tool"]["ruff"]

    assert own["line-length"] == root["line-length"]
    assert own["target-version"] == root["target-version"]
    assert own["lint"] == root["lint"]
