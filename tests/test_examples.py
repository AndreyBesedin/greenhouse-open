"""Every example runs, on its own, and finishes cleanly.

Examples are documentation that can go stale silently; running them here
means a change that breaks one fails a build instead of a reader. An
example is a numbered file. A module beside them without a number, such as
the policy example 06 makes from its settings, is one an example imports.
"""

import pathlib
import subprocess
import sys

import pytest

EXAMPLES = sorted(
    (pathlib.Path(__file__).resolve().parents[1] / "examples").glob("[0-9][0-9]_*.py")
)
# Examples that take about half a minute, left out of the fast checks: one
# starts the port's server and a policy of its own, and one runs eight
# episodes of an experiment.
SLOW = {"05_policy_in_its_own_process", "06_run_an_experiment"}


def test_there_are_examples() -> None:
    assert len(EXAMPLES) >= 4


@pytest.mark.parametrize(
    "example",
    [
        pytest.param(path, marks=pytest.mark.slow) if path.stem in SLOW else path
        for path in EXAMPLES
    ],
    ids=lambda path: path.stem,
)
def test_an_example_runs(example: pathlib.Path) -> None:
    result = subprocess.run(
        [sys.executable, str(example)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "an example should show what it did"
