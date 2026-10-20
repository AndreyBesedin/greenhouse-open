"""Weather through a season (P10.3): each day's coldest and warmest
temperatures follow the year, and wander from them from day to day, as a
spell of weather does; each day its own clouds. A run under it from March
into summer sees cold nights give way to warm ones, a mild week in a cold
month, a dull day after a bright one.

- **The year:** a day's usual coldest and warmest temperatures go from their
  values on the year's coldest day (`coldest_day`) to those half a year
  later along a half cosine, and back: `coldest_c` and `warmest_c` give each
  pair, winter's first.
- **Spells:** each day's temperatures are its usual ones shifted by the
  same amount, drawn from the scenario's seed and the date: an
  autoregressive series whose next day keeps `persistence` of the day
  before's shift, with a standard deviation of `day_to_day_c`. It is worked
  out from the days before it, so a date has the same weather whenever a
  run asks for it, and whenever a run starts.
- **Clouds:** each day's cover is `cloud_cover_pct`, more or less by up to
  `cloud_spread_pct`, drawn from the seed and the date, and dims the sun's
  light as it does on a synthetic day.
- **A day's shape** is a synthetic day's (`greenhouse_sim.weather.synthetic`):
  coldest at `coldest_hour`, warmest at `warmest_hour`, along a half cosine
  each way, the air holding as much water as gives `humidity_at_coldest_pct`
  at the coldest; and its wind, gusts and veer the same. Through the evening
  and the night the air cools from the day's warmest to the next day's
  coldest, and its water goes from one day's to the next's, so that nothing
  jumps at midnight.

Its temperatures are the outside air's, not a record of any one year: a
plausible season at the site, the same for the same seed.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import cached_property, lru_cache
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
from greenhouse_sim.weather.sources import WeatherSource
from greenhouse_sim.weather.state import OUTSIDE_CO2_PPM, Percent, WeatherState
from greenhouse_sim.weather.synthetic import (
    HOURS_IN_A_DAY,
    SECONDS_PER_HOUR,
    Hour,
    SyntheticWeather,
)
from greenhouse_sim.world.site import Bearing, Site

DAYS_IN_A_YEAR: Final = 365.25
# How many days before a date its spell is worked out from: the shift a day
# keeps from so long before is too small to matter at any persistence below
# 0.8 (0.8 ** 40 is about 1e-4).
SPELL_MEMORY_DAYS: Final = 40
# How many dates' shifts and clouds are kept, so that a run asking for
# nearby moments draws each once.
_KEPT_DAYS: Final = 1024

type Persistence = Annotated[float, Field(ge=0.0, lt=0.8)]
# A pair of temperatures, winter's and summer's.
type Seasons = tuple[float, float]


@lru_cache(maxsize=_KEPT_DAYS)
def _draw(seed: int, day: date) -> float:
    """The day's own share of its spell, of unit standard deviation."""
    return float(seeded_rng(seed, "weather", "spell", day.toordinal()).normal())


@lru_cache(maxsize=_KEPT_DAYS)
def _cloud_draw(seed: int, day: date) -> float:
    """Where the day's clouds fall in their range, from -1 to 1."""
    return float(seeded_rng(seed, "weather", "clouds", day.toordinal()).uniform(-1.0, 1.0))


