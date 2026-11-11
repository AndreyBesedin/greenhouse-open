"""Runs decision 0076's test of a calibrated tomato model on the 2024
challenge's fruit, and writes its report, once.

    python -m research.validation.agc4.challenge tomgro DRIVERS_DIR

writes `tested/tomgro.json`, and refuses to run if that report is there:
each model runs the test once, and its first report is kept (decision
0076). `DRIVERS_DIR` holds the series `drivers.py` writes; each 2024
compartment's is refused unless its sha256 is the one `drivers.json`
records. The model runs with the parameters its calibration's report holds
(`calibrated/<model>.json`), every other one published, from the 2023
transplants scaled to the density at transplanting, through each
compartment's hours to the midnight that begins its harvest day.

What it is held to, from `Harvest.xlsx` as the adapter reads it:

- the fruit's fresh weight per plant, at each of the three samplings and
  at the final harvest, over the plants weighed whole: the 24
  compartment-dates, held to the model's fruit;
- for Reduced-State TOMGRO alone, the final harvest's red fruit per plant,
  over every plant weighed for it, held to its mature fruit and reported
  apart.

A prediction is the model's dry fruit per plant at the midnight that
begins the measurement's day, over the pre-trial's fruit dry-matter
fraction at its last date; for a sampling, the midnight after is given
beside it. The report holds, per compartment-date, the prediction, the
measurement with its standard error and its plants, the error and the
relative error; over the test, the bias, the root mean square of the
relative errors, how many fall within two standard errors, and Spearman's
rank correlation over the final harvests; and the skill against the
baseline, which grows every compartment's fruit as the pre-trial's EC3
treatments grew theirs, by the days since transplanting. The baseline's
fruit is dry, as the pre-trial weighed it, and is turned fresh by the same
fraction as the model's, so that the skill compares how each grows dry
matter, not how it is converted.

The sensitivities take the same measures with GreenLight's assumed 6 %,
with the lowest and the highest dry matter of 2024's red batches
(`profile.json`), with each sampling at the midnight after, and, for
Vanthoor's model, with Reduced-State TOMGRO's 0.75 g of dry matter per g
of carbohydrate. With them: the run time, the hours each series fills from
the hour before, the leaves a model prunes, and each difference between
what a model gives and what was measured.
"""

import argparse
import io
import json
import math
import platform
import sys
import time
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from importlib.metadata import version
from itertools import pairwise
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Final

import openpyxl
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_adapters.wur.agc4_challenge_2024.harvest import (
    HarvestWorkbook,
    read_harvest_workbook,
)
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from pydantic import BaseModel
from scipy.stats import spearmanr

from research.validation.agc4.archives import (
    CHALLENGE,
    CHALLENGE_ARCHIVE,
    PRETRIAL,
    PRETRIAL_ARCHIVE,
    archive_path,
    members,
)
from research.validation.agc4.calibrate import HERE, MODELS, written, zones
from research.validation.agc4.calibration import (
    FRUIT,
    ORGANS,
    VANTHOOR,
    Model,
    Target,
    readings_of,
    targets,
)
from research.validation.agc4.drivers import CHALLENGE_START, DAYS, HOUR, Hour
from research.validation.agc4.harness import (
    DESTRUCTIVE_SHEET,
    DESTRUCTIVE_WORKBOOK,
    TRANSPLANTED,
    Midnight,
    Transplant,
    transplants,
)

TESTED: Final = HERE / "tested"
CALIBRATED: Final = HERE / "calibrated"
PROFILE: Final = HERE / "profile.json"
HARVEST_WORKBOOK: Final = "Harvest.xlsx"

# What a 2024 measurement is: its occasion and its quantity, both fresh.
SAMPLING: Final = "sampling"
FINAL_HARVEST: Final = "final harvest"
FRUIT_FRESH: Final = "fruit_fresh_g"
RED_FRUIT_FRESH: Final = "red_fruit_fresh_g"

# The baseline is the pre-trial's EC3 crop: 2024's EC was 2.8.
BASELINE_EC: Final = "EC3"
PRETRIAL_TRANSPLANTED: Final = date.fromisoformat(TRANSPLANTED)
CHALLENGE_TRANSPLANTED: Final = CHALLENGE_START.date()
# GreenLight 2.0.7's assumed fruit dry-matter content (`main_cli.py`).
GREENLIGHT_DRY_MATTER: Final = 0.06
# Reduced-State TOMGRO's dry weight per g of carbohydrate, Vanthoor's
# model's sensitivity.
TOMGRO_DRY_PER_CARBOHYDRATE: Final = TomgroParameters().e
RED_BATCH: Final = "red"

