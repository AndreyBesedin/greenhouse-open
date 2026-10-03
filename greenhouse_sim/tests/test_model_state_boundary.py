"""Only the plant model reads the values it keeps for itself.

`GreenhouseWorld.plant_model` holds how the simple tomato model generates the
world, not what the world is. A sensor, an action, ground truth or an
evaluation that read it would depend on one model's internals, and would
break or silently change meaning when another model replaces it. So outside
the model itself, only the module that composes the models and the world's
own definition may touch it.
"""

import ast
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "greenhouse_sim"
STATE_MODULE = "greenhouse_sim.biology.tomato.simple.state"
ALLOWED = (
    "biology/tomato/simple/",
    "world/state.py",
    "world_builder.py",
)


def _touches_model_state(source: str) -> list[int]:
    """Line numbers that read `plant_model` or import the model's state types."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == "plant_model":
            lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module == STATE_MODULE:
            lines.append(node.lineno)
    return lines


def test_only_the_plant_model_and_its_composition_touch_its_state() -> None:
    offenders = [
        f"  greenhouse_sim/{relative}:{lineno}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if not (relative := path.relative_to(PACKAGE).as_posix()).startswith(ALLOWED)
        for lineno in _touches_model_state(path.read_text())
    ]
    assert not offenders, "the plant model's own state is read from:\n" + "\n".join(offenders)


def test_the_boundary_check_can_fail() -> None:
    source = (
        "from greenhouse_sim.biology.tomato.simple.state import SimpleTomatoState\n"
        "stress = world.plant_model.plants['p1'].water_stress\n"
    )

    assert _touches_model_state(source) == [1, 2]
