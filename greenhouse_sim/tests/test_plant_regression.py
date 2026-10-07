"""Reference plants at several ages, held to what they were.

Each reference is one of the plant lab's plants on one run, summarised in
numbers a grower would recognise: how far it has developed, how tall it
stands, its trusses, flowers and fruits, and what has been done to it. A
change to how plants develop shows here as a changed summary, to be reviewed
and, if it is intended, written anew from `greenhouse_sim/`:

    python tests/test_plant_regression.py --update
"""

import json
import sys
from collections import Counter
from pathlib import Path

from greenhouse_sim.biology.tomato.organ.fruit import maturity
from greenhouse_sim.biology.tomato.organ.topology import (
    FlowerStage,
    FruitStage,
    LeafStage,
    Plant,
)
from greenhouse_sim.services import plants
from greenhouse_sim.services.plants import LabAction, LabRun

GOLDEN_FILE = Path(__file__).parent / "golden" / "plant_lab.json"
# Summaries are kept to this many decimals, enough to show any real change.
DECIMALS = 1

# A pruned and harvested plant: its lowest leaves off, its first truss cut,
# and its stem lowered over them.
_TENDED = tuple(
    LabAction(day=80, plant_id="p01", kind="remove_leaf", target=f"p01_n{rank:02d}_leaf")
    for rank in range(1, 9)
) + (
    LabAction(day=85, plant_id="p01", kind="harvest_truss", target="p01_t01"),
    LabAction(day=85, plant_id="p01", kind="lower_stem", target="8"),
)

REFERENCES: dict[str, tuple[LabRun, str]] = {
    "p01, day 0": (LabRun(day=0), "p01"),
    "p01, day 30": (LabRun(day=30), "p01"),
    "p01, day 60": (LabRun(day=60), "p01"),
    "p01, day 90": (LabRun(day=90), "p01"),
    "p02, day 60": (LabRun(day=60), "p02"),
    "p03, day 60": (LabRun(day=60), "p03"),
    "p01, day 90, seed 7": (LabRun(day=90, seed=7), "p01"),
    "p01, day 60, cool_dim": (LabRun(day=60, environment="cool_dim"), "p01"),
    "p01, day 60, warm_bright": (LabRun(day=60, environment="warm_bright"), "p01"),
    "p01, day 60, dry": (LabRun(day=60, environment="dry"), "p01"),
    "p01, day 90, tended": (LabRun(day=90, actions=_TENDED), "p01"),
}


def _round(value: float) -> float:
    return round(value, DECIMALS)


def summary(plant: Plant) -> dict[str, object]:
    """A plant in numbers a grower would recognise."""
    phytomers = plant.stem.phytomers
    standing = phytomers[plant.laid_internodes :]
    leaves = [p.leaf for p in phytomers]
    flowers = [f for p in phytomers if p.truss is not None for f in p.truss.flowers]
    fruits = [f.fruit for f in flowers if f.fruit is not None]
    on_plant = [f for f in fruits if f.stage == FruitStage.ATTACHED]
    return {
        "thermal_time_cd": _round(plant.thermal_time),
        "phytomers": len(phytomers),
        "laid_internodes": plant.laid_internodes,
        "standing_height_cm": _round(sum(p.internode.length_cm for p in standing)),
        "leaf_length_cm": _round(
            sum(leaf.length_cm for leaf in leaves if leaf.stage != LeafStage.REMOVED)
        ),
        "leaves_removed": sum(leaf.stage == LeafStage.REMOVED for leaf in leaves),
        "trusses": sum(p.truss is not None for p in phytomers),
        "flowers": dict(sorted(Counter(f.stage.value for f in flowers).items())),
        "fruits_on_plant": dict(
            sorted(Counter(maturity(f.ripeness).value for f in on_plant).items())
        ),
        "fruits_aborted": sum(f.stage == FruitStage.ABORTED for f in fruits),
        "fruits_harvested": sum(f.stage == FruitStage.HARVESTED for f in fruits),
        "fruit_on_plant_g": _round(sum(f.mass_g for f in on_plant)),
        "harvested_g": _round(sum(event.harvested_g for event in plant.history)),
        "events": [event.note for event in plant.history],
        "open_flowers": sum(f.stage == FlowerStage.OPEN for f in flowers),
    }


def _summaries() -> dict[str, dict[str, object]]:
    return {
        name: summary(plants.structure(run, plant_id))
        for name, (run, plant_id) in REFERENCES.items()
    }


def test_the_reference_plants_are_as_they_were() -> None:
    golden = json.loads(GOLDEN_FILE.read_text())
    now = json.loads(json.dumps(_summaries()))

    assert now.keys() == golden.keys()
    for name in golden:
        assert now[name] == golden[name], (
            f"{name} has changed; if that is intended, run "
            "python tests/test_plant_regression.py --update"
        )


def test_the_references_cover_ages_plants_seeds_environments_and_actions() -> None:
    golden = json.loads(GOLDEN_FILE.read_text())
    tended = golden["p01, day 90, tended"]

    assert golden["p01, day 0"]["trusses"] == 0
    assert golden["p01, day 90"]["fruits_on_plant"].get("red", 0) > 0
    assert (
        golden["p01, day 60, warm_bright"]["phytomers"]
        > golden["p01, day 60, cool_dim"]["phytomers"]
    )
    assert tended["laid_internodes"] == 8 and tended["harvested_g"] > 0


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit("usage: python tests/test_plant_regression.py --update")
    GOLDEN_FILE.write_text(json.dumps(_summaries(), indent=2) + "\n")
    print("wrote", GOLDEN_FILE)
