"""The import paths callers rely on today.

The examples, this package's README and downstream applications import the
names below from these modules. As the package is reorganised into domain
subpackages, each path keeps resolving, through a re-export if its module
moves, until removing it is a deliberate, announced change.

Internal helpers that only this package's own tests reach into are not
listed: those tests are import-adjusted when the code they test moves.
"""

import importlib

import pytest

PUBLIC_IMPORTS: dict[str, tuple[str, ...]] = {
    "greenhouse_sim.engine": ("ActionExecution", "SimulationEngine", "SimulationStep"),
    "greenhouse_sim.scenarios": ("SCENARIO_REGISTRY", "ScenarioConfig"),
    "greenhouse_sim.scenarios.config": ("ScenarioConfig",),
    "greenhouse_sim.world": (
        "Fruit",
        "FruitStatus",
        "GreenhouseEnvironment",
        "GreenhouseWorld",
        "PlantWorld",
        "RipenessStage",
        "Truss",
        "TrussStage",
    ),
    "greenhouse_sim.world_builder": ("advance_world", "initialize_world"),
    "greenhouse_sim.executor": ("ActionExecutor", "SimulatedOperatorExecutor", "executor_for"),
    "greenhouse_sim.checkpoints": ("InMemoryWorldCheckpoints", "WorldCheckpoints"),
    "greenhouse_sim.ground_truth": ("GroundTruth", "PlantTruth", "ground_truth"),
    "greenhouse_sim.evaluation.observation_accuracy": (
        "AccuracyByType",
        "AccuracyReport",
        "observation_accuracy",
    ),
}


@pytest.mark.parametrize(
    ("module", "name"),
    [(module, name) for module, names in PUBLIC_IMPORTS.items() for name in names],
)
def test_a_public_import_path_resolves(module: str, name: str) -> None:
    assert hasattr(importlib.import_module(module), name), f"from {module} import {name}"
