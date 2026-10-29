"""greenhouse-sim's public API: every name callers may import, and from where.

These paths are stable (decision 0011). Describing a simulation goes through
short top-level modules such as `greenhouse_sim.scenarios` and
`greenhouse_sim.world`, which stay put while the implementation behind them
moves between domain subpackages; scoring one goes through its ground truth;
looking at one goes through the geometry and scene types. Removing or moving
any of these is a breaking change.

Everything else in the package is internal and may move without notice, so
this package's own tests import it from wherever it currently lives.
"""

import importlib

import pytest

PUBLIC_IMPORTS: dict[str, tuple[str, ...]] = {
    "greenhouse_sim.scenarios": ("SCENARIO_REGISTRY", "ScenarioConfig"),
    "greenhouse_sim.scenarios.config": ("ScenarioConfig",),
    "greenhouse_sim.world": (
        "Fruit",
        "FruitStatus",
        "PlantWorld",
        "RipenessStage",
        "Truss",
        "TrussStage",
    ),
    "greenhouse_sim.ground_truth": ("GroundTruth", "TrueReading", "ground_truth"),
    "greenhouse_sim.evaluation.observation_accuracy": (
        "AccuracyByType",
        "AccuracyReport",
        "observation_accuracy",
    ),
    # Looking at a simulation.
    "greenhouse_sim.world.envelope": ("Envelope",),
    "greenhouse_sim.world.geometry": (
        "Axes",
        "Box",
        "Cylinder",
        "Plane",
        "Quaternion",
        "Shape",
        "Transform",
        "Vector3",
    ),
    "greenhouse_sim.scene.snapshot": (
        "Color",
        "SceneEntity",
        "SceneEntityKind",
        "SceneSnapshot",
        "greenhouse_scene",
    ),
}


@pytest.mark.parametrize(
    ("module", "name"),
    [(module, name) for module, names in PUBLIC_IMPORTS.items() for name in names],
)
def test_a_public_import_path_resolves(module: str, name: str) -> None:
    assert hasattr(importlib.import_module(module), name), f"from {module} import {name}"


# Removed: the engine's actions and its executor (P13.9), since a policy acts
# on the run, through its gateway, as a person in the viewer does (decision
# 0046); then the engine's day itself, its world, its model contracts, its
# simple models and its checkpoints, since the run is the one simulator
# (decision 0059).
REMOVED_MODULES = (
    "greenhouse_sim.actions",
    "greenhouse_sim.executor",
    "greenhouse_sim.engine",
    "greenhouse_sim.core.engine",
    "greenhouse_sim.world_builder",
    "greenhouse_sim.checkpoints",
    "greenhouse_sim.core.checkpoints",
    "greenhouse_sim.biology.contract",
    "greenhouse_sim.biology.tomato.simple.model",
    "greenhouse_sim.environment",
    "greenhouse_sim.sensors.contract",
    "greenhouse_sim.sensors.generation",
)
REMOVED_NAMES = {
    "greenhouse_sim.world": ("GreenhouseEnvironment", "GreenhouseWorld", "PlantModelState"),
    "greenhouse_sim.scene.snapshot": ("scene_snapshot",),
}


@pytest.mark.parametrize("module", REMOVED_MODULES)
def test_a_removed_module_does_not_come_back(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.parametrize(
    ("module", "name"),
    [(module, name) for module, names in REMOVED_NAMES.items() for name in names],
)
def test_a_removed_name_does_not_come_back(module: str, name: str) -> None:
    assert not hasattr(importlib.import_module(module), name), f"from {module} import {name}"
