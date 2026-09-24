"""Every example runs, on its own, and finishes cleanly.

Examples are documentation that can go stale silently; running them here
means a change that breaks one fails a build instead of a reader.
"""

import pathlib
import subprocess
import sys

import pytest

EXAMPLES = sorted((pathlib.Path(__file__).resolve().parents[1] / "examples").glob("*.py"))


def test_there_are_examples() -> None:
    assert len(EXAMPLES) >= 4


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.stem)
def test_an_example_runs(example: pathlib.Path) -> None:
    result = subprocess.run(
        [sys.executable, str(example)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "an example should show what it did"
