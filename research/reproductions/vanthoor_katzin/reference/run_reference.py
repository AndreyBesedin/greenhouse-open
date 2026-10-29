"""Runs the reference, GreenLight 2.0.7, on the reproduction's drivers.

    <its venv>/bin/python -I run_reference.py <drivers.csv> <reference folder> <scratch folder>

GreenLight runs unmodified: the crop's definition and the standalone
extension, as its `main_vanthoor_crop.json` composes them, with the
reproduction's drivers in place of that file's EnergyPlus series, from 0 s
to 120 days. It runs twice, with the manifest's two solver settings:

- `defaults.csv`: its default options, checked here before the run;
- `converged.csv`: the same, its tolerances tightened to the manifest's.

Each keeps, at the hourly output step, the six states, the leaf area index
and the rate of the fruit's harvest, every value in full (`repr`).

- `rates.csv`: the six states' rates of change as GreenLight works them
  out, the function it hands to scipy's `solve_ivp` kept by wrapping
  `solve_ivp` (which it then calls unchanged), evaluated at each half hour
  between output moments, at the converged run's states interpolated
  there: a check of the equations that no solver's step touches.

GreenLight writes its own output and logs into the scratch folder. This
runs in the reference's own environment (`setup.sh`), never the
repository's: nothing in the repository imports it.
"""

import csv
import sys
from collections.abc import Callable, Iterable, Sequence
from importlib import resources
from pathlib import Path
from typing import Any

import greenlight
import greenlight._solve._solve_ivp_from_str as solve_ivp_from_str
from greenlight import GreenLight

VERSION = "2.0.7"
DEFINITIONS = "models/katzin_2021/definition/vanthoor_2011"
CROP = "crop_vanthoor_2011_chapter_9_simplified.json"
STANDALONE = "extension_crop_vanthoor_2011_for_standalone.json"
SEASON_S = 120 * 86400
STATES = ("cBuf", "cFruit", "cLeaf", "cStem", "tCanSum", "tCan24")
# GreenLight's defaults, as the manifest records them.
DEFAULTS = {
    "solving_method": "solve_ivp_from_str",
    "solver": "BDF",
    "max_step": "3600",
    "atol": "1e-3",
    "rtol": "1e-6",
    "first_step": "None",
    "t_eval": "None",
    "output_step": "3600",
    "interpolation": "linear",
    "formatting_mode": "numpy",
    "expand_functions": "True",
    "expand_variables": "False",
    "clip_large_nums": "True",
    "nans_to_zeros": "True",
}
# The manifest's converged solver: the defaults, these two tightened.
CONVERGED = {"atol": "1e-7", "rtol": "1e-10"}
KEPT = ("Time", *STATES, "lai", "mcFruitHar")


def solve(
    drivers: Path, scratch: Path, name: str, options: dict[str, str]
) -> tuple[Any, Callable[..., Any], Sequence[Any]]:
    """GreenLight's run with these options, and the right-hand side and
    arguments it handed to `solve_ivp`."""
    folder = resources.files("greenlight") / DEFINITIONS
    model = GreenLight(
        base_path=str(folder),
        input_prompt=[
            str(folder / CROP),
            STANDALONE,
            str(drivers.resolve()),
            {"options": {"t_start": "0", "t_end": str(SEASON_S), **options}},
        ],
        output_path=str((scratch / f"greenlight_{name}.csv").resolve()),
    )
    model.load()
    expected = {**DEFAULTS, **options}
    differing = {
        key: model.options[key] for key, value in expected.items() if model.options[key] != value
    }
    if differing:
        raise SystemExit(f"GreenLight's options are not the manifest's: {differing}")
    handed: dict[str, Any] = {}
    unwrapped = solve_ivp_from_str.solve_ivp

    def keeping(fun: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        handed["fun"], handed["args"] = fun, kwargs["args"]
        return unwrapped(fun, *args, **kwargs)

    solve_ivp_from_str.solve_ivp = keeping
    try:
        model.solve()
    finally:
        solve_ivp_from_str.solve_ivp = unwrapped
    if not model.states_sol.success:
        raise SystemExit(f"GreenLight's solver failed: {model.states_sol.message}")
    model.save()
    return model.full_sol, handed["fun"], handed["args"]


def write(path: Path, header: Sequence[str], rows: Iterable[Sequence[float]]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([repr(float(value)) for value in row])


def main(drivers: Path, folder: Path, scratch: Path) -> None:
    if greenlight.__version__ != VERSION:
        raise SystemExit(f"GreenLight {greenlight.__version__} is installed, not {VERSION}")
    defaults, _, _ = solve(drivers, scratch, "defaults", {})
    write(
        folder / "defaults.csv",
        KEPT,
        zip(*(defaults[name].to_numpy() for name in KEPT), strict=True),
    )
    converged, rates, arguments = solve(drivers, scratch, "converged", CONVERGED)
    write(
        folder / "converged.csv",
        KEPT,
        zip(*(converged[name].to_numpy() for name in KEPT), strict=True),
    )
    times = converged["Time"].to_numpy()
    states = converged[list(STATES)].to_numpy()
    checked = []
    for k in range(len(times) - 1):
        t = (times[k] + times[k + 1]) / 2
        y = (states[k] + states[k + 1]) / 2
        checked.append([t, *y, *rates(t, y.copy(), *arguments)])
    write(folder / "rates.csv", ("Time", *STATES, *(f"rate_{name}" for name in STATES)), checked)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
