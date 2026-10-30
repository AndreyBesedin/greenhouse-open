"""A published model reproduced stays reproduced (decision 0060, milestone A).

Each reproduction under `research/reproductions/` holds an implementation
written on its own, the reference implementation's output on the same
drivers, and a manifest of what both ran with. This holds the
implementation to the reference within the manifest's tolerances, so that
a change to either is seen: Reduced-State TOMGRO on every state and every
day; Vanthoor's model on its rates at the same states, and on every output
at every hour of a run with the manifest's converged solver.
"""

import copy
import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from research.reproductions.reduced_tomgro import compare as tomgro
from research.reproductions.reduced_tomgro.model import Hour, State, run
from research.reproductions.vanthoor_katzin import compare as vanthoor
from research.reproductions.vanthoor_katzin.drivers import csv_text
from research.reproductions.vanthoor_katzin.model import STATES as VANTHOOR_STATES
from research.reproductions.vanthoor_katzin.model import derivatives


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


def test_vanthoor_katzin_rates_agree_with_its_reference_at_the_same_states() -> None:
    differences = vanthoor.compare_rates()

    assert [each.output for each in differences] == [f"rate of {name}" for name in VANTHOOR_STATES]
    assert all(each.within for each in differences), differences


def test_the_rates_see_a_parameter_moved_by_a_millionth(monkeypatch: pytest.MonkeyPatch) -> None:
    moved = copy.deepcopy(vanthoor.manifest())
    moved["parameters"]["j25LeafMax"]["value"] *= 1 + 1e-6
    monkeypatch.setattr(vanthoor, "manifest", lambda: moved)

    assert not all(each.within for each in vanthoor.compare_rates())


def test_a_rate_that_is_not_a_number_is_beyond_its_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As for Reduced-State TOMGRO: the buffer's rate gone to NaN from the
    60th point is seen."""
    worked_out = 0

    def gone_to_nan(
        state: Sequence[float],
        t_can: float,
        par_gh: float,
        co2_ppm: float,
        p: Mapping[str, float],
    ) -> list[float]:
        nonlocal worked_out
        worked_out += 1
        rates = derivatives(state, t_can, par_gh, co2_ppm, p)
        return [math.nan, *rates[1:]] if worked_out > 60 else rates

    monkeypatch.setattr(vanthoor, "derivatives", gone_to_nan)

    buffer = next(each for each in vanthoor.compare_rates() if each.output == "rate of cBuf")
    assert math.isnan(buffer.absolute)
    assert not buffer.within


@pytest.mark.slow
def test_vanthoor_katzin_agrees_with_its_reference_when_both_are_converged() -> None:
    """About ten seconds: the solver's tolerances are tight."""
    differences, _ = vanthoor.compare_run(vanthoor.HELD)

    assert [each.output for each in differences] == list(vanthoor.COMPARED)
    assert all(each.within for each in differences), differences


def test_vanthoor_katzin_drivers_are_made_as_the_manifest_pins_them() -> None:
    """They are made, not committed (decision 0063, rule 2), and the
    reference read them from a file: they must come out byte for byte, on
    every platform this runs on."""
    made = csv_text().encode()

    assert hashlib.sha256(made).hexdigest() == vanthoor.manifest()["drivers"]["sha256"]


def test_vanthoor_katzin_refuses_drivers_other_than_the_pinned_ones() -> None:
    changed = csv_text().encode().replace(b"520.000000000000", b"521.000000000000", 1)

    with pytest.raises(ValueError, match="sha256"):
        vanthoor.drivers(changed, vanthoor.manifest()["drivers"]["sha256"])
