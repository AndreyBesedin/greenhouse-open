"""Tests that run OpenFOAM (marked `cfd`) run only when asked for, with
`pytest -m cfd`, and are skipped where OpenFOAM cannot run. Without OpenFOAM
installed they pull its container the first time, about 2 GB, so neither the
canonical checks nor the pre-push pass run them."""

import pytest

from greenhouse_sim.cfd import runner


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    asked = "cfd" in (config.getoption("markexpr") or "")
    unasked = pytest.mark.skip(reason="runs OpenFOAM: only with -m cfd")
    unavailable = pytest.mark.skip(reason="OpenFOAM is not installed, and Docker is not running")
    can_run: bool | None = None
    for item in items:
        if item.get_closest_marker("cfd") is None:
            continue
        if not asked:
            item.add_marker(unasked)
            continue
        if can_run is None:
            can_run = runner.available()
        if not can_run:
            item.add_marker(unavailable)
