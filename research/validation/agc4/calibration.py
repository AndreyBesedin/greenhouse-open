"""The 2023 calibration targets of decision 0076, the objective a tomato
model's calibration minimises, and a screen of which parameters move it.

    python -m research.validation.agc4.calibration DRIVERS_DIR \\
        > research/validation/agc4/screen.json

`DRIVERS_DIR` holds the series `drivers.py` writes. The targets come from
the pre-trial's destructive samples (`DestructiveHarvest.xlsx`, `All
Data`): per light zone, EC treatment and date after transplanting, the mean
per plant, its standard error and its plants, of

- `dry_weight_g`: the dry weight above ground (`DW whole plant`);
- `fruit_dry_g`: the fruit's (`DW fruits`), zero on a plant whose fruiting
  clusters weigh nothing fresh, since fruit not yet set is a measurement;
- `dry_leaves_g` and `dry_stem_g` (`DW leaves`, `DW stem`);
- `leaf_area_index`: the leaf area measured, times the plants per m² the
  sample gives.

An organ dried heavier than it weighed fresh is no target, nor is its
plant's dry weight above ground: dry matter cannot outweigh the fresh.

Each model is held to the quantities it has: Reduced-State TOMGRO to the
dry weight above ground, the fruit's and the leaf area index; Vanthoor's
model to all five. The objective is decision 0076's: the sum, over the
targets, of the squared natural logarithm of (predicted + c) over
(measured + c), c being half the smallest mean above zero of each quantity.

The screen runs each model with the published parameters, then with each
parameter, one at a time, at 0.8 and at 1.25 times its value, and reports
the objective each time, per parameter ranked by how far it moves it. It
reads the calibration data alone, and no 2024 measurement.
"""

import argparse
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Final

import openpyxl
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters
from pydantic import BaseModel

from research.validation.agc4.archives import PRETRIAL, PRETRIAL_ARCHIVE, archive_path, members
from research.validation.agc4.drivers import DAYS, PRETRIAL_ZONES
from research.validation.agc4.harness import (
    DESTRUCTIVE_SHEET,
    DESTRUCTIVE_WORKBOOK,
    TRANSPLANTED,
    Midnight,
    Transplant,
    read_series,
    run_tomgro,
    run_vanthoor,
    transplants,
)

# The pre-trial's light treatments, as its workbook writes them, by the
# zones `drivers.py` names.
LIGHT: Final = {"high light": "high", "med light": "medium", "low light": "low", "no light": "none"}
DRY_WEIGHT: Final = "dry_weight_g"
FRUIT: Final = "fruit_dry_g"
LEAVES: Final = "dry_leaves_g"
STEM: Final = "dry_stem_g"
LAI: Final = "leaf_area_index"
TOMGRO_QUANTITIES: Final = (DRY_WEIGHT, FRUIT, LAI)
VANTHOOR_QUANTITIES: Final = (DRY_WEIGHT, FRUIT, LEAVES, STEM, LAI)
# Each organ's dry and fresh weight columns, to refuse a dry weight above its fresh.
ORGANS: Final = {
    "leaves": ("DW leaves (g/plant)", "FW leaves (g/plant)"),
    "stem": ("DW stem (g/plant)", "FW stem (g/plant)"),
    "flowers": ("DW flowers (g/plant)", "FW flowers (g/plant)"),
    "fruits": ("DW fruits (g/plant)", "FW fruits clusters(g/plant)"),
}
WHOLE: Final = "DW whole plant (g/plant)"
LEAF_AREA: Final = "Leaf Area measured (cm²/plant)"
DENSITY: Final = "Plant density (p/m2)"
CM2_A_M2: Final = 1e4
# The screen's steps, each parameter's published value times these.
SCREEN_STEPS: Final = (0.8, 1.25)
# Parameters the screen leaves as they are: constants of physics, units and
# the harness's own (ρ is the density in force; TRGH is 1 for PAR measured
# inside the greenhouse; D converts µmol CO₂ m⁻² s⁻¹ to g CH₂O m⁻² d⁻¹).
FIXED: Final = frozenset({"r", "t25k", "m_ch2o", "ro", "trgh", "d"})


