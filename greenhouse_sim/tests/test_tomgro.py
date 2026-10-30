"""Reduced-State TOMGRO as the run grows it (P14.10, decision 0060): the
package's model agrees with the reference implementation on the
reproduction's own drivers, within the reproduction's tolerances, and its
parameters are the published set it reproduced
(`research/reproductions/reduced_tomgro`, milestone A)."""

import csv
import hashlib
import json
from itertools import groupby
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.biology.area_contract import HourDrivers, StepCourse
from greenhouse_sim.biology.tomato.tomgro.parameters import (
    INITIAL_STATE,
    TomgroParameters,
    TomgroState,
)
from greenhouse_sim.core.tomgro_crop import TomgroRung

REPRODUCTION: Final = (
    Path(__file__).resolve().parents[2] / "research" / "reproductions" / "reduced_tomgro"
)
STATES: Final = ("n", "lai", "w", "wf", "wm")
# The published symbols, as the reproduction's manifest names them, by the
# package's field.
SYMBOLS: Final = {
    "alpha_f": "alpha_F",
    "beta": "beta",
    "delta": "delta",
    "df_max": "DFmax",
    "e": "E",
    "k": "K",
    "k_f": "K_F",
    "m": "m",
    "n_b": "N_b",
    "n_ff": "N_FF",
    "n_max": "N_max",
    "p_1": "p_1",
    "q10": "Q10",
    "qe": "Qe",
    "rm": "rm",
    "sl_n1": "sl_N1",
    "sl_n2": "sl_N2",
    "sl_r": "sl_R",
    "t_crit": "T_crit",
    "tau1": "tau1",
    "tau2": "tau2",
    "tmax_pg": "tmaxPg",
    "tmin_fr_gr": "tmin_fr_gr",
    "t_slop": "TSlop",
    "v": "V",
    "v_max": "V_max",
}
INPUTS: Final = {"d": "D", "trgh": "TRGH", "lai_max": "LAI_max", "ro": "ro"}
# The temperature at which the reference's Qe would vary, which its
# implementation leaves out, as the package's model does.
UNUSED: Final = {"TQe"}


def _manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((REPRODUCTION / "manifest.json").read_text())
    return loaded


def _courses() -> list[StepCourse]:
    """The reproduction's drivers, day by day, checked against the sha256
    its manifest pins."""
    pinned = _manifest()["drivers"]
    path = REPRODUCTION / pinned["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pinned["sha256"]
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    return [
        StepCourse(
            hours=tuple(
                HourDrivers(
                    temperature_c=float(row["tmean"]),
                    par_above_umol_m2_s=float(row["rad"]),
                    co2_ppm=float(row["co2"]),
                )
                for row in day
            )
        )
        for _, day in groupby(rows, key=lambda row: int(row["dat"]))
    ]


def _reference() -> list[TomgroState]:
    with (REPRODUCTION / "reference" / "output.csv").open(newline="") as file:
        return [
            TomgroState(**{name: float(row[name]) for name in STATES})
            for row in csv.DictReader(file)
        ]


def test_its_parameters_and_its_start_are_the_published_ones() -> None:
    manifest = _manifest()
    parameters = TomgroParameters()

    assert set(SYMBOLS.values()) == set(manifest["parameters"]) - UNUSED
    for field, symbol in SYMBOLS.items():
        assert getattr(parameters, field) == manifest["parameters"][symbol]["value"], symbol
    assert set(INPUTS.values()) == set(manifest["inputs"])
    for field, symbol in INPUTS.items():
        assert getattr(parameters, field) == manifest["inputs"][symbol]["value"], symbol
    assert INITIAL_STATE.model_dump() == manifest["initial_state"]


def test_it_agrees_with_the_reference_on_every_state_every_day() -> None:
    """Within the reproduction's tolerances: |ours - reference| <=
    absolute + relative * |reference|."""
    tolerances = _manifest()["tolerances"]
    rung = TomgroRung(TomgroParameters(), canopy_height_m=2.0)
    reference = _reference()
    state = rung.planted()
    grown = [state]
    for course in _courses():
        state = rung.live_step(state, course)
        grown.append(state)

    assert len(grown) == len(reference)
    for day, (ours, theirs) in enumerate(zip(grown, reference, strict=True)):
        for name in STATES:
            expected = getattr(theirs, name)
            assert getattr(ours, name) == pytest.approx(
                expected, rel=tolerances["relative"], abs=tolerances["absolute"]
            ), f"{name} on day {day}"
    # A season's fruit, grown and matured.
    assert grown[-1].wf > 0.0 and grown[-1].wm > 0.0
