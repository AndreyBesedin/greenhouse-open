"""Scenarios as manifests (P09.1).

`fixtures/scenarios_as_code.json` holds every scenario's configuration as
its Python module built it, before the scenarios became files: whatever
reads them now must build the same.
"""

import json
from pathlib import Path

import pytest

from greenhouse_sim.scenarios import SCENARIO_REGISTRY

AS_CODE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "scenarios_as_code.json").read_text()
)


def test_the_same_scenarios_are_registered() -> None:
    assert set(SCENARIO_REGISTRY) == set(AS_CODE)


@pytest.mark.parametrize("scenario_id", sorted(AS_CODE))
def test_every_scenario_is_configured_as_its_code_was(scenario_id: str) -> None:
    assert SCENARIO_REGISTRY[scenario_id].model_dump(mode="json") == AS_CODE[scenario_id]
