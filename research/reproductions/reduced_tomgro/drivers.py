"""The reproduction's drivers: a synthetic season, hour by hour.

Written for the reproduction, so that nothing in it is borrowed or
licensed: a day's course of the greenhouse air's temperature, the PPFD
inside it and its CO₂, varied from day to day by fixed rules, over a
season. Both implementations, this one and the reference, read the same
file it writes (`drivers.csv`), whose checksum the manifest pins.

    python -m research.reproductions.reduced_tomgro.drivers

Each row is one hour of one day: `dat` (the day after transplanting, from
1), `hour` (0 to 23), `tmean` (the hour's mean air temperature, °C), `rad`
(the hour's mean PPFD inside the greenhouse, µmol m⁻² s⁻¹) and `co2`
(ppm). The hours carry no time zone: a day is 24 rows, its hour 0 its
first.
"""

import csv
import hashlib
import math
from pathlib import Path
from typing import Final

HERE: Final = Path(__file__).resolve().parent
DRIVERS: Final = HERE / "drivers.csv"
DAYS: Final = 120
HOURS: Final = 24
# The air: a mean that warms through the season, and a day's swing about
# it, warmest at 15:00.
MEAN_START_C: Final = 18.0
MEAN_WARMING_C_PER_DAY: Final = 0.06
SWING_C: Final = 4.5
WARMEST_HOUR: Final = 15
# The light: a day's arc from 06:00 to 18:00, its noon's height varied by a
# week's cycle of cloud.
SUNRISE_HOUR: Final = 6
SUNSET_HOUR: Final = 18
NOON_PPFD: Final = 900.0
CLOUD_CYCLE_DAYS: Final = 7.0
CLEAREST: Final = 1.0
CLOUDIEST: Final = 0.35
# The CO₂: lower by day, as a crop and vents draw it down, higher by night.
CO2_NIGHT_PPM: Final = 520.0
CO2_DAY_PPM: Final = 420.0
COLUMNS: Final = ("dat", "hour", "tmean", "rad", "co2")


def temperature_c(day: int, hour: int) -> float:
    mean = MEAN_START_C + MEAN_WARMING_C_PER_DAY * (day - 1)
    return mean + SWING_C * math.cos(2 * math.pi * (hour - WARMEST_HOUR) / HOURS)


def ppfd(day: int, hour: int) -> float:
    if not SUNRISE_HOUR < hour < SUNSET_HOUR:
        return 0.0
    clearness = CLOUDIEST + (CLEAREST - CLOUDIEST) * 0.5 * (
        1 + math.cos(2 * math.pi * (day - 1) / CLOUD_CYCLE_DAYS)
    )
    arc = math.sin(math.pi * (hour - SUNRISE_HOUR) / (SUNSET_HOUR - SUNRISE_HOUR))
    return NOON_PPFD * clearness * arc


def co2_ppm(hour: int) -> float:
    return CO2_DAY_PPM if SUNRISE_HOUR < hour < SUNSET_HOUR else CO2_NIGHT_PPM


def rows() -> list[tuple[int, int, float, float, float]]:
    return [
        (day, hour, temperature_c(day, hour), ppfd(day, hour), co2_ppm(hour))
        for day in range(1, DAYS + 1)
        for hour in range(HOURS)
    ]


def write(path: Path = DRIVERS) -> str:
    """Writes the series, each value to 12 decimals, and answers its
    sha256."""
    with path.open("w", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(COLUMNS)
        for day, hour, tmean, rad, co2 in rows():
            writer.writerow([day, hour, f"{tmean:.12f}", f"{rad:.12f}", f"{co2:.12f}"])
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    print(write())
