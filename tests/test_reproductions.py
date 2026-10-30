"""A published model reproduced stays reproduced (decision 0060, milestone A).

Each reproduction under `research/reproductions/` holds an implementation
written on its own, the reference implementation's output on the same
drivers, and a manifest of what both ran with. This holds the
implementation to the reference within the manifest's tolerances, on every
state and every day, so that a change to either is seen.
"""

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from research.reproductions.reduced_tomgro import compare as tomgro
from research.reproductions.reduced_tomgro.model import Hour, State, run


def test_reduced_tomgro_agrees_with_its_reference_on_every_state_and_day() -> None:
    differences = tomgro.compare()

    assert [each.state for each in differences] == list(tomgro.STATES)
    assert all(each.within for each in differences), differences


def test_the_comparison_sees_a_parameter_moved_by_a_millionth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A check that cannot fail is worth nothing."""
    moved = copy.deepcopy(tomgro.manifest())
    parameters = moved["parameters"]
    assert isinstance(parameters, dict)
    parameters["Qe"]["value"] *= 1 + 1e-6
    monkeypatch.setattr(tomgro, "manifest", lambda: moved)

    assert not all(each.within for each in tomgro.compare())


def test_a_state_that_is_not_a_number_is_beyond_its_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NaN compares false with everything, so the largest difference must
    not pass over it: the dry weight gone to NaN from day 60 is seen."""

    def gone_to_nan(
        days: Sequence[Sequence[Hour]],
        initial: State,
        p: Mapping[str, float],
        i: Mapping[str, float],
    ) -> list[State]:
        states = run(days, initial, p, i)
        return [*states[:60], *(replace(each, w=math.nan) for each in states[60:])]

    monkeypatch.setattr(tomgro, "run", gone_to_nan)

    w = next(each for each in tomgro.compare() if each.state == "w")
    assert math.isnan(w.absolute)
    assert not w.within


def test_drivers_other_than_the_pinned_ones_are_refused(tmp_path: Path) -> None:
    pinned = tomgro.HERE / "drivers.csv"
    changed = tmp_path / "drivers.csv"
    changed.write_bytes(pinned.read_bytes().replace(b"520.000000000000", b"521.000000000000", 1))

    with pytest.raises(ValueError, match="sha256"):
        tomgro.drivers(changed, tomgro.manifest()["drivers"]["sha256"])  # type: ignore[index]
