"""The sun's and the sky's light outside the greenhouse (P08.3).

- **Global horizontal irradiance (GHI):** the sun's and the sky's light
  together on a level surface, in W/m², as the weather's
  `global_radiation_w_m2` gives it. A clear sky's, for a weather that has
  none of its own, is Haurwitz's: GHI = 1098 cos Z e^(−0.057 / cos Z), Z the
  sun's zenith angle; nothing while the sun is down.
- **Above the atmosphere** the sun gives 1361 W/m² (the solar constant)
  square to its beam, 3.3% more at the earth's perihelion in early January
  and as much less at its aphelion in early July.
- **Clouds** dim a clear sky's light after Kasten and Czeplak (1980):
  by 1 − 0.75 (N/8)^3.4, N the cloud cover in oktas; a sky full of cloud
  passes a quarter (P08.7).
- **Beam and diffuse:** the beam, as direct normal irradiance (DNI), along
  the sun's direction, and the diffuse sky's light on a level surface
  (DHI), so that GHI = DNI cos Z + DHI. The diffuse share is Erbs's (Erbs,
  Klein and Duffie, 1982), by the clearness index k_t, the share of the
  light above the atmosphere that reaches the ground: nearly all under a
  dark sky, k_t up to 0.22; a polynomial in k_t up to 0.8; and 0.165 under
  the clearest. The beam never carries more than the sun gives above the
  atmosphere; any more is the sky's (P08.7).
- **PAR:** photosynthetically active radiation is taken as 47% of the
  global shortwave's energy, at 4.57 µmol of photons per joule: about
  2.15 µmol/m²/s for each W/m².
"""

import math
from datetime import UTC, datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, NonNegativeFloat

from greenhouse_sim.solar.position import SunPosition

# Haurwitz's clear sky: its scale, in W/m², and its attenuation's.
HAURWITZ_W_M2: Final = 1098.0
HAURWITZ_ATTENUATION: Final = 0.057
# The sun's irradiance above the atmosphere, square to its beam, at the
# earth's mean distance, in W/m²; how much the earth's orbit changes it
# through the year, and the day of the year it is greatest, near the
# perihelion.
SOLAR_CONSTANT_W_M2: Final = 1361.0
ORBIT_SHARE: Final = 0.033
DAYS_IN_A_YEAR: Final = 365.25
PERIHELION_DAY: Final = 3
# Kasten and Czeplak's dimming by clouds: its share and power, and the
# oktas a sky full of cloud has.
CLOUD_DIMMING: Final = 0.75
CLOUD_POWER: Final = 3.4
OKTAS: Final = 8.0
PERCENT: Final = 100.0
# Erbs's diffuse share: below the first clearness, a line; to the second, a
# polynomial, lowest power first; above it, a constant.
DARK_CLEARNESS: Final = 0.22
DARK_DIFFUSE: Final = (1.0, -0.09)
CLEAR_CLEARNESS: Final = 0.80
MIDDLING_DIFFUSE: Final = (0.9511, -0.1604, 4.388, -16.638, 12.336)
CLEAR_DIFFUSE: Final = 0.165
# PAR's share of the shortwave's energy, and the photons in a joule of it,
# in µmol.
PAR_SHARE: Final = 0.47
PAR_UMOL_PER_J: Final = 4.57
PAR_UMOL_M2_S_PER_W_M2: Final = PAR_SHARE * PAR_UMOL_PER_J


def par_umol_m2_s(irradiance_w_m2: float) -> float:
    """The photosynthetically active photons in shortwave light of
    `irradiance_w_m2`, in µmol/m²/s."""
    return irradiance_w_m2 * PAR_UMOL_M2_S_PER_W_M2


def extraterrestrial_w_m2(moment: datetime) -> float:
    """The sun's irradiance above the atmosphere, square to its beam, on
    `moment`'s day."""
    day = moment.astimezone(UTC).timetuple().tm_yday
    return SOLAR_CONSTANT_W_M2 * (
        1.0 + ORBIT_SHARE * math.cos(2.0 * math.pi * (day - PERIHELION_DAY) / DAYS_IN_A_YEAR)
    )


def clear_sky_ghi_w_m2(sun: SunPosition) -> float:
    """A clear sky's global horizontal irradiance under `sun`, by Haurwitz's
    model; nothing while it is down."""
    cos_zenith = math.sin(math.radians(sun.elevation_deg))
    if cos_zenith <= 0:
        return 0.0
    return HAURWITZ_W_M2 * cos_zenith * math.exp(-HAURWITZ_ATTENUATION / cos_zenith)


def cloud_factor(cloud_cover_pct: float) -> float:
    """The share of a clear sky's light a sky `cloud_cover_pct` clouded
    passes."""
    oktas = cloud_cover_pct / PERCENT * OKTAS
    return 1.0 - CLOUD_DIMMING * math.pow(oktas / OKTAS, CLOUD_POWER)


def _polynomial(coefficients: tuple[float, ...], x: float) -> float:
    total = 0.0
    for coefficient in reversed(coefficients):
        total = total * x + coefficient
    return total


def diffuse_share(clearness: float) -> float:
    """The diffuse sky's share of the global horizontal irradiance at a
    clearness index, by Erbs's correlation."""
    if clearness <= DARK_CLEARNESS:
        return _polynomial(DARK_DIFFUSE, clearness)
    if clearness <= CLEAR_CLEARNESS:
        return _polynomial(MIDDLING_DIFFUSE, clearness)
    return CLEAR_DIFFUSE


class OutsideLight(BaseModel):
    """The light outside at a moment: its global horizontal irradiance, its
    beam's direct normal irradiance and the diffuse sky's on a level
    surface, in W/m², and its PAR on a level surface, in µmol/m²/s."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ghi_w_m2: NonNegativeFloat
    dni_w_m2: NonNegativeFloat
    dhi_w_m2: NonNegativeFloat
    par_umol_m2_s: NonNegativeFloat


DARK: Final = OutsideLight(ghi_w_m2=0.0, dni_w_m2=0.0, dhi_w_m2=0.0, par_umol_m2_s=0.0)


def outside_light(ghi_w_m2: float, sun: SunPosition, moment: datetime) -> OutsideLight:
    """The light outside at `moment`, its global horizontal irradiance
    `ghi_w_m2` under `sun`, split into the beam and the diffuse sky's by
    Erbs's correlation; nothing while the sun is down."""
    cos_zenith = math.sin(math.radians(sun.elevation_deg))
    if ghi_w_m2 <= 0 or cos_zenith <= 0:
        return DARK
    above = extraterrestrial_w_m2(moment)
    beam = ghi_w_m2 * (1.0 - diffuse_share(ghi_w_m2 / (above * cos_zenith)))
    dni = min(beam / cos_zenith, above)
    return OutsideLight(
        ghi_w_m2=ghi_w_m2,
        dni_w_m2=dni,
        dhi_w_m2=max(ghi_w_m2 - dni * cos_zenith, 0.0),
        par_umol_m2_s=par_umol_m2_s(ghi_w_m2),
    )
