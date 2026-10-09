"""Where the simulated world lies on the Earth (P07.1, decision 0028).

A site gives the world a latitude, a longitude, an elevation and a time
zone, and the compass bearing its x axis points to. Weather needs the
bearing to turn a wind from the north-west into a wind across the house,
and the time zone for its day; the sun (P08) needs all of it.

Bearings are degrees clockwise from north, as a compass reads them. The
world's axes are right-handed with z up (decision 0007), so its y axis
points 90° anticlockwise of its x axis, seen from above: by default x
points east and y north. A greenhouse's own frame is turned within the
world by its envelope's origin (decision 0016).
"""

import math
from datetime import date, datetime, time
from typing import Annotated, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from greenhouse_sim.world.geometry import Vector3

DEGREES_IN_A_TURN: Final = 360.0
QUARTER_TURN_DEG: Final = 90.0
# The standard atmosphere's pressure at sea level, and how it falls with
# height below 11 km: p = p0 (1 - L h / T0) ^ (g M / R L).
SEA_LEVEL_PRESSURE_HPA: Final = 1013.25
LAPSE_PER_M: Final = 2.25577e-5
PRESSURE_EXPONENT: Final = 5.25588

type Bearing = Annotated[float, Field(ge=0.0, lt=DEGREES_IN_A_TURN)]


def bearing(degrees: float) -> float:
    """A bearing in degrees, brought within 0 to 360: a hair below north,
    which the remainder rounds up to 360, is north."""
    within = degrees % DEGREES_IN_A_TURN
    return 0.0 if within >= DEGREES_IN_A_TURN else within


class Site(BaseModel):
    """Where the world lies: its latitude and longitude (degrees north and
    east), its elevation (metres above sea level), its time zone (by its
    IANA name, such as `Europe/Amsterdam`), and the bearing of its x axis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude_deg: Annotated[float, Field(ge=-QUARTER_TURN_DEG, le=QUARTER_TURN_DEG)]
    longitude_deg: Annotated[float, Field(ge=-DEGREES_IN_A_TURN / 2, le=DEGREES_IN_A_TURN / 2)]
    elevation_m: float = 0.0
    time_zone: str
    # East, by default: x east, y north and z up.
    x_bearing_deg: Bearing = QUARTER_TURN_DEG

    @field_validator("time_zone")
    @classmethod
    def _a_known_time_zone(cls, name: str) -> str:
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as unknown:
            raise ValueError(f"no time zone is called {name!r}") from unknown
        return name

    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.time_zone)

    def midnight(self, day: date) -> datetime:
        """The instant `day` starts at the site, in its time zone."""
        return datetime.combine(day, time(0), tzinfo=self.zone())

    def towards(self, bearing_deg: float) -> Vector3:
        """The horizontal unit vector, in the world's axes, that points to a
        compass bearing."""
        angle = math.radians(self.x_bearing_deg - bearing_deg)
        return Vector3(x=math.cos(angle), y=math.sin(angle), z=0.0)

    def bearing_of(self, direction: Vector3) -> float:
        """The compass bearing a direction in the world's axes points to,
        seen from above."""
        return bearing(self.x_bearing_deg - math.degrees(math.atan2(direction.y, direction.x)))

    def standard_pressure_hpa(self) -> float:
        """The standard atmosphere's pressure at the site's elevation."""
        return float(
            SEA_LEVEL_PRESSURE_HPA * (1.0 - LAPSE_PER_M * self.elevation_m) ** PRESSURE_EXPONENT
        )


# Near Bleiswijk, in the Netherlands, where the recorded WUR greenhouse data
# (`greenhouse_adapters`) were taken, at sea level, its x axis east.
DEFAULT_SITE: Final = Site(latitude_deg=52.0, longitude_deg=4.5, time_zone="Europe/Amsterdam")