class SeasonalWeather(BaseModel):
    """Weather through a season: each day's usual coldest and warmest
    temperatures on the year's coldest day and half a year later, which day
    of the year is coldest, how far a day's temperatures wander from their
    usual ones and how much of that a day keeps from the day before, and
    each day's clouds; and a synthetic day's shape, humidity and wind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["seasonal"] = "seasonal"
    coldest_c: Seasons
    warmest_c: Seasons
    # The year's coldest day, as its day of the year (1 for 1 January).
    coldest_day: Annotated[int, Field(ge=1, le=366)] = 20
    day_to_day_c: NonNegativeFloat = 0.0
    persistence: Persistence = 0.0
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
    cloud_spread_pct: Percent = 0.0
    barometric_pressure_hpa: PositiveFloat | None = None

    @model_validator(mode="after")
    def _days_that_warm_and_cool(self) -> Self:
        if not self.coldest_hour < self.warmest_hour:
            raise ValueError("the coldest hour comes before the warmest, in a day")
        if any(warm < cold for cold, warm in zip(self.coldest_c, self.warmest_c, strict=True)):
            raise ValueError("a season's warmest temperature is no colder than its coldest")
        if self.windiest_m_s < self.calmest_m_s:
            raise ValueError("the windiest wind is no calmer than the calmest")
        return self

    @cached_property
    def day_shape(self) -> SyntheticWeather:
        """A day of this weather's shape: its hours, humidity and wind; its
        temperatures are each day's own."""
        return SyntheticWeather(
            coldest_c=self.coldest_c[0],
            warmest_c=self.warmest_c[0],
            coldest_hour=self.coldest_hour,
            warmest_hour=self.warmest_hour,
            humidity_at_coldest_pct=self.humidity_at_coldest_pct,
            co2_ppm=self.co2_ppm,
            calmest_m_s=self.calmest_m_s,
            windiest_m_s=self.windiest_m_s,
            wind_from_deg=self.wind_from_deg,
            veer_deg=self.veer_deg,
            gustiness=self.gustiness,
            cloud_cover_pct=self.cloud_cover_pct,
            barometric_pressure_hpa=self.barometric_pressure_hpa,
        )

    def summery(self, day: date) -> float:
        """How far `day` is from the year's coldest day to its warmest: 0 on
        the coldest, 1 half a year later, along a half cosine each way."""
        since = day.timetuple().tm_yday - self.coldest_day
        return (1.0 - math.cos(2 * math.pi * since / DAYS_IN_A_YEAR)) / 2

    def spell_c(self, seed: int, day: date) -> float:
        """How far `day`'s temperatures are from their usual ones, by its
        spell of weather, drawn from `seed`."""
        keep = self.persistence
        own = self.day_to_day_c * math.sqrt(1.0 - keep**2)
        return own * sum(
            keep**back * _draw(seed, day - timedelta(days=back))
            for back in range(SPELL_MEMORY_DAYS)
        )

    def temperatures_c(self, seed: int, day: date) -> tuple[float, float]:
        """`day`'s coldest and warmest temperatures, drawn from `seed`."""
        return _temperatures_c(self, seed, day)

    def clouds_pct(self, seed: int, day: date) -> float:
        """`day`'s cloud cover, drawn from `seed`."""
        drawn = self.cloud_cover_pct + self.cloud_spread_pct * _cloud_draw(seed, day)
        return min(max(drawn, 0.0), 100.0)

    def source(self, site: Site, seed: int, start: datetime | None = None) -> WeatherSource:
        """This weather at `site`, drawn from `seed`, the same on each date
        whenever a run starts."""
        return _Seasonal(self, site, seed)


@dataclass(frozen=True)
class _Seasonal:
    weather: SeasonalWeather
    site: Site
    seed: int

    def _day(self, day: date) -> WeatherSource:
        """A synthetic day of this weather's shape under `day`'s clouds: its
        wind, gusts and light."""
        return _clouded_day(self.weather, self.site, self.seed, day)

    def _water_g_kg(self, day: date) -> float:
        coldest, _ = self.weather.temperatures_c(self.seed, day)
        return float(humidity_ratio_g_kg(coldest, self.weather.humidity_at_coldest_pct))

    def at(self, moment: datetime) -> WeatherState:
        if moment.utcoffset() is None:
            raise ValueError(f"a moment has a time zone: {moment.isoformat()}")
        weather = self.weather
        wall = moment.astimezone(self.site.zone()).replace(tzinfo=None)
        today = wall.date()
        hour = (wall - datetime.combine(today, time())).total_seconds() / SECONDS_PER_HOUR
        warmth = weather.day_shape.warmth(hour)
        # The stretch the moment falls in, from one coldest hour to the next:
        # warming through today's morning, or cooling from a day's warmest to
        # the next day's coldest.
        if hour < weather.coldest_hour:
            cold_day, warm_day = today, today - timedelta(days=1)
            since_coldest = hour + HOURS_IN_A_DAY - weather.coldest_hour
        elif hour <= weather.warmest_hour:
            cold_day, warm_day = today, today
            since_coldest = hour - weather.coldest_hour
        else:
            cold_day, warm_day = today + timedelta(days=1), today
            since_coldest = hour - weather.coldest_hour
        coldest, _ = weather.temperatures_c(self.seed, cold_day)
        _, warmest = weather.temperatures_c(self.seed, warm_day)
        temperature = coldest + (warmest - coldest) * warmth
        # The air's water goes from one coldest hour's to the next's.
        first = today if hour >= weather.coldest_hour else today - timedelta(days=1)
        share = since_coldest / HOURS_IN_A_DAY
        water = (1.0 - share) * self._water_g_kg(first) + share * self._water_g_kg(
            first + timedelta(days=1)
        )
        state = self._day(today).at(moment)
        return state.model_copy(
            update={
                "air_temperature_c": temperature,
                "relative_humidity_pct": min(
                    float(relative_humidity_pct(temperature, water)), 100.0
                ),
            }
        )


@lru_cache(maxsize=_KEPT_DAYS)
def _temperatures_c(weather: SeasonalWeather, seed: int, day: date) -> tuple[float, float]:
    summery = weather.summery(day)
    spell = weather.spell_c(seed, day)

    def usual(pair: Seasons) -> float:
        return pair[0] + (pair[1] - pair[0]) * summery

    return usual(weather.coldest_c) + spell, usual(weather.warmest_c) + spell


@lru_cache(maxsize=_KEPT_DAYS)
def _clouded_day(weather: SeasonalWeather, site: Site, seed: int, day: date) -> WeatherSource:
    clouds = weather.clouds_pct(seed, day)
    return weather.day_shape.model_copy(update={"cloud_cover_pct": clouds}).source(site, seed)
