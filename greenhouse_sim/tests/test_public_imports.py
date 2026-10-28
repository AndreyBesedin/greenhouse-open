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
    "greenhouse_sim.engine": ("SimulationEngine", "SimulationStep"),
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
    "greenhouse_sim.checkpoints": ("InMemoryWorldCheckpoints", "WorldCheckpoints"),
    "greenhouse_sim.ground_truth": ("GroundTruth", "TrueReading", "ground_truth"),
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
        "greenhouse_scene",
        "scene_snapshot",
    ),
}


@pytest.mark.parametrize(
    ("module", "name"),
    [(module, name) for module, names in PUBLIC_IMPORTS.items() for name in names],
)
def test_a_public_import_path_resolves(module: str, name: str) -> None:
    assert hasattr(importlib.import_module(module), name), f"from {module} import {name}"


# The engine's actions and its executor, removed (P13.9): a policy acts on the
# run, through its gateway, as a person in the viewer does (decision 0046).
REMOVED_MODULES = ("greenhouse_sim.actions", "greenhouse_sim.executor")
REMOVED_NAMES = {"greenhouse_sim.engine": ("ActionExecution",)}


@pytest.mark.parametrize("module", REMOVED_MODULES)
def test_a_removed_module_does_not_come_back(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_the_engine_takes_no_actions() -> None:
    engine = importlib.import_module("greenhouse_sim.engine")

    for module, names in REMOVED_NAMES.items():
        assert not any(hasattr(importlib.import_module(module), name) for name in names)
    assert not hasattr(engine.SimulationEngine, "apply_actions")
