"""Only the plant model reads the values it keeps for itself.

The simple tomato model keeps how it grows a plant apart from what the plant
is (`greenhouse_sim.biology.tomato.simple.state`): a plant's vigour and water
stress, each fruit's drawn target size and ripening day. A sensor, an
action, ground truth or an evaluation that read them would depend on one
model's internals, and would break or silently change meaning when another
model replaces it. So outside the model itself, only the run's simple crop
(`core/simple_crop.py`), which keeps them beside each plant, may import
them.
"""

import ast
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "greenhouse_sim"
STATE_MODULE = "greenhouse_sim.biology.tomato.simple.state"
ALLOWED = (
    "biology/tomato/simple/",
    "core/simple_crop.py",
)


def _touches_model_state(source: str) -> list[int]:
    """Line numbers that import the model's state types."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module == STATE_MODULE
    ]


def test_only_the_plant_model_and_its_rung_touch_its_state() -> None:
    offenders = [
        f"  greenhouse_sim/{relative}:{lineno}"
        for path in sorted(PACKAGE.rglob("*.py"))
        if not (relative := path.relative_to(PACKAGE).as_posix()).startswith(ALLOWED)
        for lineno in _touches_model_state(path.read_text())
    ]
    assert not offenders, "the plant model's own state is read from:\n" + "\n".join(offenders)


def test_the_boundary_check_can_fail() -> None:
    source = (
        "import greenhouse_sim\n"
        "from greenhouse_sim.biology.tomato.simple.state import SimpleTomatoState\n"
    )

    assert _touches_model_state(source) == [2]
