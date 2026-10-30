"""Compares this implementation with the reference's outputs.

    python -m research.reproductions.vanthoor_katzin.compare [<defaults.csv>]

It makes the drivers and checks them against the manifest's checksum, then
makes the manifest's comparisons against the reference's kept outputs
(`reference/`, made by `reference/run_reference.py`):

- the rates: the six states' rates of change, at the same moments and
  states, with no solver between;
- the run with the manifest's `converged` solver: each output at each
  hourly moment, the six states, the leaf area index and the fruit
  harvested, accumulated alike from both rates.

Given the reference's run with its `defaults` solver, which
`run_reference.py` writes into its scratch folder, it compares that run
too. It prints each output's largest difference, as a share of what its
tolerance allows, and each run's time. It fails if a difference lies
beyond its tolerance in the rates or the converged run. The defaults'
comparison is reported, not held: their answer moves beyond the
tolerances when the reference's own tolerance moves by a part in 10⁷
(README.md). No test compares against it, so its output is not kept
(decision 0063).
"""

import csv
import hashlib
import io
import itertools
import json
import math
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from research.reproductions.vanthoor_katzin.drivers import csv_text
from research.reproductions.vanthoor_katzin.model import (
    STATES,
    Drivers,
    Outputs,
    Solver,
    derivatives,
    run,
)

HERE: Final = Path(__file__).resolve().parent

COMPARED: Final = (*STATES, "lai", "harvested_fruit")
HELD: Final = "converged"
REPORTED: Final = "defaults"


@dataclass(frozen=True)
class Difference:
    """An output's largest difference from the reference, over every moment,
    as a share of what its tolerance allows there: the moment (s), the
    absolute difference, the reference's value and what is allowed."""

    output: str
    moment_s: float
    absolute: float
    reference: float
    allowed: float

    @property
    def within(self) -> bool:
        return self.absolute <= self.allowed


def manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    return loaded


def drivers(content: bytes, sha256: str) -> Drivers:
    """The drivers, refused if they are not the ones the manifest pins."""
    found = hashlib.sha256(content).hexdigest()
    if found != sha256:
        raise ValueError(f"the drivers' sha256 is {found}, not {sha256}")
    rows = list(csv.DictReader(io.StringIO(content.decode())))
    return Drivers(
        times=[float(row["Time"]) for row in rows],
        t_can=[float(row["tCan"]) for row in rows],
        par_gh=[float(row["parGh"]) for row in rows],
        co2_ppm=[float(row["co2InPpm"]) for row in rows],
    )


def _pinned_drivers(m: dict[str, Any]) -> Drivers:
    return drivers(csv_text().encode(), m["drivers"]["sha256"])


def _parameters(m: dict[str, Any]) -> dict[str, float]:
    return {name: float(entry["value"]) for name, entry in m["parameters"].items()}


def harvested(rates: Sequence[float], step_s: float) -> list[float]:
    """The fruit harvested since the first moment (mg CH₂O m⁻²), its rate
    accumulated over the moments by the trapezoidal rule."""
    total = [0.0]
    for before, after in itertools.pairwise(rates):
        total.append(total[-1] + (before + after) / 2 * step_s)
    return total


def _outputs(found: Outputs, step_s: float) -> dict[str, list[float]]:
    return {
        **found.states,
        "lai": found.lai,
        "harvested_fruit": harvested(found.fruit_harvest, step_s),
    }


def _rows(path: Path) -> list[dict[str, float]]:
    with path.open(newline="") as file:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(file)]


def reference(path: Path, step_s: float) -> tuple[list[float], dict[str, list[float]]]:
    """The reference's moments and outputs from one of its runs."""
    rows = _rows(path)
    found = Outputs(
        times=[row["Time"] for row in rows],
        states={name: [row[name] for row in rows] for name in STATES},
        lai=[row["lai"] for row in rows],
        fruit_harvest=[row["mcFruitHar"] for row in rows],
    )
    return found.times, _outputs(found, step_s)


