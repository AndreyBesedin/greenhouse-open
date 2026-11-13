"""Sourisseau et al. (2026)'s indoor climate reproduced in OpenModelica:
TiGwerLib's global model, unchanged, simulated from its season's start to
the end of one of the paper's figures' windows, and compared with the
paper's own simulated series at every moment of the window.

    python -m research.modelica.sourisseau_2026 FOLDER WORKDIR fig8

FOLDER is one `openmodelica setup` made, which holds the paper's dataset
too. What is compared, where and within which tolerances is stated in
`sourisseau_2026.json`, committed before any run. The report goes to
`results/<window>.json` beside it, with each day's RMSE against the
measurements, ours and the paper's.
"""

import argparse
import csv
import io
import json
import math
import subprocess
import sys
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from research.modelica import openmodelica as om

HERE: Final = Path(__file__).parent
MANIFEST: Final = HERE / "sourisseau_2026.json"
RESULTS: Final = HERE / "results"
# The variables compared, as the model names them.
VARIABLES: Final = ("MainAir.T", "MainAir.RH")
# The regular expression that keeps only them in the results.
KEPT: Final = r"MainAir\\.(T|RH)"


@dataclass(frozen=True)
class Window:
    name: str
    start_s: int
    end_s: int


# A series: each moment, in seconds on the dataset's clock, with its value.
type Series = dict[int, float]


def manifest() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return loaded


def window(name: str) -> Window:
    given = manifest()["windows"][name]
    return Window(name, int(given["start_s"]), int(given["end_s"]))


def reference_series(archive: Path) -> tuple[dict[str, Series], dict[str, Series]]:
    """The paper's simulated series and the measured ones, by variable,
    read from its dataset's archive."""
    series = manifest()["reference"]["series"]
    rows = _csv_rows(archive, series["member"])
    simulated = {v: _column(rows, series["simulated"][v]) for v in VARIABLES}
    measured = {v: _column(rows, series["measured"][v]) for v in VARIABLES}
    return simulated, measured


def papers_daily_rmse(archive: Path) -> dict[str, Series]:
    """The paper's own daily RMSE against the measurements, from its Fig 10
    data, by variable, each day stamped with its end."""
    daily = manifest()["reference"]["daily_rmse"]
    rows = _csv_rows(archive, daily["member"])
    return {v: _column(rows, daily["columns"][v]) for v in VARIABLES}


def our_series(results: Path) -> dict[str, Series]:
    """OpenModelica's results, as its CSV output writes them."""
    with results.open(encoding="utf-8", newline="") as text:
        rows = list(csv.DictReader(text))
    return {v: _column(rows, v, time="time") for v in VARIABLES}


def compare(
    ours: Mapping[str, Series],
    reference: Mapping[str, Series],
    *,
    measured: Mapping[str, Series],
    papers_daily: Mapping[str, Series],
    at: Window,
    tolerances: Mapping[str, float],
) -> dict[str, Any]:
    """The report: for each variable, how ours differs from the reference
    at every moment of the window, its two ends included, against its
    tolerance; and each day's RMSE against the measurements, ours, the
    paper's from the same series, and the paper's own."""
    moments = range(at.start_s, at.end_s + om.INTERVAL_S, om.INTERVAL_S)
    report: dict[str, Any] = {}
    for variable in VARIABLES:
        tolerance = tolerances[variable]
        missing = [t for t in moments if t not in ours[variable] or t not in reference[variable]]
        both = [t for t in moments if t in ours[variable] and t in reference[variable]]
        differences = {t: ours[variable][t] - reference[variable][t] for t in both}
        beyond = [t for t, d in differences.items() if abs(d) > tolerance]
        largest = max(differences, key=lambda t: abs(differences[t]), default=None)
        report[variable] = {
            "tolerance": tolerance,
            "moments": len(moments),
            "compared": len(both),
            "missing": len(missing),
            "beyond_tolerance": len(beyond),
            "first_beyond_s": beyond[0] if beyond else None,
            "largest_difference": None if largest is None else differences[largest],
            "largest_at_s": largest,
            "mean_difference": _mean(differences.values()),
            "rmse_difference": _rmse(differences.values()),
            "within": not missing and not beyond,
            "days": _days(
                ours[variable], reference[variable], measured[variable], papers_daily[variable], at
            ),
        }
    return report


