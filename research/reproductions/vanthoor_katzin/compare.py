"""Compares this implementation with the reference's outputs.

    python -m research.reproductions.vanthoor_katzin.compare

It checks the drivers against the manifest's checksum, then makes the
manifest's three comparisons, each against the reference's kept output
(`reference/`, made by `reference/run_reference.py`):

- the rates: the six states' rates of change, at the same moments and
  states, with no solver between;
- the run with each of the manifest's two solvers, `defaults` and
  `converged`: each output at each hourly moment, the six states, the leaf
  area index and the fruit harvested, accumulated alike from both rates.

It prints each output's largest difference, as a share of what its
tolerance allows, and each run's time. It fails if a difference lies
beyond its tolerance in the rates or the converged run. The defaults'
comparison is reported, not held: their answer moves beyond the
tolerances when the reference's own tolerance moves by a part in 10⁷
(README.md).
"""

import csv
import hashlib
import itertools
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

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


def drivers(path: Path, sha256: str) -> Drivers:
    """The drivers, refused if they are not the ones the manifest pins."""
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != sha256:
        raise ValueError(f"the drivers' sha256 is {found}, not {sha256}")
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    return Drivers(
        times=[float(row["Time"]) for row in rows],
        t_can=[float(row["tCan"]) for row in rows],
        par_gh=[float(row["parGh"]) for row in rows],
        co2_ppm=[float(row["co2InPpm"]) for row in rows],
    )


def _pinned_drivers(m: dict[str, Any]) -> Drivers:
    return drivers(HERE / m["drivers"]["file"], m["drivers"]["sha256"])


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
        key=lambda each: each.absolute / each.allowed,
    )


def compare_run(solver: str) -> tuple[list[Difference], float]:
    """Each output's largest difference from the reference's run with the
    same solver, over its moments, and this implementation's run's time
    (s)."""
    m = manifest()
    moments, mine, took = ours(solver)
    their_moments, theirs = reference(
        HERE / m["solving"]["solvers"][solver]["reference_output"], float(m["output_step_s"])
    )
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


def main() -> int:
    rates = compare_rates()
    print("The rates, at the same moments and states:")
    _report(rates)
    held = list(rates)
    for solver in manifest()["solving"]["solvers"]:
        differences, took = compare_run(solver)
        role = "held" if solver == HELD else "reported, not held"
        print(f"The run with the {solver} solver ({role}; ours took {took:.1f} s):")
        _report(differences)
        if solver == HELD:
            held += differences
    return 0 if all(each.within for each in held) else 1


if __name__ == "__main__":
    sys.exit(main())
