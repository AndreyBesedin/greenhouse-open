"""Runs GreenLight 2.0.7's greenhouse, for a canopy's temperature beside its
air's.

    <its venv>/bin/python -I reference/greenhouse.py <scratch folder>

Katzin (2021)'s greenhouse with Vanthoor's crop (`main_katzin_2021.json`),
unmodified, on the Bleiswijk weather its wheel ships
(`input_data/test_data/Bleiswijk_from_20091020.csv`, BSD 3-Clause Clear,
from Katzin et al.'s 4TU data, doi:10.4121/78968E1B-EAEA-4F37-89F9-2B98BA3ED865.V2),
for its 110 days from 20 October 2009, at its default solver, its output
every 5 minutes. Its lamps are its high-pressure sodium ones.

It writes `forcing.csv` into the scratch folder: at each output moment,
the air's and the canopy's temperatures (°C), the CO₂ around the crop
(ppm), the PAR above the canopy from the sun and from the lamps, each in
µmol m⁻² s⁻¹ by GreenLight's own conversions, and its crop's six states
and fruit harvest rate. Every number is GreenLight's simulation, not a
measurement. Nothing here is kept in the repository (decision 0063, rule
1): it runs in the reference's own environment
(`research/reproductions/vanthoor_katzin/reference/setup.sh`).
"""

import csv
import sys
from importlib import resources
from pathlib import Path

import greenlight
from greenlight import GreenLight

VERSION = "2.0.7"
DEFINITIONS = "models/katzin_2021/definition"
WEATHER = "models/katzin_2021/input_data/test_data/Bleiswijk_from_20091020.csv"
DAYS = 110
OUTPUT_STEP_S = 300
# GreenLight's conversions of PAR from W m⁻² to µmol m⁻² s⁻¹: the sun's
# (parJtoUmolSun) and its lamps' (zetaLampPar, Katzin 2021, Table 4.3).
SUN_UMOL_PER_J = 4.6
LAMP_UMOL_PER_J = 5.4
STATES = ("cBuf", "cFruit", "cLeaf", "cStem", "tCanSum", "tCan24")


def main(scratch: Path) -> None:
    if greenlight.__version__ != VERSION:
        raise SystemExit(f"GreenLight {greenlight.__version__} is installed, not {VERSION}")
    package = resources.files("greenlight")
    folder = package / DEFINITIONS
    model = GreenLight(
        base_path=str(folder),
        input_prompt=[
            str(folder / "main_katzin_2021.json"),
            str(package / WEATHER),
            {
                "options": {
                    "t_start": "0",
                    "t_end": str(DAYS * 86400),
                    "output_step": str(OUTPUT_STEP_S),
                }
            },
        ],
        output_path=str((scratch / "greenlight.csv").resolve()),
    )
    model.load()
    constants = model.consts
    if (float(constants["parJtoUmolSun"]), float(constants["zetaLampPar"])) != (
        SUN_UMOL_PER_J,
        LAMP_UMOL_PER_J,
    ):
        raise SystemExit("GreenLight's PAR conversions are not the ones this reads")
    model.solve()
    if not model.states_sol.success:
        raise SystemExit(f"GreenLight's solver failed: {model.states_sol.message}")
    model.save()
    out = model.full_sol
    columns = {
        "Time": out["Time"],
        "tAir": out["tAir"],
        "tCan": out["tCan"],
        "co2InPpm": out["co2InPpm"],
        "parSun": SUN_UMOL_PER_J * out["rParGhSun"],
        "parLamp": LAMP_UMOL_PER_J * out["rParGhLamp"],
        **{name: out[name] for name in STATES},
        "mcFruitHar": out["mcFruitHar"],
    }
    with (scratch / "forcing.csv").open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(columns)
        for row in zip(*(column.to_numpy() for column in columns.values()), strict=True):
            writer.writerow([repr(float(value)) for value in row])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
