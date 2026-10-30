"""The reproduction's drivers: the synthetic season of the TOMGRO one.

The same numbers as `reduced_tomgro/drivers.csv`, so that the two models
are driven alike: each hour's air temperature taken as the canopy's
temperature, its PPFD inside the greenhouse as the PAR above the canopy,
and its CO₂, in the columns GreenLight reads. They are made, not committed
(decision 0063, rule 2): the comparison makes them in memory, and the
reference reads them from the file this writes,

    python -m research.reproductions.vanthoor_katzin.drivers <drivers.csv>

which prints their sha256, the one the manifest pins.

Each row is one moment: `Time` (s from the season's start, hour `h` of day
`d` at `((d - 1) * 24 + h) * 3600`), `tCan` (°C), `parGh` (µmol photons
m⁻² s⁻¹) and `co2InPpm` (ppm). Between rows the values are interpolated
linearly, as `model.Drivers` says.
"""

import csv
import hashlib
import io
import sys
from pathlib import Path
from typing import Final

from research.reproductions.reduced_tomgro import drivers as season

SECONDS_PER_HOUR: Final = 3600
COLUMNS: Final = ("Time", "tCan", "parGh", "co2InPpm")


def rows() -> list[tuple[int, float, float, float]]:
    return [
        (((day - 1) * season.HOURS + hour) * SECONDS_PER_HOUR, tmean, rad, co2)
        for day, hour, tmean, rad, co2 in season.rows()
    ]


def csv_text() -> str:
    """The series as GreenLight reads it, each value to 12 decimals."""
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(COLUMNS)
    for time, t_can, par_gh, co2 in rows():
        writer.writerow([time, f"{t_can:.12f}", f"{par_gh:.12f}", f"{co2:.12f}"])
    return text.getvalue()


def write(path: Path) -> str:
    """Writes the series to `path` and answers its sha256."""
    content = csv_text().encode()
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    print(write(Path(sys.argv[1])))
