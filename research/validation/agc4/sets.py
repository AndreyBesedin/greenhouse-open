"""Decision 0076's calibrated parameters as crop parameter sets (decision
0077), so that a study cites each by its name, its version and its digest.

Each set is written from its calibration's report (`calibrated/<model>.json`):
based on its model's published set, it changes the parameters the report
holds calibrated, to the values the report gives, each saying where it
comes from. The report stays the record of the calibration; the set is what
names its numbers. `tests/test_agc4_sets.py` holds each committed set to its
report, and its values to those the test on 2024 ran (`challenge.py`).

A calibrated set is a research result kept here, never one of the models'
published defaults, and never packaged with the simulator (decisions 0076
and 0077).

    python -m research.validation.agc4.sets

writes `sets/<model>.json` for each model from its report.
"""

import json
from pathlib import Path
from typing import Any, Final

from greenhouse_sim.biology.parameter_sets import (
    PUBLISHED_SETS,
    ParameterSet,
    ResolvedSet,
    read_parameter_set,
    resolved,
)
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios.registry import model as registered

from research.validation.agc4.calibrate import HERE, MODELS
from research.validation.agc4.calibration import Model

SETS: Final = HERE / "sets"
# The name both calibrated sets go by: what they were calibrated on.
NAME: Final = "agc4_pretrial_2023"
VERSION: Final = 1
# Each model of the calibration by the name the registry gives it.
REGISTERED: Final = {
    "tomgro": CropModel.REDUCED_TOMGRO.value,
    "vanthoor_katzin": CropModel.VANTHOOR_KATZIN.value,
}


def report(model: Model) -> dict[str, Any]:
    """The model's calibration's report, as committed."""
    found: dict[str, Any] = json.loads((HERE / "calibrated" / f"{model.name}.json").read_text())
    if found["model"] != model.name:
        raise ValueError(f"{model.name}'s calibration's report is {found['model']}'s")
    return found


def calibrated_set(model: Model) -> ParameterSet:
    """The model's calibrated set, from its calibration's report."""
    found = report(model)
    name = REGISTERED[model.name]
    base = resolved(PUBLISHED_SETS[name])
    return read_parameter_set(
        {
            "model": name,
            "name": NAME,
            "version": VERSION,
            "based_on": base.named.model_dump(),
            "parameters": {each["name"]: each["calibrated"] for each in found["parameters"]},
            "why": {each["name"]: _why(each) for each in found["parameters"]},
            "made_for": registered(Part.CROP, name).version,
            "cultivar": None,
            "description": (
                f"{base.parameter_set.name} v{base.parameter_set.version} with the parameters"
                f" calibrated on WUR AGC4's 2023 pre-trial (decision 0076), as"
                f" research/validation/agc4/calibrated/{model.name}.json reports them and as"
                " the test on 2024's fruit ran them. A research result, not the model's"
                " published defaults. The pre-trial's cultivar is not verified (the AGC4"
                " memo, §2), so the set names none."
            ),
        }
    )


def calibrated_sets() -> dict[str, ResolvedSet]:
    """Each model's calibrated set, resolved, by the calibration's name for it."""
    return {name: resolved(calibrated_set(model)) for name, model in MODELS.items()}


def written(parameter_set: ParameterSet) -> str:
    """A set as its file holds it."""
    return json.dumps(parameter_set.model_dump(mode="json"), indent=1, ensure_ascii=False) + "\n"


def path(model: Model) -> Path:
    """Where the model's calibrated set is kept."""
    return SETS / f"{model.name}.json"


def _why(parameter: dict[str, Any]) -> str:
    low, high = parameter["bounds"]
    at_bound = f", at its {parameter['at_bound']} bound" if parameter["at_bound"] else ""
    return (
        f"Calibrated on AGC4's 2023 pre-trial (decision 0076), within {low:g} to {high:g}"
        f"{at_bound}; published {parameter['published']:g}."
    )


def main() -> None:
    SETS.mkdir(exist_ok=True)
    for model in MODELS.values():
        path(model).write_text(written(calibrated_set(model)))


if __name__ == "__main__":
    main()