SHARED_DIFFERENCES: Final = (
    "The run starts from the 2023 transplants, per plant, scaled to the density"
    " at transplanting: 2024's transplants were not measured.",
    "2024's fruit was weighed fresh. The model's dry fruit is turned fresh by the"
    " pre-trial's fruit dry-matter fraction at its last date, of mostly green fruit"
    " weighed with its cluster stems; the final harvest's fruit is mostly red.",
    "A measurement is compared with the state at the midnight that begins its day."
    " A compartment's drivers end at the midnight that begins its harvest day, so a"
    " final harvest has no midnight after.",
    "A final harvest's fruit is the mean over the plants weighed whole; fruit fallen"
    " off before it was weighed is in no measurement.",
    "The baseline's dry fruit is turned fresh by the same fraction as the model's.",
)
DIFFERENCES: Final = {
    "tomgro": (
        "Its fruit is its fruit's dry weight. Its red fruit is held to its mature"
        " fruit, which is not a colour.",
    ),
    "vanthoor_katzin": (
        "Its fruit is its standing fruit and its harvested, its carbohydrate taken"
        " for dry matter one for one. It tells no ripeness: it has no red fruit to"
        " compare.",
        "It prunes leaves, which AGC4 did not: the leaves it has pruned per plant"
        " by each date are given.",
    ),
}


@dataclass(frozen=True)
class Measured:
    """A compartment's fruit, fresh, per plant on a date: the mean over the
    plants weighed, its standard error and its plants."""

    compartment: str
    on: date
    occasion: str
    quantity: str
    mean: float
    standard_error: float | None
    plants: int


@dataclass(frozen=True)
class Assumed:
    """How a model's fruit becomes a fresh prediction: the fruit's
    dry-matter fraction, the dry matter per unit of the model's fruit, and
    whether a sampling is read at the midnight after its day's."""

    dry_matter: float
    dry_per_unit: float = 1.0
    after: bool = False

    def fresh(self, model_fruit: float) -> float:
        return model_fruit * self.dry_per_unit / self.dry_matter


def harvest(archive: Path) -> HarvestWorkbook:
    """The challenge's fruit, as the adapter reads `Harvest.xlsx`."""
    with zipfile.ZipFile(archive) as opened:
        (member,) = [n for n in members(opened) if Path(n).name == HARVEST_WORKBOOK]
        return read_harvest_workbook(io.BytesIO(opened.read(member)))


def harvest_days(series: Mapping[str, Sequence[Hour]]) -> dict[str, date]:
    """Each compartment's harvest day: its series ends at the midnight that
    begins it (`drivers.py`)."""
    return {
        compartment: (hours[-1].start + HOUR).astimezone(DAYS).date()
        for compartment, hours in series.items()
    }


def measured(workbook: HarvestWorkbook, days: Mapping[str, date]) -> list[Measured]:
    """Each compartment's fruit at its samplings and its final harvest, on
    its harvest day, and its red fruit at the final harvest."""
    found: list[Measured] = []
    for compartment, harvested in days.items():
        code = compartment.replace(".", "")
        for sampling in workbook.samplings:
            weights = [plant.fresh_weight_g for plant in sampling.for_compartment(code)]
            if weights:
                found.append(_mean(compartment, sampling.day, SAMPLING, FRUIT_FRESH, weights))
        for final in workbook.final_harvests:
            if final.compartment_code != code:
                continue
            whole = [plant.fresh_weight_g for plant in final.plants]
            red = [p.red_fresh_weight_g for p in final.plants if p.red_fresh_weight_g is not None]
            red += [plant.red_fresh_weight_g for plant in final.red_fruit_alone]
            if whole:
                found.append(_mean(compartment, harvested, FINAL_HARVEST, FRUIT_FRESH, whole))
            if red:
                found.append(_mean(compartment, harvested, FINAL_HARVEST, RED_FRUIT_FRESH, red))
    return found


