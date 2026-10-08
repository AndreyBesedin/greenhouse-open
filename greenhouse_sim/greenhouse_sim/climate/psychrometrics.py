"""Moist air, as a climate run carries it (P05.4).

The air's water is carried as its humidity ratio, grams of water per
kilogram of air, which mixing conserves. Its relative humidity follows from
that and its temperature: the share of the water vapour's pressure in what
the air could hold at that temperature, its saturation pressure, by Buck's
equation over water (1996), at standard atmospheric pressure.

Everything here takes NumPy arrays as well as single numbers.
"""

from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

# Standard atmospheric pressure, in pascals.
ATMOSPHERE_PA: Final = 101_325.0
# Water's molar mass over dry air's: grams of water per gram of air for each
# unit of vapour pressure share, times 1000 for grams per kilogram.
WATER_PER_AIR_G_KG: Final = 622.0
PERCENT: Final = 100.0
# Buck's (1996) saturation pressure over water: 611.21 Pa at 0 °C, with
# these constants.
_BUCK_ZERO_PA: Final = 611.21
_BUCK_A: Final = 18.678
_BUCK_B_C: Final = 234.5
_BUCK_C_C: Final = 257.14


def saturation_pressure_pa(temperature_c: ArrayLike) -> NDArray[np.float64]:
    """The water vapour pressure air at `temperature_c` holds at saturation."""
    t = np.asarray(temperature_c, dtype=float)
    return np.asarray(
        _BUCK_ZERO_PA * np.exp((_BUCK_A - t / _BUCK_B_C) * (t / (_BUCK_C_C + t))), dtype=float
    )


def humidity_ratio_g_kg(temperature_c: ArrayLike, relative_pct: ArrayLike) -> NDArray[np.float64]:
    """The grams of water per kilogram of air at a temperature and relative
    humidity."""
    vapour = np.asarray(relative_pct, dtype=float) / PERCENT * saturation_pressure_pa(temperature_c)
    return np.asarray(WATER_PER_AIR_G_KG * vapour / (ATMOSPHERE_PA - vapour), dtype=float)


def saturation_ratio_g_kg(temperature_c: ArrayLike) -> NDArray[np.float64]:
    """The most water air at `temperature_c` holds, in grams per kilogram."""
    return humidity_ratio_g_kg(temperature_c, PERCENT)


def relative_humidity_pct(temperature_c: ArrayLike, ratio_g_kg: ArrayLike) -> NDArray[np.float64]:
    """The relative humidity of air at a temperature holding `ratio_g_kg`."""
    ratio = np.asarray(ratio_g_kg, dtype=float)
    vapour = ratio * ATMOSPHERE_PA / (WATER_PER_AIR_G_KG + ratio)
    return np.asarray(PERCENT * vapour / saturation_pressure_pa(temperature_c), dtype=float)
