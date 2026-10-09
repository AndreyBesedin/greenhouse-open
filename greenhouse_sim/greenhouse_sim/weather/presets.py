"""Synthetic days by name (P07.2), any of which a scenario can be run under in
place of its own weather."""

from typing import Final

from greenhouse_sim.weather.synthetic import SyntheticWeather

# A cold, damp spring day: a night near 4 °C, an afternoon near 16 °C, and a
# wind rising through the day as it veers from the south-west to the
# north-west; half the sky clouded.
COLD_SPRING_DAY: Final = SyntheticWeather(
    coldest_c=4.0,
    warmest_c=16.0,
    coldest_hour=6.0,
    warmest_hour=15.0,
    humidity_at_coldest_pct=95.0,
    calmest_m_s=1.5,
    windiest_m_s=6.0,
    wind_from_deg=225.0,
    veer_deg=90.0,
    gustiness=0.2,
    cloud_cover_pct=50.0,
)
# A hot, dry summer day: 17 °C before dawn, 31 °C in the afternoon, the air
# drying to a third of saturation, and a light easterly; a clear sky.
HOT_DRY_SUMMER_DAY: Final = SyntheticWeather(
    coldest_c=17.0,
    warmest_c=31.0,
    coldest_hour=5.0,
    warmest_hour=15.0,
    humidity_at_coldest_pct=75.0,
    calmest_m_s=1.0,
    windiest_m_s=3.0,
    wind_from_deg=90.0,
    veer_deg=30.0,
    gustiness=0.1,
    cloud_cover_pct=10.0,
)
# A windy autumn day: mild and damp under a grey sky, a strong, gusty
# south-westerly veering to the west.
WINDY_AUTUMN_DAY: Final = SyntheticWeather(
    coldest_c=9.0,
    warmest_c=13.0,
    coldest_hour=7.0,
    warmest_hour=14.0,
    humidity_at_coldest_pct=92.0,
    calmest_m_s=7.0,
    windiest_m_s=13.0,
    wind_from_deg=200.0,
    veer_deg=70.0,
    gustiness=0.3,
    cloud_cover_pct=90.0,
)

PRESETS: Final[dict[str, SyntheticWeather]] = {
    "cold_spring_day": COLD_SPRING_DAY,
    "hot_dry_summer_day": HOT_DRY_SUMMER_DAY,
    "windy_autumn_day": WINDY_AUTUMN_DAY,
}
