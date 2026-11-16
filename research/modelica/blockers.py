"""How much of the gap between the simulator's indoor air temperature and
TiGwerLib's each blocker accounts for (item 6 of the research priorities):
TiGwerLib run again with one blocker taken out at a time, and with all of
them at once, in the comparison's own harness.

    python -m research.modelica.blockers run FOLDER WORKDIR fig8 screens
    python -m research.modelica.blockers apportion

The variants, how each is made, what is measured and how the gap is
attributed are stated in `blockers.json`, committed before any run. A
variant extends TiGwerLib's global model, unchanged, with modifiers on its
components; none edits an equation. `run` writes its report to
`results/blockers/<variant>_<window>.json`, with the comparison's numbers
alone; `apportion` reads the reports committed, and the comparison's own
as the baseline, and prints the attribution.
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from research.modelica import openmodelica as om
from research.modelica import simulator_comparison as comparison
from research.modelica import sourisseau_2026 as repro
from research.modelica.sourisseau_2026 import Window

HERE: Final = Path(__file__).parent
MANIFEST: Final = HERE / "blockers.json"
RESULTS: Final = HERE / "results" / "blockers"
BASELINE: Final = HERE / "results"
# The variant all the others make together.
ALL: Final = "all"
# The parts of a window a gap is measured over, as a report names them.
PARTS: Final = ("all moments", "sun_up", "sun_down")


@dataclass(frozen=True)
class Variant:
    """TiGwerLib's global model with blockers taken out: by component, the
    modifiers that take them out."""

    name: str
    modifiers: Mapping[str, Mapping[str, str]]

    @property
    def model(self) -> str:
        return f"CTIFLWithout_{self.name}"

    def source(self) -> str:
        """The model, in Modelica: TiGwerLib's global model extended with
        the variant's modifiers."""
        modified = ",\n".join(
            f"    {component}({', '.join(f'{key}={value}' for key, value in values.items())})"
            for component, values in self.modifiers.items()
        )
        return (
            f'model {self.model} "TiGwerLib\'s global model, its variant {self.name}"\n'
            f"  extends {om.MODEL}(\n{modified});\n"
            f"end {self.model};\n"
        )


def manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return loaded


def variants() -> dict[str, Variant]:
    """Each variant the statement names: the single ones by their own
    modifiers, and `all` by every one of theirs."""
    given = manifest()["variants"]
    single = {
        name: Variant(name, _parsed(stated["modifiers"]))
        for name, stated in given.items()
        if "modifiers" in stated
    }
    together: dict[str, dict[str, str]] = {}
    for name in given[ALL]["of"]:
        for component, values in single[name].modifiers.items():
            merged = together.setdefault(component, {})
            repeated = set(merged) & set(values)
            if repeated:
                raise ValueError(f"{name} modifies {component}'s {sorted(repeated)} again")
            merged.update(values)
    return {**single, ALL: Variant(ALL, together)}


def _parsed(stated: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """A variant's modifiers as the statement writes them, `key=value` and
    comma-separated, by component."""
    modifiers = {}
    for component, written in stated.items():
        values = {}
        for pair in written.split(","):
            key, value = (part.strip() for part in pair.split("=", 1))
            values[key] = value
        modifiers[component] = values
    return modifiers


def run(folder: Path, workdir: Path, at: Window, variant: Variant) -> dict[str, Any]:
    """The comparison's run, with `variant` in TiGwerLib's global model's
    place, and its report."""
    workdir.mkdir(parents=True, exist_ok=True)
    source = f"{variant.model}.mo"
    (workdir / source).write_text(variant.source(), encoding="utf-8")
    report = comparison.run(folder, workdir, at, model=variant.model, sources=[source])
    return {
        "variant": {"name": variant.name, "modifiers": variant.modifiers},
        "stated_in": comparison.last_commit(MANIFEST),
        "comparison_stated_in": report.pop("stated_in"),
        **report,
    }


def gap(report: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """A report's gap: the mean and the RMSE of the difference over all the
    window's moments, with the sun up and with it down."""
    found = report["compared"]["MainAir.T"]
    parts = {"all moments": found, "sun_up": found["sun_up"], "sun_down": found["sun_down"]}
    return {
        part: {"mean": float(given["mean_difference"]), "rmse": float(given["rmse_difference"])}
        for part, given in parts.items()
    }


def apportion(
    baseline: Mapping[str, Any], reports: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """For one window: how far each variant moves the gap from the
    baseline's, the blockers ranked by how far they take its RMSE down over
    all moments, and the single moves' sum beside the all-at-once move."""
    before = gap(baseline)
    moves: dict[str, dict[str, dict[str, float]]] = {}
    for name, report in reports.items():
        after = gap(report)
        moves[name] = {
            part: {
                "rmse": after[part]["rmse"],
                "mean": after[part]["mean"],
                "rmse_closed": before[part]["rmse"] - after[part]["rmse"],
                "mean_moved": after[part]["mean"] - before[part]["mean"],
                "share_of_mean": (before[part]["mean"] - after[part]["mean"])
                / before[part]["mean"],
            }
            for part in PARTS
        }
    singles = [name for name in moves if name != ALL]
    together = {}
    if ALL in moves:
        for part in PARTS:
            for measure in ("rmse_closed", "mean_moved"):
                summed = sum(moves[name][part][measure] for name in singles)
                together[f"{part}: {measure}"] = {
                    "sum_of_singles": summed,
                    "all_at_once": moves[ALL][part][measure],
                    "interaction": moves[ALL][part][measure] - summed,
                }
    return {
        "baseline": before,
        "moves": moves,
        "ranking": sorted(
            singles, key=lambda name: moves[name]["all moments"]["rmse_closed"], reverse=True
        ),
        "together": together,
    }


def reports_for(window: str) -> dict[str, dict[str, Any]]:
    """The variants' reports committed for `window`, by variant."""
    found = {}
    for name in variants():
        path = RESULTS / f"{name}_{window}.json"
        if path.is_file():
            found[name] = json.loads(path.read_text(encoding="utf-8"))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    running = commands.add_parser("run")
    running.add_argument("folder", type=Path)
    running.add_argument("workdir", type=Path)
    running.add_argument("window", choices=sorted(repro.manifest()["windows"]))
    running.add_argument("variant", choices=sorted(variants()))
    commands.add_parser("apportion")
    arguments = parser.parse_args(argv)
    if arguments.command == "apportion":
        attribution = {
            window: apportion(
                json.loads((BASELINE / f"simulator_{window}.json").read_text(encoding="utf-8")),
                reports_for(window),
            )
            for window in sorted(repro.manifest()["windows"])
        }
        sys.stdout.write(json.dumps(attribution, indent=1) + "\n")
        return 0
    variant = variants()[arguments.variant]
    try:
        report = run(arguments.folder, arguments.workdir, repro.window(arguments.window), variant)
    except (om.OpenModelicaUnavailable, om.PinRefused, om.CheckFailed) as error:
        raise SystemExit(str(error)) from error
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{variant.name}_{arguments.window}.json"
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    found = report["compared"]["MainAir.T"]
    sys.stdout.write(
        f"{variant.name}, {arguments.window}: RMSE of the difference {found['rmse_difference']}, "
        f"mean {found['mean_difference']}\nreport: {path}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
