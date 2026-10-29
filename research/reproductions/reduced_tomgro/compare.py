"""Compares this implementation with the reference's output.

    python -m research.reproductions.reduced_tomgro.compare

It checks the drivers against the manifest's checksum, runs `model.py` on
them with the manifest's parameters, inputs and initial state, and holds
each of the five states, on each day, to the reference's output
(`reference/output.csv`, made by `reference/run_reference.py`) within the
manifest's tolerances. It prints every state's largest difference, and
fails if any lies beyond its tolerance.
"""

import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Final

from research.reproductions.reduced_tomgro.model import Hour, State, run

HERE: Final = Path(__file__).resolve().parent

STATES: Final = ("n", "lai", "w", "wf", "wm")


@dataclass(frozen=True)
class Difference:
    """A state's largest difference from the reference, over every day: the
    day it lies on, the absolute difference, and the reference's value."""

    state: str
    day: int
    absolute: float
    reference: float
    allowed: float

    @property
    def within(self) -> bool:
        return self.absolute <= self.allowed


def manifest() -> dict[str, object]:
    loaded: dict[str, object] = json.loads((HERE / "manifest.json").read_text())
    return loaded


def _values(section: object) -> dict[str, float]:
    assert isinstance(section, dict)
    return {name: float(entry["value"]) for name, entry in section.items()}


def drivers(path: Path, sha256: str) -> list[list[Hour]]:
    """The drivers, day by day, refused if they are not the ones the
    manifest pins."""
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != sha256:
        raise ValueError(f"the drivers' sha256 is {found}, not {sha256}")
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    return [
        [
            Hour(
                hour=int(row["hour"]),
                temperature_c=float(row["tmean"]),
                ppfd=float(row["rad"]),
                co2_ppm=float(row["co2"]),
            )
            for row in day
        ]
        for _, day in groupby(rows, key=lambda row: int(row["dat"]))
    ]


def reference(path: Path) -> list[State]:
    with path.open(newline="") as file:
        return [
            State(**{name: float(row[name]) for name in STATES}) for row in csv.DictReader(file)
        ]


def compare() -> list[Difference]:
    """Each state's largest difference from the reference, over its days."""
    m = manifest()
    pinned = m["drivers"]
    assert isinstance(pinned, dict)
    days = drivers(HERE / str(pinned["file"]), str(pinned["sha256"]))
    initial = m["initial_state"]
    assert isinstance(initial, dict)
    ours = run(days, State(**initial), _values(m["parameters"]), _values(m["inputs"]))
    theirs = reference(HERE / str(m["reference_output"]))
    if len(ours) != len(theirs):
        raise ValueError(f"{len(ours)} days of ours, {len(theirs)} of the reference")
    tolerances = m["tolerances"]
    assert isinstance(tolerances, dict)
    relative, absolute = float(tolerances["relative"]), float(tolerances["absolute"])
    largest: list[Difference] = []
    for name in STATES:
        found = [
            Difference(
                state=name,
                day=day,
                absolute=abs(getattr(mine, name) - getattr(other, name)),
                reference=getattr(other, name),
                allowed=absolute + relative * abs(getattr(other, name)),
            )
            for day, (mine, other) in enumerate(zip(ours, theirs, strict=True))
        ]
        largest.append(max(found, key=lambda each: each.absolute / each.allowed))
    return largest


def main() -> int:
    differences = compare()
    for each in differences:
        verdict = "within" if each.within else "BEYOND"
        print(
            f"{each.state:>3}: largest difference {each.absolute:.3e} on day {each.day} "
            f"(reference {each.reference:.6g}, allowed {each.allowed:.3e}): {verdict}"
        )
    return 0 if all(each.within for each in differences) else 1


if __name__ == "__main__":
    sys.exit(main())
