"""The sun's and the sky's light outside the greenhouse (P08.3).

- **Global horizontal irradiance (GHI):** the sun's and the sky's light
  together on a level surface, in W/m², as the weather's
  `global_radiation_w_m2` gives it. A clear sky's, for a weather that has
  none of its own, is Haurwitz's: GHI = 1098 cos Z e^(−0.057 / cos Z), Z the
  sun's zenith angle; nothing while the sun is down.
- **Above the atmosphere** the sun gives 1361 W/m² (the solar constant)
  square to its beam, 3.3% more at the earth's perihelion in early January
  and as much less at its aphelion in early July.
- **Beam and diffuse:** the beam, as direct normal irradiance (DNI), along
  the sun's direction, and the diffuse sky's light on a level surface
  (DHI), so that GHI = DNI cos Z + DHI. Until the sky's diffuse light is
  modelled (P08.7) the light is all beam, as far as the beam can carry it:
  never more than the sun gives above the atmosphere, the rest diffuse.
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
    `ghi_w_m2` under `sun`: as much of it beam as the beam can carry, the
    rest diffuse; nothing while the sun is down."""
    cos_zenith = math.sin(math.radians(sun.elevation_deg))
    if ghi_w_m2 <= 0 or cos_zenith <= 0:
        return DARK
    dni = min(ghi_w_m2 / cos_zenith, extraterrestrial_w_m2(moment))
    return OutsideLight(
        ghi_w_m2=ghi_w_m2,
        dni_w_m2=dni,
        dhi_w_m2=max(ghi_w_m2 - dni * cos_zenith, 0.0),
        par_umol_m2_s=par_umol_m2_s(ghi_w_m2),
    )
