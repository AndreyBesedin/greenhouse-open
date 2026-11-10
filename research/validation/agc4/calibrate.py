"""Runs decision 0076's calibration of a tomato model, as its manifest
names it, on the pre-trial's calibration data alone, and reports its fit.

    python -m research.validation.agc4.calibrate tomgro DRIVERS_DIR \\
        > research/validation/agc4/calibrated/tomgro.json

`DRIVERS_DIR` holds the series `drivers.py` writes. Each 2023 zone's series
is refused unless its sha256 is the one `drivers.json` records. The
manifest (`manifests/<model>.json`) names the parameters calibrated, each
with its bounds, and the optimizer's options: scipy's Powell, each
parameter mapped linearly from its bounds to [0, 1], started from its
published value. Every other parameter keeps its published value.

The report holds the calibrated parameters beside the published, the
objective at both, the optimizer's account of itself and its run time,
and the fit: each target's prediction at the midnight that begins its day,
its error and relative error, and whether it falls within two standard
errors of the measurement, with the same measures per quantity. Each
zone's largest leaf area index at a midnight is given beside the model's
most and, for Vanthoor's model, the leaves it has pruned per plant by each
target's date: its pruning is a smooth switch that prunes some leaf below
its most, and AGC4 pruned none (decision 0076). No 2024 measurement is
read.
"""

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from collections.abc import Mapping, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any, Final

from greenhouse_adapters.storage.layout import DataDirectory
from pydantic import BaseModel
from scipy.optimize import minimize

from research.validation.agc4.archives import PRETRIAL, PRETRIAL_ARCHIVE, archive_path
from research.validation.agc4.calibration import (
    TOMGRO,
    VANTHOOR,
    Model,
    Target,
    objective,
    readings_of,
    targets,
)
from research.validation.agc4.drivers import Hour
from research.validation.agc4.harness import Transplant, read_series, transplants

HERE: Final = Path(__file__).resolve().parent
MANIFESTS: Final = HERE / "manifests"
DRIVERS: Final = HERE / "drivers.json"
MODELS: Final = {model.name: model for model in (TOMGRO, VANTHOOR)}
METHOD: Final = "Powell"
INDENT: Final = " "
# A calibrated value within this share of its bounds' span from one is
# reported at it: Powell's bounded line search stops short of a bound.
NEAR_A_BOUND: Final = 0.01


def zones(drivers_dir: Path, dataset: str = PRETRIAL) -> dict[str, list[Hour]]:
    """A dataset's series, one per 2023 light zone or 2024 compartment, each
    checked against the sha256 `drivers.json` records."""
    recorded = json.loads(DRIVERS.read_text())[dataset]["series"]
    found: dict[str, list[Hour]] = {}
    for zone, entry in recorded.items():
        path = drivers_dir / entry["file"]
        text = path.read_bytes()
        if hashlib.sha256(text).hexdigest() != entry["sha256"]:
            raise ValueError(f"{path} is not the series drivers.json records")
        found[zone] = read_series(text.decode())
    return found


def unscaled(manifest: Mapping[str, Any], x: Sequence[float]) -> dict[str, float]:
    """The parameters named, each mapped from [0, 1] back to its bounds."""
    return {
        each["name"]: each["bounds"][0] + float(share) * (each["bounds"][1] - each["bounds"][0])
        for each, share in zip(manifest["parameters"], x, strict=True)
    }


def scaled(manifest: Mapping[str, Any], values: Mapping[str, float]) -> list[float]:
    """Each parameter named, held within its bounds and mapped to [0, 1]."""
    shares = []
    for each in manifest["parameters"]:
        low, high = each["bounds"]
        shares.append((min(max(values[each["name"]], low), high) - low) / (high - low))
    return shares


def calibrate(
    model: Model,
    manifest: Mapping[str, Any],
    transplant: Transplant,
    series: Mapping[str, Sequence[Hour]],
    goals: Sequence[Target],
) -> dict[str, Any]:
    """The manifest's calibration of `model`, and its fit."""
    if manifest["model"] != model.name:
        raise ValueError(f"the manifest is {manifest['model']}'s, not {model.name}'s")
    if manifest["method"]["optimizer"].split(", ")[1] != f"method {METHOD}":
        raise ValueError(f"the manifest's method is not {METHOD}")

    def parameters_at(x: Sequence[float]) -> BaseModel:
        return model.published.model_copy(update=unscaled(manifest, x))

    def score(x: Sequence[float]) -> float:
        readings = readings_of(model, parameters_at(x), transplant, series)
        return objective(readings, goals, model.quantities)

    published = model.published.model_dump()
    start = scaled(manifest, published)
    began = time.perf_counter()
    result = minimize(
        score,
        start,
        method=METHOD,
        bounds=[(0.0, 1.0)] * len(start),
        options=manifest["method"]["options"],
    )
    seconds = time.perf_counter() - began
    calibrated = parameters_at(result.x)
    return {
        "model": model.name,
        "decision": "0076",
        "manifest": f"manifests/{model.name}.json",
        "data": "the 2023 pre-trial's destructive samples and its climate, no 2024 measurement",
        "software": {
            "python": platform.python_version(),
            "scipy": version("scipy"),
            "numpy": version("numpy"),
        },
        "optimizer": {
            "method": METHOD,
            "options": manifest["method"]["options"],
            "evaluations": int(result.nfev),
            "iterations": int(result.nit),
            "success": bool(result.success),
            "message": str(result.message),
            "seconds": round(seconds, 1),
        },
        "objective": {"published": score(start), "calibrated": score(result.x)},
        "parameters": [
            _parameter(each, published[each["name"]], getattr(calibrated, each["name"]))
            for each in manifest["parameters"]
        ],
        **fit(model, calibrated, transplant, series, goals),
    }


