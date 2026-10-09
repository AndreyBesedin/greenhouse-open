"""The sun's position over a site at a moment (P08.1).

By NOAA's solar equations, after Jean Meeus's *Astronomical Algorithms*: the
moment's Julian century, the sun's geometric mean longitude and anomaly,
the earth's orbital eccentricity, the sun's equation of centre, apparent
longitude and declination, the obliquity of the ecliptic, the equation of
time, and from them the hour angle at the site's longitude and the sun's
zenith angle and azimuth at its latitude. Its elevation includes the
atmosphere's refraction, by NOAA's approximation. Accurate to about 0.01°
between 1800 and 2100.

The azimuth is the compass bearing the sun stands at, clockwise from north,
as every bearing is (decision 0028); the direction towards the sun in the
world's axes follows through the site's compass.
"""

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import Site, bearing

# The Julian day of the Unix epoch, and of the J2000.0 epoch; days in a
# Julian century; seconds in a day; minutes in a day, and per degree of
# longitude.
UNIX_EPOCH_JULIAN_DAY: Final = 2440587.5
J2000_JULIAN_DAY: Final = 2451545.0
DAYS_PER_JULIAN_CENTURY: Final = 36525.0
SECONDS_PER_DAY: Final = 86_400.0
MINUTES_PER_DAY: Final = 1440.0
MINUTES_PER_DEGREE: Final = 4.0
HALF_TURN_DEG: Final = 180.0
QUARTER_TURN_DEG: Final = 90.0
DEGREES_IN_A_TURN: Final = 360.0
# Polynomials in the Julian century, lowest power first.
MEAN_LONGITUDE: Final = (280.46646, 36000.76983, 0.0003032)
MEAN_ANOMALY: Final = (357.52911, 35999.05029, -0.0001537)
ECCENTRICITY: Final = (0.016708634, -0.000042037, -0.0000001267)
CENTRE_FIRST: Final = (1.914602, -0.004817, -0.000014)
CENTRE_SECOND: Final = (0.019993, -0.000101)
CENTRE_THIRD: Final = 0.000289
# The harmonics of the mean anomaly and longitude the equations take.
THIRD_HARMONIC: Final = 3
FOURTH_HARMONIC: Final = 4
# The nutation and aberration's correction to the longitude, and the moon's
# ascending node's longitude it turns with.
ABERRATION_DEG: Final = 0.00569
NUTATION_DEG: Final = 0.00478
NODE: Final = (125.04, -1934.136)
OBLIQUITY_NUTATION_DEG: Final = 0.00256
# The mean obliquity of the ecliptic: 23° 26′ and so many seconds.
OBLIQUITY_DEGREES: Final = 23.0
OBLIQUITY_MINUTES: Final = 26.0
OBLIQUITY_SECONDS: Final = (21.448, -46.815, -0.00059, 0.001813)
ARC_MINUTES_PER_DEGREE: Final = 60.0
# The equation of time's terms.
TIME_ECCENTRIC: Final = 4.0
TIME_HALF: Final = 0.5
TIME_ECCENTRIC_SQUARED: Final = 1.25
# NOAA's refraction approximation: none near the zenith; by the tangent of
# the elevation above 5°; by a polynomial near the horizon; and below it.
NO_REFRACTION_ABOVE_DEG: Final = 85.0
TANGENT_REFRACTION_ABOVE_DEG: Final = 5.0
HORIZON_REFRACTION_ABOVE_DEG: Final = -0.575
TANGENT_ARC_SECONDS: Final = (58.1, -0.07, 0.000086)
HORIZON_ARC_SECONDS: Final = (1735.0, -518.2, 103.4, -12.79, 0.711)
BELOW_HORIZON_ARC_SECONDS: Final = -20.772
ARC_SECONDS_PER_DEGREE: Final = 3600.0


def _polynomial(coefficients: Sequence[float], x: float) -> float:
    """Σ cᵢ xⁱ, the lowest power first."""
    total = 0.0
    for coefficient in reversed(coefficients):
        total = total * x + coefficient
    return total


def _refraction_deg(elevation_deg: float) -> float:
    """How far the atmosphere lifts the sun's image, in degrees."""
    if elevation_deg > NO_REFRACTION_ABOVE_DEG:
        return 0.0
    tangent = math.tan(math.radians(elevation_deg))
    if elevation_deg > TANGENT_REFRACTION_ABOVE_DEG:
        first, third, fifth = TANGENT_ARC_SECONDS
        seconds = first / tangent + third / tangent**3 + fifth / tangent**5
    elif elevation_deg > HORIZON_REFRACTION_ABOVE_DEG:
        seconds = _polynomial(HORIZON_ARC_SECONDS, elevation_deg)
    else:
        seconds = BELOW_HORIZON_ARC_SECONDS / tangent
    return seconds / ARC_SECONDS_PER_DEGREE


