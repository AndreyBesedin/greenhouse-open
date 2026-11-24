"""The sky's temperature over a house (P24.3, decision 0078): what the
cover radiates its longwave to, a black body at that temperature.

- **As the weather records it:** its sky temperature where it gives one;
  otherwise a black body's that radiates the downward longwave it records,
  T = (L / sigma)^(1/4).
- **Or estimated** from the air's temperature, its humidity and the cloud
  cover, where the weather records neither: the air's emissivity under a
  clear sky by Prata (1996), ε_clr = 1 - (1 + w) exp(-(1.2 + 3 w)^(1/2)),
  w = 46.5 e / T for the vapour pressure e in hPa and the air's temperature
  T in K; corrected for a cloud cover c, a fraction of the sky, by Unsworth
  and Monteith (1975), ε = (1 - 0.84 c) ε_clr + 0.84 c, as Flerchinger et
  al. (2009, Water Resources Research 45, W03423, Tables 1 and 2) write
  both; and the sky the black body that radiates ε sigma T⁴,
  T_sky = ε^(1/4) T.
"""

import math
from typing import Final

from greenhouse_sim.climate.psychrometrics import saturation_pressure_pa
from greenhouse_sim.units import KELVIN, PERCENT, STEFAN_BOLTZMANN_W_M2K4
from greenhouse_sim.weather.state import WeatherState

PA_PER_HPA: Final = 100.0
# Prata (1996): the precipitable water's index, per hPa of vapour pressure
# and K of the air's temperature, and the formula's own constants.
PRATA_WATER_PER_HPA_K: Final = 46.5
PRATA_OFFSET: Final = 1.2
PRATA_PER_WATER: Final = 3.0
# Unsworth and Monteith (1975): what a cloud adds, as a share of a black
# body's emissivity.
CLOUD_EMISSIVITY: Final = 0.84


def clear_sky_emissivity(air_c: float, vapour_hpa: float) -> float:
    """The air's emissivity under a clear sky, by Prata (1996)."""
    water = PRATA_WATER_PER_HPA_K * vapour_hpa / (air_c + KELVIN)
    return 1.0 - (1.0 + water) * math.exp(-math.sqrt(PRATA_OFFSET + PRATA_PER_WATER * water))


def sky_emissivity(air_c: float, vapour_hpa: float, cloud_share: float) -> float:
    """The air's emissivity under a cloud cover of `cloud_share`, from 0 to
    1, by Unsworth and Monteith (1975)."""
    clear = clear_sky_emissivity(air_c, vapour_hpa)
    return (1.0 - CLOUD_EMISSIVITY * cloud_share) * clear + CLOUD_EMISSIVITY * cloud_share


def sky_temperature_c(weather: WeatherState) -> float:
    """The sky's temperature under `weather`: see the module."""
    if weather.sky_temperature_c is not None:
        return weather.sky_temperature_c
    if weather.downward_longwave_w_m2 is not None:
        return float((weather.downward_longwave_w_m2 / STEFAN_BOLTZMANN_W_M2K4) ** 0.25 - KELVIN)
    vapour_hpa = (
        weather.relative_humidity_pct
        / PERCENT
        * float(saturation_pressure_pa(weather.air_temperature_c))
        / PA_PER_HPA
    )
    emissivity = sky_emissivity(
        weather.air_temperature_c, vapour_hpa, weather.cloud_cover_pct / PERCENT
    )
    return float(emissivity**0.25 * (weather.air_temperature_c + KELVIN) - KELVIN)