def baseline(goals: Sequence[Target]) -> list[tuple[int, float]]:
    """The pre-trial's EC3 fruit, dry per plant: none at transplanting, then
    the mean of its light zones' means at each destructive date, by the days
    since transplanting."""
    by_date: dict[date, list[float]] = defaultdict(list)
    for goal in goals:
        if goal.quantity == FRUIT and goal.ec == BASELINE_EC:
            by_date[goal.on].append(goal.mean)
    if len(by_date) < 2:
        raise ValueError(f"the baseline needs two dates of {BASELINE_EC} fruit")
    return [(0, 0.0)] + [
        ((on - PRETRIAL_TRANSPLANTED).days, mean(means)) for on, means in sorted(by_date.items())
    ]


def grown(knots: Sequence[tuple[int, float]], days: float) -> float:
    """The baseline's fruit `days` after transplanting: linear between its
    dates, and past its last at its last interval's rate."""
    for (start, before), (end, after) in pairwise(knots):
        if days <= end:
            return before + (after - before) * (days - start) / (end - start)
    (start, before), (end, after) = knots[-2:]
    return after + (after - before) / (end - start) * (days - end)


def pretrial_dry_matter(archive: Path) -> tuple[float, int]:
    """The pre-trial's fruit dry-matter fraction at its last destructive
    date, and its plants: the mean of each plant's dried fruit over its
    fruiting clusters weighed fresh, where both are weighed and the dry is
    not the heavier."""
    with zipfile.ZipFile(archive) as opened:
        (member,) = [n for n in members(opened) if Path(n).name == DESTRUCTIVE_WORKBOOK]
        book = openpyxl.load_workbook(io.BytesIO(opened.read(member)), data_only=True)
    rows = [r for r in book[DESTRUCTIVE_SHEET].iter_rows(values_only=True) if any(r)]
    (at,) = [i for i, row in enumerate(rows) if "Date" in (str(c).strip() for c in row)]
    header = [str(cell).strip() if cell is not None else "" for cell in rows[at]]
    date_at = header.index("Date")
    dry_at, fresh_at = (header.index(name) for name in ORGANS["fruits"])
    weighed: list[tuple[datetime, float]] = []
    for row in rows[at + 1 :]:
        on, dry, fresh = row[date_at], _number(row[dry_at]), _number(row[fresh_at])
        if isinstance(on, datetime) and dry is not None and fresh and 0 <= dry <= fresh:
            weighed.append((on, dry / fresh))
    last = max(on for on, _ in weighed)
    fractions = [fraction for on, fraction in weighed if on == last]
    return mean(fractions), len(fractions)


def red_batches() -> list[float]:
    """The dry-matter fraction of each 2024 final harvest's red batch, as
    the profile computes it from the drying block of its sheet."""
    sheets = json.loads(PROFILE.read_text())[CHALLENGE]["harvest"]["sheets"]
    return sorted(
        batch["dry_matter_percent"] / 100
        for sheet in sheets.values()
        for batch in sheet.get("dried", [])
        if batch["fruit"] == RED_BATCH
    )


def calibrated(model: Model) -> dict[str, float]:
    """The parameters the model's calibration's report holds calibrated."""
    report = json.loads((CALIBRATED / f"{model.name}.json").read_text())
    if report["model"] != model.name:
        raise ValueError(f"{model.name}'s calibration's report is {report['model']}'s")
    return {each["name"]: each["calibrated"] for each in report["parameters"]}


def compared(
    goals: Sequence[Measured],
    readings: Mapping[tuple[str, date], Midnight],
    knots: Sequence[tuple[int, float]],
    assumed: Assumed,
) -> list[dict[str, Any]]:
    """Each measurement beside its prediction, with the baseline's for the
    fruit, and for a sampling the prediction at the midnight after."""
    rows: list[dict[str, Any]] = []
    for goal in goals:
        later = goal.on + timedelta(days=1)
        read = later if assumed.after and goal.occasion == SAMPLING else goal.on
        predicted = assumed.fresh(_fruit(readings[(goal.compartment, read)], goal.quantity))
        after = (
            assumed.fresh(_fruit(readings[(goal.compartment, later)], goal.quantity))
            if goal.occasion == SAMPLING
            else None
        )
        days = (goal.on - CHALLENGE_TRANSPLANTED).days
        error = predicted - goal.mean
        rows.append(
            {
                "compartment": goal.compartment,
                "on": goal.on.isoformat(),
                "days_after_transplanting": days,
                "occasion": goal.occasion,
                "quantity": goal.quantity,
                "measured": goal.mean,
                "standard_error": goal.standard_error,
                "plants": goal.plants,
                "predicted": predicted,
                "error": error,
                "relative_error": error / goal.mean if goal.mean else None,
                "within_two_se": abs(error) <= 2 * goal.standard_error
                if goal.standard_error
                else None,
                "predicted_the_midnight_after": after,
                "baseline": grown(knots, days) / assumed.dry_matter
                if goal.quantity == FRUIT_FRESH
                else None,
            }
        )
    return rows