@dataclass(frozen=True)
class Target:
    """A quantity's mean per plant over a treatment's plants on a date."""

    zone: str
    ec: str
    on: date
    quantity: str
    mean: float
    standard_error: float | None
    plants: int


def targets(archive: Path) -> list[Target]:
    """The pre-trial's calibration targets, from its destructive samples."""
    with zipfile.ZipFile(archive) as opened:
        (member,) = [n for n in members(opened) if Path(n).name == DESTRUCTIVE_WORKBOOK]
        book = openpyxl.load_workbook(io.BytesIO(opened.read(member)), data_only=True)
    rows = [r for r in book[DESTRUCTIVE_SHEET].iter_rows(values_only=True) if any(r)]
    (at,) = [i for i, row in enumerate(rows) if "Date" in (str(c).strip() for c in row)]
    header = [str(cell).strip() if cell is not None else "" for cell in rows[at]]
    column = {name: index for index, name in enumerate(header) if name}
    samples: dict[tuple[str, str, date, str], list[float]] = defaultdict(list)
    for row in rows[at + 1 :]:
        on = _day(row[column["Date"]])
        if on is None or on.isoformat() == TRANSPLANTED:
            continue
        key = (LIGHT[str(row[column["Light"]]).strip()], str(row[column["EC"]]).strip(), on)
        for quantity, value in _measured(row, column).items():
            samples[(*key, quantity)].append(value)
    return [
        Target(
            zone=zone,
            ec=ec,
            on=on,
            quantity=quantity,
            mean=mean(values),
            standard_error=stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None,
            plants=len(values),
        )
        for (zone, ec, on, quantity), values in sorted(samples.items())
    ]


def objective(
    readings: Mapping[tuple[str, date], Midnight],
    goals: Sequence[Target],
    quantities: Sequence[str],
) -> float:
    """Decision 0076's objective: the sum of squared log ratios, each side
    raised by half the smallest mean above zero of its quantity."""
    held = [goal for goal in goals if goal.quantity in quantities]
    floors = {
        quantity: min(g.mean for g in held if g.quantity == quantity and g.mean > 0) / 2
        for quantity in quantities
    }
    total = 0.0
    for goal in held:
        predicted = getattr(readings[(goal.zone, goal.on)], goal.quantity)
        if predicted is None:
            raise ValueError(f"the model gives no {goal.quantity}")
        floor = floors[goal.quantity]
        total += math.log((max(predicted, 0.0) + floor) / (goal.mean + floor)) ** 2
    return total


@dataclass(frozen=True)
class Model:
    """A model as the screen and the calibration run it: its quantities,
    its published parameters, and how it runs a zone."""

    name: str
    quantities: tuple[str, ...]
    published: BaseModel
    run: Callable[[BaseModel, Transplant, Sequence[Any]], list[Midnight]]


TOMGRO: Final = Model(
    "tomgro",
    TOMGRO_QUANTITIES,
    TomgroParameters(),
    lambda p, t, h: run_tomgro(_as(p, TomgroParameters), t, h),
)
VANTHOOR: Final = Model(
    "vanthoor_katzin",
    VANTHOOR_QUANTITIES,
    VanthoorParameters(),
    # Its buffer starts at the least below which its growth stops (its manifest).
    lambda p, t, h: run_vanthoor(
        _as(p, VanthoorParameters), t, h, _as(p, VanthoorParameters).c_buf_min
    ),
)


def readings_of(
    model: Model,
    parameters: BaseModel,
    transplant: Transplant,
    zones: Mapping[str, Sequence[Any]],
) -> dict[tuple[str, date], Midnight]:
    """Each zone's midnights, by zone and the day each begins."""
    found: dict[tuple[str, date], Midnight] = {}
    for zone, hours in zones.items():
        for midnight in model.run(parameters, transplant, hours):
            found[(zone, midnight.at.astimezone(DAYS).date())] = midnight
    return found


