"""Every API is only an interface to its services (decision 0021).

The check lives in `scripts/check_api_layers.py`, which also runs as a
pre-commit hook on staged files. Running it here means CI enforces it too,
for every package's API and services, present and future.
"""

import pytest

from scripts.check_api_layers import ROOT, layer_sources, layer_violations, main


def test_every_api_reaches_its_package_only_through_its_services() -> None:
    assert main([]) == 0


def test_the_check_covers_the_simulators_api_and_services() -> None:
    covered = {path.relative_to(ROOT).as_posix() for path in layer_sources()}

    assert "greenhouse_sim/greenhouse_sim/api/routes.py" in covered
    assert "greenhouse_sim/greenhouse_sim/services/scenarios.py" in covered


@pytest.mark.parametrize(
    ("source", "layer", "expected"),
    [
        # The API: its own modules, its services, the standard library and
        # third-party libraries; nothing else of its package.
        ("from greenhouse_sim.services import scenarios\n", "api", []),
        ("from greenhouse_sim.services.errors import NotFound\n", "api", []),
        ("from greenhouse_sim.api.routes import respond\n", "api", []),
        ("from http import HTTPStatus\nfrom pydantic import BaseModel\n", "api", []),
        ("from greenhouse_sim.scenarios import SCENARIO_REGISTRY\n", "api", [1]),
        ("import greenhouse_sim.world.layout\n", "api", [1]),
        ("x = 1\nfrom greenhouse_protocol.action import Action\n", "api", [2]),
        # Services: anything but the API and a transport.
        ("from greenhouse_sim.world.layout import Layout\n", "services", []),
        ("from greenhouse_sim.api.routes import Response\n", "services", [1]),
        ("from http import HTTPStatus\n", "services", [1]),
        ("import http.server\n", "services", [1]),
        ("from fastapi import FastAPI\n", "services", [1]),
    ],
)
def test_what_each_layer_may_import(source: str, layer: str, expected: list[int]) -> None:
    lines = [line for line, _ in layer_violations(source, "greenhouse_sim", layer)]

    assert lines == expected