def measures(rows: Sequence[Mapping[str, Any]], key: str = "predicted") -> dict[str, Any]:
    """Decision 0076's measures over `rows`, of the prediction `key`."""
    errors = [row[key] - row["measured"] for row in rows]
    relative = [e / row["measured"] for e, row in zip(errors, rows, strict=True) if row["measured"]]
    judged = [
        abs(e) <= 2 * row["standard_error"]
        for e, row in zip(errors, rows, strict=True)
        if row["standard_error"]
    ]
    finals = [row for row in rows if row["occasion"] == FINAL_HARVEST]
    return {
        "compared": len(rows),
        "bias": mean(relative) if relative else None,
        "rms_relative_error": math.sqrt(mean(e**2 for e in relative)) if relative else None,
        "relative_errors_of": len(relative),
        "within_two_se": sum(judged),
        "with_a_standard_error": len(judged),
        "spearman_final_harvests": spearman(
            [row[key] for row in finals], [row["measured"] for row in finals]
        ),
        "final_harvests": len(finals),
    }


def skill(rows: Sequence[Mapping[str, Any]]) -> float | None:
    """One minus the model's sum of squared errors over the baseline's."""
    model = sum((row["predicted"] - row["measured"]) ** 2 for row in rows)
    base = sum((row["baseline"] - row["measured"]) ** 2 for row in rows)
    return 1 - model / base if base else None


def spearman(predicted: Sequence[float], measured: Sequence[float]) -> float | None:
    """Spearman's rank correlation, none where either side has no order."""
    if len(set(predicted)) < 2 or len(set(measured)) < 2:
        return None
    return float(spearmanr(predicted, measured).statistic)


