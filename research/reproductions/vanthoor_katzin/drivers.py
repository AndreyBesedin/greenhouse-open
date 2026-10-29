"""The reproduction's drivers: the synthetic season of the TOMGRO one.

The same numbers as `reduced_tomgro/drivers.csv`, so that the two models
are driven alike: each hour's air temperature taken as the canopy's
temperature, its PPFD inside the greenhouse as the PAR above the canopy,
and its CO₂. They are written in the columns GreenLight reads (`drivers.csv`),
and both implementations read that file, whose checksum the manifest pins.

    python -m research.reproductions.vanthoor_katzin.drivers

Each row is one moment: `Time` (s from the season's start, hour `h` of day
`d` at `((d - 1) * 24 + h) * 3600`), `tCan` (°C), `parGh` (µmol photons
m⁻² s⁻¹) and `co2InPpm` (ppm). Between rows the values are interpolated
linearly, as `model.Drivers` says.
"""

import csv
import hashlib
from pathlib import Path
from typing import Final

from research.reproductions.reduced_tomgro import drivers as season

HERE: Final = Path(__file__).resolve().parent
DRIVERS: Final = HERE / "drivers.csv"
SECONDS_PER_HOUR: Final = 3600
COLUMNS: Final = ("Time", "tCan", "parGh", "co2InPpm")


def rows() -> list[tuple[int, float, float, float]]:
    return [
        (((day - 1) * season.HOURS + hour) * SECONDS_PER_HOUR, tmean, rad, co2)
        for day, hour, tmean, rad, co2 in season.rows()
    ]


def write(path: Path = DRIVERS) -> str:
    """Writes the series, each value to 12 decimals, and answers its
    sha256."""
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(COLUMNS)
        for time, t_can, par_gh, co2 in rows():
            writer.writerow([time, f"{t_can:.12f}", f"{par_gh:.12f}", f"{co2:.12f}"])
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    print(write())
