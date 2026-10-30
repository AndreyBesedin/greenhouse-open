"""Runs the reference implementation on the reproduction's drivers.

Run with the reference's own interpreter, from `setup.sh`, given where its
source was unpacked:

    <folder>/venv/bin/python run_reference.py <source> <drivers.csv> <output.csv>

It calls the reference's own `run_simul`, unmodified, with the parameter
set and the experiment's inputs the manifest names, read from the
reference's tables. The tables are read here, as Latin-1, rather than by
the reference's `dictFromCSV`, which opens them with the platform's
encoding. It writes each day's five states, from day 0, every value as
Python writes a float, so that nothing is lost.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE.parent / "manifest.json").read_text())
STATES = ("n", "lai", "w", "wf", "wm")


def _table(path: Path, chosen: str) -> dict[str, float]:
    found: dict[str, float] = {}
    with path.open(encoding="latin-1", newline="") as file:
        for row in csv.reader(file):
            if len(row) > 2 and row[2] in (chosen, "all"):
                found[row[0]] = float(row[1])
    return found


def main(source: Path, drivers: Path, output: Path) -> None:
    sys.path.insert(0, str(source))
    import numpy as np
    import pandas as pd
    from simulations.run_Model_ReducedTomgro import run_simul

    tables = source / "tables" / "parameters_inputs"
    params = _table(tables / "tomgro_p.csv", MANIFEST["parameter_set"])
    info = _table(tables / "tomgro_i.csv", MANIFEST["inputs_set"])
    initial = MANIFEST["initial_state"]
    states = {name: np.array(float(initial[name]), ndmin=1) for name in STATES}
    rates = {
        rate: np.array(0.0, ndmin=1) for rate in ("dn_dt", "dlai_dt", "dw_dt", "dwf_dt", "dwm_dt")
    }
    weather = pd.read_csv(drivers)
    weather["radiation_unit"] = "mmolPAR"
    state_it, _, _, _ = run_simul(info, params, rates, states, weather)
    with output.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("dat", *STATES))
        for day, row in enumerate(state_it.reshape(-1, len(STATES))):
            writer.writerow((day, *(repr(float(value)) for value in row)))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