def tested(
    model: Model,
    calibrated: Mapping[str, float],
    transplant: Transplant,
    series: Mapping[str, Sequence[Hour]],
    *,
    goals: Sequence[Measured],
    knots: Sequence[tuple[int, float]],
    dry_matter: tuple[float, int],
    batches: Sequence[float],
) -> dict[str, Any]:
    """The model's test: its run on every compartment, its calibrated
    parameters in, every other published, compared."""
    parameters = model.published.model_copy(update=dict(calibrated))
    began = time.perf_counter()
    readings = readings_of(model, parameters, transplant, series)
    seconds = time.perf_counter() - began
    gives_mature = all(m.mature_fruit_dry_g is not None for m in readings.values())
    held = [g for g in goals if g.quantity == FRUIT_FRESH or gives_mature]
    assumed = Assumed(dry_matter[0])
    varied = [
        (
            "GreenLight's assumed fruit dry matter, 6 %",
            replace(assumed, dry_matter=GREENLIGHT_DRY_MATTER),
        ),
        ("the lowest dry matter of 2024's red batches", replace(assumed, dry_matter=min(batches))),
        ("the highest dry matter of 2024's red batches", replace(assumed, dry_matter=max(batches))),
        ("each sampling at the midnight after", replace(assumed, after=True)),
    ]
    if model.name == VANTHOOR.name:
        varied.append(
            (
                "0.75 g of dry matter per g of carbohydrate",
                replace(assumed, dry_per_unit=TOMGRO_DRY_PER_CARBOHYDRATE),
            )
        )
    rows = compared(held, readings, knots, assumed)
    return {
        "model": model.name,
        "decision": "0076",
        "calibration": f"calibrated/{model.name}.json",
        "parameters": dict(calibrated),
        "data": "the 2024 challenge's fruit and climate; the 2023 transplants, and the"
        " pre-trial's EC3 fruit and fruit dry matter for the baseline and the conversion",
        "software": {
            "python": platform.python_version(),
            "scipy": version("scipy"),
            "numpy": version("numpy"),
        },
        "seconds": round(seconds, 1),
        "assumed": {
            "fruit_dry_matter": assumed.dry_matter,
            "of_plants": dry_matter[1],
            "dry_matter_per_unit": assumed.dry_per_unit,
        },
        "baseline": {
            "ec": BASELINE_EC,
            "dry_fruit_g_per_plant_by_days_after_transplanting": [list(k) for k in knots],
        },
        **_measured_by(rows),
        "sensitivities": [
            {"varied": name, **_measured_by(compared(held, readings, knots, each))}
            for name, each in varied
        ],
        "filled_hours": {
            compartment: [hour.start.isoformat() for hour in hours if hour.filled]
            for compartment, hours in series.items()
        },
        "leaves": _leaves(readings, parameters, held, series),
        "differences": [*SHARED_DIFFERENCES, *DIFFERENCES[model.name]],
        "fit": rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("model", choices=sorted(MODELS))
    parser.add_argument("drivers_dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=None, help="override GREENHOUSE_DATA_DIR")
    arguments = parser.parse_args(argv)
    report = TESTED / f"{arguments.model}.json"
    if report.exists():
        raise SystemExit(
            f"{report} is there: decision 0076 tests a model once, and keeps its first report"
        )
    data = DataDirectory(arguments.data_dir)
    pretrial = archive_path(data, PRETRIAL, PRETRIAL_ARCHIVE)
    challenge = archive_path(data, CHALLENGE, CHALLENGE_ARCHIVE)
    model = MODELS[arguments.model]
    series = zones(arguments.drivers_dir, CHALLENGE)
    found = tested(
        model,
        calibrated(model),
        transplants(pretrial),
        series,
        goals=measured(harvest(challenge), harvest_days(series)),
        knots=baseline(targets(pretrial)),
        dry_matter=pretrial_dry_matter(pretrial),
        batches=red_batches(),
    )
    TESTED.mkdir(exist_ok=True)
    with report.open("x", encoding="utf-8") as opened:
        opened.write(written(found) + "\n")
    sys.stdout.write(f"{report}\n")
    return 0


def _mean(
    compartment: str, on: date, occasion: str, quantity: str, weights: Sequence[float]
) -> Measured:
    spread = stdev(weights) / math.sqrt(len(weights)) if len(weights) > 1 else None
    return Measured(compartment, on, occasion, quantity, mean(weights), spread, len(weights))


def _fruit(midnight: Midnight, quantity: str) -> float:
    fruit = midnight.mature_fruit_dry_g if quantity == RED_FRUIT_FRESH else midnight.fruit_dry_g
    if fruit is None:
        raise ValueError(f"the model gives no fruit for {quantity}")
    return fruit


def _measured_by(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fruit = [row for row in rows if row["quantity"] == FRUIT_FRESH]
    found: dict[str, Any] = {
        "fruit": measures(fruit) | {"skill": skill(fruit)},
        "baseline_fruit": measures(fruit, "baseline"),
    }
    red = [row for row in rows if row["quantity"] == RED_FRUIT_FRESH]
    if red:
        found["red_fruit"] = measures(red)
    return found


def _leaves(
    readings: Mapping[tuple[str, date], Midnight],
    parameters: BaseModel,
    goals: Sequence[Measured],
    series: Mapping[str, Sequence[Hour]],
) -> dict[str, Any]:
    leaves: dict[str, Any] = {
        "most_leaf_area_index": parameters.model_dump()["lai_max"],
        "largest_leaf_area_index_at_a_midnight": {
            compartment: max(
                m.leaf_area_index for (c, _), m in readings.items() if c == compartment
            )
            for compartment in series
        },
    }
    if any(m.pruned_leaves_g is not None for m in readings.values()):
        leaves["pruned_g_per_plant"] = {
            compartment: {
                goal.on.isoformat(): readings[(compartment, goal.on)].pruned_leaves_g
                for goal in goals
                if goal.compartment == compartment and goal.quantity == FRUIT_FRESH
            }
            for compartment in series
        }
    return leaves


def _number(cell: object) -> float | None:
    if isinstance(cell, bool) or not isinstance(cell, int | float) or math.isnan(cell):
        return None
    return float(cell)


if __name__ == "__main__":
    raise SystemExit(main())
