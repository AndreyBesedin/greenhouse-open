"""greenhouse-sim's public API: every name callers may import, and from where.

These paths are stable (decision 0011). Running a simulation goes through
short top-level modules such as `greenhouse_sim.engine` and
`greenhouse_sim.world`, which stay put while the implementation behind them
moves between domain subpackages. Writing or composing a model goes through
the contracts and the simple models; looking at a simulation goes through the
geometry and scene types. Removing or moving any of these is a breaking
change.

Everything else in the package is internal and may move without notice, so
this package's own tests import it from wherever it currently lives.
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
        "PlantModelState",
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
    # Writing or composing models.
    "greenhouse_sim.biology.contract": ("PlantModel",),
    "greenhouse_sim.environment.contract": ("EnvironmentModel",),
    "greenhouse_sim.sensors.contract": ("SensorModel",),
    "greenhouse_sim.biology.tomato.simple.model": ("SimpleTomatoModel",),
    "greenhouse_sim.environment.simple": ("SimpleEnvironmentModel",),
    "greenhouse_sim.sensors.generation": ("SimpleSensorModel",),
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
        "scene_snapshot",
    ),
}


@pytest.mark.parametrize(
    ("module", "name"),
    [(module, name) for module, names in PUBLIC_IMPORTS.items() for name in names],
)
def test_a_public_import_path_resolves(module: str, name: str) -> None:
    assert hasattr(importlib.import_module(module), name), f"from {module} import {name}"