class SunPosition(BaseModel):
    """Where the sun stands at a moment, seen from a site: its elevation
    above the horizon (refraction included) and its azimuth, clockwise from
    north, both in degrees; with its declination and the equation of time,
    in minutes, for those who check them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    elevation_deg: float
    azimuth_deg: float
    declination_deg: float
    equation_of_time_min: float

    def is_up(self) -> bool:
        """Whether it stands above the horizon."""
        return self.elevation_deg > 0

    def direction(self, site: Site) -> Vector3:
        """The unit vector towards the sun, in the world's axes."""
        level = site.towards(self.azimuth_deg)
        elevation = math.radians(self.elevation_deg)
        across = math.cos(elevation)
        return Vector3(x=level.x * across, y=level.y * across, z=math.sin(elevation))


def sun_position(moment: datetime, site: Site) -> SunPosition:
    """Where the sun stands at `moment`, an aware instant, seen from
    `site`."""
    if moment.utcoffset() is None:
        raise ValueError(f"a moment has a time zone: {moment.isoformat()}")
    seconds = moment.astimezone(UTC).timestamp()
    julian_day = UNIX_EPOCH_JULIAN_DAY + seconds / SECONDS_PER_DAY
    century = (julian_day - J2000_JULIAN_DAY) / DAYS_PER_JULIAN_CENTURY

    mean_longitude = _polynomial(MEAN_LONGITUDE, century) % DEGREES_IN_A_TURN
    anomaly = math.radians(_polynomial(MEAN_ANOMALY, century))
    eccentricity = _polynomial(ECCENTRICITY, century)
    centre = (
        math.sin(anomaly) * _polynomial(CENTRE_FIRST, century)
        + math.sin(2 * anomaly) * _polynomial(CENTRE_SECOND, century)
        + math.sin(THIRD_HARMONIC * anomaly) * CENTRE_THIRD
    )
    node = math.radians(_polynomial(NODE, century))
    apparent_longitude = math.radians(
        mean_longitude + centre - ABERRATION_DEG - NUTATION_DEG * math.sin(node)
    )
    mean_obliquity = (
        OBLIQUITY_DEGREES
        + (OBLIQUITY_MINUTES + _polynomial(OBLIQUITY_SECONDS, century) / ARC_MINUTES_PER_DEGREE)
        / ARC_MINUTES_PER_DEGREE
    )
    obliquity = math.radians(mean_obliquity + OBLIQUITY_NUTATION_DEG * math.cos(node))
    declination = math.asin(math.sin(obliquity) * math.sin(apparent_longitude))

    y = math.tan(obliquity / 2) ** 2
    longitude_rad = math.radians(mean_longitude)
    equation_of_time = MINUTES_PER_DEGREE * math.degrees(
        y * math.sin(2 * longitude_rad)
        - 2 * eccentricity * math.sin(anomaly)
        + TIME_ECCENTRIC * eccentricity * y * math.sin(anomaly) * math.cos(2 * longitude_rad)
        - TIME_HALF * y**2 * math.sin(FOURTH_HARMONIC * longitude_rad)
        - TIME_ECCENTRIC_SQUARED * eccentricity**2 * math.sin(2 * anomaly)
    )

    minutes = (seconds % SECONDS_PER_DAY) / (SECONDS_PER_DAY / MINUTES_PER_DAY)
    true_solar = (
        minutes + equation_of_time + MINUTES_PER_DEGREE * site.longitude_deg
    ) % MINUTES_PER_DAY
    hour_angle = math.radians(true_solar / MINUTES_PER_DEGREE - HALF_TURN_DEG)

    latitude = math.radians(site.latitude_deg)
    cos_zenith = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(
        declination
    ) * math.cos(hour_angle)
    zenith = math.acos(max(-1.0, min(1.0, cos_zenith)))
    elevation = QUARTER_TURN_DEG - math.degrees(zenith)

    sin_zenith = math.sin(zenith)
    if sin_zenith == 0 or math.cos(latitude) == 0:
        azimuth = 0.0
    else:
        cos_azimuth = (math.sin(latitude) * math.cos(zenith) - math.sin(declination)) / (
            math.cos(latitude) * sin_zenith
        )
        from_south = math.degrees(math.acos(max(-1.0, min(1.0, cos_azimuth))))
        # Past noon in the west, before it in the east.
        azimuth = (
            from_south + HALF_TURN_DEG
            if hour_angle > 0
            else DEGREES_IN_A_TURN + HALF_TURN_DEG - from_south
        )
    return SunPosition(
        elevation_deg=elevation + _refraction_deg(elevation),
        azimuth_deg=bearing(azimuth),
        declination_deg=math.degrees(declination),
        equation_of_time_min=equation_of_time,
    )