def screen(
    model: Model,
    transplant: Transplant,
    zones: Mapping[str, Sequence[Any]],
    goals: Sequence[Target],
) -> dict[str, Any]:
    """The objective at the published parameters, and at each screened one
    moved alone, ranked by the largest change."""

    def score(parameters: BaseModel) -> float:
        return objective(readings_of(model, parameters, transplant, zones), goals, model.quantities)

    published = score(model.published)
    moved: list[dict[str, Any]] = []
    for name, value in model.published.model_dump().items():
        if name in FIXED or not isinstance(value, float) or value == 0:
            continue
        scores: dict[str, float | str] = {}
        for step in SCREEN_STEPS:
            try:
                scores[str(step)] = score(model.published.model_copy(update={name: value * step}))
            except (ValueError, ArithmeticError) as refused:
                scores[str(step)] = f"refused: {refused}"
        numbers = [s for s in scores.values() if isinstance(s, float)]
        change = max((abs(s - published) for s in numbers), default=math.inf)
        moved.append({"parameter": name, "published": value, "objective": scores, "change": change})
    moved.sort(key=lambda each: -each["change"])
    return {"model": model.name, "objective": published, "screened": moved}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("drivers_dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=None, help="override GREENHOUSE_DATA_DIR")
    arguments = parser.parse_args(argv)
    archive = archive_path(DataDirectory(arguments.data_dir), PRETRIAL, PRETRIAL_ARCHIVE)
    transplant = transplants(archive)
    goals = targets(archive)
    zones = {
        zone: read_series((arguments.drivers_dir / f"{PRETRIAL}_{zone}.csv").read_text())
        for zone in PRETRIAL_ZONES
    }
    report = {
        "targets": [
            {**t.__dict__, "on": t.on.isoformat()}
            for t in goals
            if t.quantity in VANTHOOR_QUANTITIES
        ],
        "screens": [screen(model, transplant, zones, goals) for model in (TOMGRO, VANTHOOR)],
    }
    sys.stdout.write(report_text(report))
    return 0


def report_text(report: Mapping[str, Any]) -> str:
    """The screen as JSON, a target or a screened parameter to a line, so
    that a change to it reads as the lines that changed."""

    def line(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, default=_finite)

    targets = ",\n".join(f"  {line(each)}" for each in report["targets"])
    screens = []
    for each in report["screens"]:
        screened = ",\n".join(f"    {line(moved)}" for moved in each["screened"])
        screens.append(
            f'  {{"model": {line(each["model"])}, "objective": {line(each["objective"])},'
            f' "screened": [\n{screened}\n  ]}}'
        )
    return f'{{\n "targets": [\n{targets}\n ],\n "screens": [\n{",\n".join(screens)}\n ]\n}}\n'


def _measured(row: Sequence[object], column: Mapping[str, int]) -> dict[str, float]:
    """A sampled plant's targets, without an organ dried heavier than fresh."""
    found: dict[str, float] = {}
    impossible = False
    for organ, (dry, fresh) in ORGANS.items():
        dry_g, fresh_g = _number(row[column[dry]]), _number(row[column[fresh]])
        if dry_g is not None and fresh_g is not None and dry_g > fresh_g:
            impossible = True
            continue
        if organ == "leaves" and dry_g is not None:
            found[LEAVES] = dry_g
        elif organ == "stem" and dry_g is not None:
            found[STEM] = dry_g
        elif organ == "fruits":
            if dry_g is not None:
                found[FRUIT] = dry_g
            elif fresh_g == 0:
                found[FRUIT] = 0.0
    whole = _number(row[column[WHOLE]])
    if whole is not None and not impossible:
        found[DRY_WEIGHT] = whole
    area, plants = _number(row[column[LEAF_AREA]]), _number(row[column[DENSITY]])
    if area is not None and plants is not None:
        found[LAI] = area / CM2_A_M2 * plants
    return found


def _day(cell: object) -> date | None:
    return cell.date() if isinstance(cell, datetime) else None


def _number(cell: object) -> float | None:
    if isinstance(cell, bool) or not isinstance(cell, int | float):
        return None
    return None if math.isnan(cell) else float(cell)


def _as[ParametersT: BaseModel](parameters: BaseModel, kind: type[ParametersT]) -> ParametersT:
    if not isinstance(parameters, kind):
        raise TypeError(f"{kind.__name__} expected, not {type(parameters).__name__}")
    return parameters


def _finite(value: object) -> object:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    raise TypeError(f"{value!r} is not JSON")


if __name__ == "__main__":
    raise SystemExit(main())