def ours(solver: str) -> tuple[list[float], dict[str, list[float]], float]:
    """This implementation's moments and outputs with one of the manifest's
    solvers, and its run's time (s)."""
    m = manifest()
    settings = m["solving"]["solvers"][solver]
    initial = {name: float(entry["value"]) for name, entry in m["initial_state"].items()}
    started = time.perf_counter()
    found = run(
        _pinned_drivers(m),
        initial,
        _parameters(m),
        end_s=float(m["season_s"]),
        output_step_s=float(m["output_step_s"]),
        solver=Solver(
            method=settings["method"],
            max_step=float(settings["max_step"]),
            atol=float(settings["atol"]),
            rtol=float(settings["rtol"]),
        ),
    )
    took = time.perf_counter() - started
    return found.times, _outputs(found, float(m["output_step_s"])), took


def _how_far(difference: Difference) -> float:
    """How far a difference goes into what is allowed, past it beyond 1. An
    output that is not a number is the furthest: NaN compares false with
    everything, so `max` would pass over it."""
    ratio = difference.absolute / difference.allowed
    return math.inf if math.isnan(ratio) else ratio


def _largest(
    name: str,
    moments: Sequence[float],
    mine: Sequence[float],
    theirs: Sequence[float],
    *,
    relative: float,
    absolute: float,
) -> Difference:
    return max(
        (
            Difference(
                output=name,
                moment_s=moment,
                absolute=abs(value - other),
                reference=other,
                allowed=max(absolute, relative * abs(other)),
            )
            for moment, value, other in zip(moments, mine, theirs, strict=True)
        ),
        key=_how_far,
    )


def compare_run(solver: str, output: Path | None = None) -> tuple[list[Difference], float]:
    """Each output's largest difference from the reference's run with the
    same solver, its kept output or `output`, over its moments, and this
    implementation's run's time (s)."""
    m = manifest()
    moments, mine, took = ours(solver)
    if output is None:
        output = HERE / m["solving"]["solvers"][solver]["reference_output"]
    their_moments, theirs = reference(output, float(m["output_step_s"]))
    if moments != their_moments:
        raise ValueError("this implementation's output moments are not the reference's")
    tolerances = m["compared"]["tolerances"]
    return [
        _largest(
            name,
            moments,
            mine[name],
            theirs[name],
            relative=float(tolerances[name]["relative"]),
            absolute=float(tolerances[name]["absolute"]),
        )
        for name in COMPARED
    ], took


def compare_rates() -> list[Difference]:
    """Each state's largest rate difference from the reference's, at the
    same moments and states."""
    m = manifest()
    forcing = _pinned_drivers(m)
    parameters = _parameters(m)
    rows = _rows(HERE / m["rates"]["reference_output"])
    moments = [row["Time"] for row in rows]
    mine = [
        derivatives([row[name] for name in STATES], *forcing.at(row["Time"]), parameters)
        for row in rows
    ]
    tolerances = m["rates"]["tolerances"]
    return [
        _largest(
            f"rate of {name}",
            moments,
            [rates[index] for rates in mine],
            [row[f"rate_{name}"] for row in rows],
            relative=float(tolerances["relative"]),
            absolute=float(tolerances["absolute"]),
        )
        for index, name in enumerate(STATES)
    ]


def _report(differences: Sequence[Difference]) -> None:
    for each in differences:
        verdict = "within" if each.within else "BEYOND"
        print(
            f"  {each.output:>15}: {each.absolute:.3e} at {each.moment_s / 86400:8.3f} d, "
            f"{each.absolute / each.allowed:.3g} of the {each.allowed:.3e} allowed "
            f"(reference {each.reference:.6g}): {verdict}"
        )


def main(defaults: Path | None) -> int:
    rates = compare_rates()
    print("The rates, at the same moments and states:")
    _report(rates)
    differences, took = compare_run(HELD)
    print(f"The run with the {HELD} solver (held; ours took {took:.1f} s):")
    _report(differences)
    if defaults is not None:
        reported, took = compare_run(REPORTED, defaults)
        print(f"The run with the {REPORTED} solver (reported, not held; ours took {took:.1f} s):")
        _report(reported)
    return 0 if all(each.within for each in [*rates, *differences]) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else None))