def reproduce(folder: Path, workdir: Path, at: Window) -> dict[str, Any]:
    """Builds and simulates the model to the window's end in `workdir`,
    compares it, and answers the report."""
    archive = folder / om.SOURISSEAU_DATASET.name
    if not archive.is_file():
        raise om.PinRefused(f"{archive} is not there: run `openmodelica setup {folder}` first")
    given = manifest()
    build = om.build_global_model(folder, workdir, at.end_s, variables=KEPT, output_format="csv")
    simulate = om.simulate_global_model(folder, workdir, given["ours"]["solver"])
    reference, measured = reference_series(archive)
    report = compare(
        our_series(workdir / om.RESULTS[1]),
        reference,
        measured=measured,
        papers_daily=papers_daily_rmse(archive),
        at=at,
        tolerances={v: float(given["tolerances"][v]) for v in VARIABLES},
    )
    return {
        "window": {"name": at.name, **given["windows"][at.name]},
        "stated_in": _last_commit(MANIFEST),
        "run": {
            "image": om.IMAGE,
            "solver": given["ours"]["solver"],
            "tolerance": om.TOLERANCE,
            "simulated_s": at.end_s - om.START_S,
            "build_s": round(build.seconds),
            "build_peak_bytes": build.peak_bytes,
            "simulate_s": round(simulate.seconds),
            "simulate_peak_bytes": simulate.peak_bytes,
        },
        "compared": report,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("window", choices=sorted(manifest()["windows"]))
    arguments = parser.parse_args(argv)
    try:
        report = reproduce(arguments.folder, arguments.workdir, window(arguments.window))
    except (om.OpenModelicaUnavailable, om.PinRefused, om.CheckFailed) as error:
        raise SystemExit(str(error)) from error
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{arguments.window}.json"
    path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for variable in VARIABLES:
        found = report["compared"][variable]
        sys.stdout.write(
            f"{variable}: {found['beyond_tolerance']} of {found['moments']} moments beyond "
            f"{found['tolerance']}, largest {found['largest_difference']}, "
            f"RMSE {found['rmse_difference']}\n"
        )
    sys.stdout.write(f"report: {path}\n")
    return 0


def _days(
    ours: Series, reference: Series, measured: Series, papers: Series, at: Window
) -> list[dict[str, Any]]:
    """Each day of the window, midnight to midnight: the RMSE against the
    measurements of ours and of the paper's series, over its moments from
    its start, and the paper's own, which its Fig 10 data stamps with the
    day's end."""
    days = []
    for start in range(at.start_s, at.end_s, om.DAY_S):
        moments = range(start, start + om.DAY_S, om.INTERVAL_S)
        days.append(
            {
                "start_s": start,
                "ours": _rmse(
                    ours[t] - measured[t] for t in moments if t in ours and t in measured
                ),
                "papers_series": _rmse(
                    reference[t] - measured[t] for t in moments if t in reference and t in measured
                ),
                "papers_own": papers.get(start + om.DAY_S),
            }
        )
    return days


def _csv_rows(archive: Path, member: str) -> list[dict[str, str]]:
    """A CSV member of the dataset's archive, as rows by column. The
    figures' files open with a line of empty cells before their header."""
    with zipfile.ZipFile(archive) as unpacked:
        text = unpacked.read(member).decode("utf-8")
    lines = text.splitlines()
    while lines and not lines[0].strip(", "):
        lines.pop(0)
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def _column(rows: Iterable[Mapping[str, str]], name: str, *, time: str = "Time") -> Series:
    return {
        round(float(row[time])): float(row[name])
        for row in rows
        if row.get(time, "").strip() and row.get(name, "").strip()
    }


def _mean(values: Iterable[float]) -> float | None:
    given = list(values)
    return sum(given) / len(given) if given else None


def _rmse(values: Iterable[float]) -> float | None:
    given = list(values)
    return math.sqrt(sum(v * v for v in given) / len(given)) if given else None


def _last_commit(path: Path) -> str:
    found = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", path.name],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    return found.stdout.strip()


if __name__ == "__main__":
    sys.exit(main())