def fit(
    model: Model,
    parameters: BaseModel,
    transplant: Transplant,
    series: Mapping[str, Sequence[Hour]],
    goals: Sequence[Target],
) -> dict[str, Any]:
    """Each target against its prediction, the same measures per quantity,
    each zone's largest leaf area index at a midnight, and the leaves pruned
    by each target's date if the model prunes."""
    readings = readings_of(model, parameters, transplant, series)
    held = [goal for goal in goals if goal.quantity in model.quantities]
    rows = [
        _compared(goal, getattr(readings[(goal.zone, goal.on)], goal.quantity)) for goal in held
    ]
    quantities = [
        _summed(quantity, [r for r in rows if r["quantity"] == quantity], readings, goals)
        for quantity in model.quantities
        if any(r["quantity"] == quantity for r in rows)
    ]
    leaves: dict[str, Any] = {
        "most_leaf_area_index": parameters.model_dump()["lai_max"],
        "largest_leaf_area_index_at_a_midnight": {
            zone: max(m.leaf_area_index for (z, _), m in readings.items() if z == zone)
            for zone in series
        },
    }
    if any(m.pruned_leaves_g is not None for m in readings.values()):
        dates = sorted({goal.on for goal in held})
        leaves["pruned_g_per_plant"] = {
            zone: {on.isoformat(): readings[(zone, on)].pruned_leaves_g for on in dates}
            for zone in series
        }
    return {"per_quantity": quantities, "leaves": leaves, "fit": rows}


def written(value: object, depth: int = 0) -> str:
    """The report as JSON: an object of plain values on a line of its own,
    and a list of such objects an item to a line, so that a change to it
    reads as the lines that changed."""
    inner = INDENT * (depth + 1)
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        items = [f"{inner}{json.dumps(each, ensure_ascii=False)}" for each in value]
        return "[\n" + ",\n".join(items) + "\n" + INDENT * depth + "]"
    if not isinstance(value, dict) or all(_plain(each) for each in value.values()):
        return json.dumps(value, ensure_ascii=False)
    lines = [
        f"{inner}{json.dumps(key, ensure_ascii=False)}: {written(each, depth + 1)}"
        for key, each in value.items()
    ]
    return "{\n" + ",\n".join(lines) + "\n" + INDENT * depth + "}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("model", choices=sorted(MODELS))
    parser.add_argument("drivers_dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=None, help="override GREENHOUSE_DATA_DIR")
    arguments = parser.parse_args(argv)
    archive = archive_path(DataDirectory(arguments.data_dir), PRETRIAL, PRETRIAL_ARCHIVE)
    manifest = json.loads((MANIFESTS / f"{arguments.model}.json").read_text())
    report = calibrate(
        MODELS[arguments.model],
        manifest,
        transplants(archive),
        zones(arguments.drivers_dir),
        targets(archive),
    )
    sys.stdout.write(written(report) + "\n")
    return 0


def _parameter(named: Mapping[str, Any], published: float, calibrated: float) -> dict[str, Any]:
    low, high = named["bounds"]
    near = (high - low) * NEAR_A_BOUND
    at_bound = "lower" if calibrated - low < near else None
    at_bound = "upper" if high - calibrated < near else at_bound
    return {
        "name": named["name"],
        "published": published,
        "calibrated": calibrated,
        "bounds": [low, high],
        "at_bound": at_bound,
    }


def _compared(goal: Target, predicted: float) -> dict[str, Any]:
    error = predicted - goal.mean
    se = goal.standard_error
    return {
        "zone": goal.zone,
        "ec": goal.ec,
        "on": goal.on.isoformat(),
        "quantity": goal.quantity,
        "measured": goal.mean,
        "standard_error": se,
        "plants": goal.plants,
        "predicted": predicted,
        "error": error,
        "relative_error": error / goal.mean if goal.mean else None,
        # A mean whose plants all measured the same has no spread to judge by.
        "within_two_se": abs(error) <= 2 * se if se else None,
    }


def _summed(
    quantity: str,
    rows: Sequence[Mapping[str, Any]],
    readings: Mapping[Any, Any],
    goals: Sequence[Target],
) -> dict[str, Any]:
    relative = [r["relative_error"] for r in rows if r["relative_error"] is not None]
    judged = [r["within_two_se"] for r in rows if r["within_two_se"] is not None]
    return {
        "quantity": quantity,
        "targets": len(rows),
        "objective": objective(readings, goals, (quantity,)),
        "bias": sum(relative) / len(relative),
        "rms_relative_error": math.sqrt(sum(e**2 for e in relative) / len(relative)),
        "relative_errors_of": len(relative),
        "within_two_se": sum(judged),
        "with_a_standard_error": len(judged),
    }


def _plain(value: object) -> bool:
    return not isinstance(value, dict | list) or all(not isinstance(v, dict | list) for v in value)


if __name__ == "__main__":
    raise SystemExit(main())
