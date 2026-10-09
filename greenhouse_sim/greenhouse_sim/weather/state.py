"""The weather outside the greenhouse at a moment (P07.1).

Its quantities are named as the protocol's outside observation types are,
without their `outside_` prefix (`greenhouse_protocol.enums`), in the units
the names state, so that the same name means the same thing in a record, a
file and a run.

The wind's direction is the one it blows from, in degrees clockwise from
north, as meteorology gives it (`greenhouse_sim.world.site`).
"""

from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat

from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Bearing, Site, bearing

type Percent = Annotated[float, Field(ge=0.0, le=100.0)]

OUTSIDE_TEMPERATURE_C: Final = 10.0
OUTSIDE_HUMIDITY_PCT: Final = 80.0
OUTSIDE_CO2_PPM: Final = 420.0
# The wind blows to the bearing opposite the one it blows from.
HALF_TURN_DEG: Final = 180.0


class OutsideConditions(BaseModel):
    """What the weather is at a moment, but for its pressure, which a
    source may leave to its site."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    air_temperature_c: float = OUTSIDE_TEMPERATURE_C
    relative_humidity_pct: Percent = OUTSIDE_HUMIDITY_PCT
    co2_ppm: PositiveFloat = OUTSIDE_CO2_PPM
    wind_speed_m_s: NonNegativeFloat = 0.0
    # None when it is not known, as in a recording without a wind vane's:
    # such a wind drives nothing that needs its direction.
    wind_direction_deg: Bearing | None = 0.0
    # The sun's and the sky's light on a level surface, its global
    # horizontal irradiance (`greenhouse_sim.solar.sky`).
    global_radiation_w_m2: NonNegativeFloat = 0.0
    cloud_cover_pct: Percent = 0.0


class WeatherState(OutsideConditions):
    """The weather at a moment: the outside air's temperature, relative
    humidity and CO2, the wind's speed and the direction it blows from, the
    barometric pressure, the global radiation and the cloud cover."""

    barometric_pressure_hpa: PositiveFloat

    def wind_m_s(self, site: Site) -> Vector3:
        """The wind's velocity at `site`, in the world's axes: along the way
        it blows to, at its speed; nothing, if its direction is not known."""
        if self.wind_direction_deg is None:
            return Vector3(x=0.0, y=0.0, z=0.0)
        towards = site.towards(bearing(self.wind_direction_deg + HALF_TURN_DEG))
        return Vector3(x=self.wind_speed_m_s * towards.x, y=self.wind_speed_m_s * towards.y, z=0.0)
