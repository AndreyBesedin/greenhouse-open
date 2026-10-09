"""A day of weather from a handful of numbers, the same every day and every
time (P07.2).

The day follows the site's clock (`greenhouse_sim.world.site`):

- **temperature:** coldest at `coldest_hour`, near dawn, and warmest at
  `warmest_hour`, mid-afternoon, along a half cosine from one to the other,
  rising through the morning and falling through the evening and night;
- **humidity:** the air holds the same water all day, as much as gives
  `humidity_at_coldest_pct` at the coldest, so that its relative humidity
  falls as it warms and rises as it cools, as it mostly does outdoors;
- **wind:** calmest when it is coldest and windiest when it is warmest,
  along the same curve, its direction veering steadily through the day from
  the one it has at midnight; gusts and lulls change its speed by a share
  drawn afresh every `GUST_EVERY_S`, and in between linearly, seeded by the
  scenario's seed and the moment, so that the same seed always gives the
  same gusts;
- **radiation:** a clear sky's under the sun where it stands at the site,
  dimmed by the day's clouds (`greenhouse_sim.solar.sky`), nothing while
  the sun is down;
- **the rest:** CO2, cloud cover and pressure (the standard atmosphere's at
  the site's elevation, unless given) hold all day.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    model_validator,
)

from greenhouse_sim.climate.psychrometrics import humidity_ratio_g_kg, relative_humidity_pct
from greenhouse_sim.core.rng import seeded_rng
from greenhouse_sim.solar.position import sun_position
from greenhouse_sim.solar.sky import clear_sky_ghi_w_m2, cloud_factor
from greenhouse_sim.weather.sources import WeatherSource
from greenhouse_sim.weather.state import OUTSIDE_CO2_PPM, Percent, WeatherState
from greenhouse_sim.world.site import Bearing, Site, bearing

HOURS_IN_A_DAY: Final = 24.0
SECONDS_PER_HOUR: Final = 3600.0
# Gusts and lulls are drawn afresh this often, in seconds.
GUST_EVERY_S: Final = 60.0
# How many gusts' draws are kept, so that a run asking for nearby moments
# draws each once.
_KEPT_GUSTS: Final = 4096

type Hour = Annotated[float, Field(ge=0.0, lt=HOURS_IN_A_DAY)]


@lru_cache(maxsize=_KEPT_GUSTS)
def _gust(seed: int, index: int) -> float:
    """The `index`th gust's share of the wind, of unit standard deviation."""
    return float(seeded_rng(seed, "weather", "gust", index).normal())


class SyntheticWeather(BaseModel):
    """A day of weather, each day alike: its coldest and warmest temperatures
    and their hours, its humidity at the coldest, its CO2, its calmest and
    windiest winds, the direction the wind blows from at midnight and how
    far it veers clockwise by the next (backing if negative), its gusts' size
    as a share of the wind's speed, its cloud cover and its pressure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["synthetic"] = "synthetic"
    coldest_c: float
    warmest_c: float
    coldest_hour: Hour
    warmest_hour: Hour
    humidity_at_coldest_pct: Percent
    co2_ppm: PositiveFloat = OUTSIDE_CO2_PPM
    calmest_m_s: NonNegativeFloat
    windiest_m_s: NonNegativeFloat
    wind_from_deg: Bearing
    veer_deg: float = 0.0
    gustiness: NonNegativeFloat = 0.0
    cloud_cover_pct: Percent = 0.0
    barometric_pressure_hpa: PositiveFloat | None = None

    @model_validator(mode="after")
    def _a_day_that_warms_and_cools(self) -> Self:
        if not self.coldest_hour < self.warmest_hour:
            raise ValueError("the coldest hour comes before the warmest, in a day")
        if self.warmest_c < self.coldest_c:
            raise ValueError("the warmest temperature is no colder than the coldest")
        if self.windiest_m_s < self.calmest_m_s:
            raise ValueError("the windiest wind is no calmer than the calmest")
        return self

    def warmth(self, hour: float) -> float:
        """How far the day is from its coldest to its warmest at `hour`, local
        time: 0 at the coldest, 1 at the warmest, along a half cosine each
        way."""
        coldest, warmest = self.coldest_hour, self.warmest_hour
        if coldest <= hour <= warmest:
            return (1.0 - math.cos(math.pi * (hour - coldest) / (warmest - coldest))) / 2
        since = (hour - warmest) % HOURS_IN_A_DAY
        falling = HOURS_IN_A_DAY - (warmest - coldest)
        return (1.0 + math.cos(math.pi * since / falling)) / 2

    def source(self, site: Site, seed: int, start: datetime | None = None) -> WeatherSource:
        """This day's weather at `site`, its gusts drawn from `seed`, each
        day alike whenever a run starts."""
        pressure = self.barometric_pressure_hpa
        return _Synthetic(
            self,
            site,
            seed,
            site.standard_pressure_hpa() if pressure is None else pressure,
            float(humidity_ratio_g_kg(self.coldest_c, self.humidity_at_coldest_pct)),
        )


@dataclass(frozen=True)
class _Synthetic:
    weather: SyntheticWeather
    site: Site
    seed: int
    pressure_hpa: float
    water_g_kg: float

    def _gusting(self, moment: datetime) -> float:
        """The share gusts and lulls add to the wind at `moment`, between the
        draws either side of it."""
        steps = moment.astimezone(UTC).timestamp() / GUST_EVERY_S
        index = math.floor(steps)
        share = steps - index
        between = (1.0 - share) * _gust(self.seed, index) + share * _gust(self.seed, index + 1)
        return self.weather.gustiness * between

    def at(self, moment: datetime) -> WeatherState:
        if moment.utcoffset() is None:
            raise ValueError(f"a moment has a time zone: {moment.isoformat()}")
        weather = self.weather
        # The hour on the site's clock, whatever the day's length.
        wall = moment.astimezone(self.site.zone()).replace(tzinfo=None)
        midnight = wall.replace(hour=0, minute=0, second=0, microsecond=0)
        hour = (wall - midnight).total_seconds() / SECONDS_PER_HOUR
        warmth = weather.warmth(hour)
        temperature = weather.coldest_c + (weather.warmest_c - weather.coldest_c) * warmth
        wind = weather.calmest_m_s + (weather.windiest_m_s - weather.calmest_m_s) * warmth
        return WeatherState(
            air_temperature_c=temperature,
            relative_humidity_pct=min(
                float(relative_humidity_pct(temperature, self.water_g_kg)), 100.0
            ),
            co2_ppm=weather.co2_ppm,
            wind_speed_m_s=max(wind * (1.0 + self._gusting(moment)), 0.0),
            wind_direction_deg=bearing(
                weather.wind_from_deg + weather.veer_deg * hour / HOURS_IN_A_DAY
            ),
            barometric_pressure_hpa=self.pressure_hpa,
            global_radiation_w_m2=clear_sky_ghi_w_m2(sun_position(moment, self.site))
            * cloud_factor(weather.cloud_cover_pct),
            cloud_cover_pct=weather.cloud_cover_pct,
        )
