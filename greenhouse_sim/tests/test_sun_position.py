"""The sun's position (P08.1): NOAA's equations against NREL's published
example and the seasons' known values, and its direction in the world's
axes."""

import json
from datetime import UTC, datetime, timedelta, timezone
from http import HTTPStatus

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.solar.position import sun_position
from greenhouse_sim.world.site import DEFAULT_SITE, Site

# NREL's Solar Position Algorithm (Reda and Andreas, 2004), its example:
# 17 October 2003, 12:30:30 local time, 7 h behind UTC, in Golden,
# Colorado; the sun's zenith angle 50.11162° and azimuth 194.34024°.
GOLDEN = Site(
    latitude_deg=39.742476,
    longitude_deg=-105.1786,
    elevation_m=1830.14,
    time_zone="America/Denver",
)
SPA_MOMENT = datetime(2003, 10, 17, 12, 30, 30, tzinfo=timezone(timedelta(hours=-7)))
SPA_ZENITH_DEG = 50.11162
SPA_AZIMUTH_DEG = 194.34024
TOLERANCE_DEG = 0.05
OBLIQUITY_DEG = 23.44


def _noon(day: datetime) -> float:
    """The sun's highest elevation over the default site on a day, minute by
    minute around noon."""
    return max(
        sun_position(day + timedelta(minutes=minute), DEFAULT_SITE).elevation_deg
        for minute in range(10 * 60, 14 * 60)
    )


def test_it_matches_nrels_published_example() -> None:
    position = sun_position(SPA_MOMENT, GOLDEN)

    assert 90.0 - position.elevation_deg == pytest.approx(SPA_ZENITH_DEG, abs=TOLERANCE_DEG)
    assert position.azimuth_deg == pytest.approx(SPA_AZIMUTH_DEG, abs=TOLERANCE_DEG)


def test_at_an_equinox_the_noon_sun_stands_the_colatitude_high() -> None:
    noon = _noon(datetime(2026, 3, 20, tzinfo=UTC))

    assert noon == pytest.approx(90.0 - DEFAULT_SITE.latitude_deg, abs=0.3)


def test_at_the_solstices_the_sun_turns_at_the_obliquity() -> None:
    summer = sun_position(datetime(2026, 6, 21, 12, tzinfo=UTC), DEFAULT_SITE)
    winter = sun_position(datetime(2026, 12, 21, 12, tzinfo=UTC), DEFAULT_SITE)

    assert summer.declination_deg == pytest.approx(OBLIQUITY_DEG, abs=0.01)
    assert winter.declination_deg == pytest.approx(-OBLIQUITY_DEG, abs=0.01)
    assert _noon(datetime(2026, 6, 21, tzinfo=UTC)) > _noon(datetime(2026, 12, 21, tzinfo=UTC))


def test_the_sun_rises_in_the_east_stands_south_at_noon_and_sets_in_the_west() -> None:
    morning = sun_position(datetime(2026, 3, 20, 7, tzinfo=UTC), DEFAULT_SITE)
    # Solar noon at 4.5° east, the equation of time 7.5 minutes slow: 11:50.
    noon = sun_position(datetime(2026, 3, 20, 11, 50, tzinfo=UTC), DEFAULT_SITE)
    evening = sun_position(datetime(2026, 3, 20, 16, tzinfo=UTC), DEFAULT_SITE)
    night = sun_position(datetime(2026, 3, 20, 23, tzinfo=UTC), DEFAULT_SITE)

    assert 90.0 < morning.azimuth_deg < 135.0
    assert noon.azimuth_deg == pytest.approx(180.0, abs=2.0)
    assert 225.0 < evening.azimuth_deg < 270.0
    assert not night.is_up()


def test_the_equation_of_time_follows_the_year() -> None:
    # The sun runs about 14 minutes slow in mid-February, and 16 fast in
    # early November.
    february = sun_position(datetime(2026, 2, 12, 12, tzinfo=UTC), DEFAULT_SITE)
    november = sun_position(datetime(2026, 11, 3, 12, tzinfo=UTC), DEFAULT_SITE)

    assert february.equation_of_time_min == pytest.approx(-14.2, abs=0.3)
    assert november.equation_of_time_min == pytest.approx(16.4, abs=0.3)


def test_its_direction_points_along_its_azimuth_and_up_by_its_elevation() -> None:
    position = sun_position(datetime(2026, 3, 20, 11, 50, tzinfo=UTC), DEFAULT_SITE)
    direction = position.direction(DEFAULT_SITE)

    # By default x points east and y north: at noon the sun is to the south.
    assert direction.y < -0.7
    assert abs(direction.x) < 0.05
    assert direction.z == pytest.approx(0.6157, abs=0.01)
    assert direction.x**2 + direction.y**2 + direction.z**2 == pytest.approx(1.0)
    turned = DEFAULT_SITE.model_copy(update={"x_bearing_deg": 180.0})
    assert position.direction(turned).x > 0.7


def test_a_moment_without_a_time_zone_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        sun_position(datetime(2026, 3, 20, 12), DEFAULT_SITE)


def test_the_api_serves_the_sun_with_the_weather() -> None:
    # 12:45 in Amsterdam on 1 January, 11:45 UTC: about solar noon.
    noon = respond("GET", "/api/scenarios/climate_box/weather?t=45900")
    midnight = respond("GET", "/api/scenarios/climate_box/weather")
    body = json.loads(json.dumps(noon.body))

    assert noon.status == HTTPStatus.OK
    # The climate box's runs start on 1 January: a low winter sun at noon.
    assert body["sun"]["elevation_deg"] == pytest.approx(15.1, abs=0.1)
    assert body["sun"]["azimuth_deg"] == pytest.approx(180.0, abs=2.0)
    assert body["sun_direction"]["z"] > 0
    assert json.loads(json.dumps(midnight.body))["sun"]["elevation_deg"] < 0


def test_the_api_serves_the_suns_path_through_the_day() -> None:
    body = json.loads(json.dumps(respond("GET", "/api/scenarios/climate_box/weather/day").body))
    up = [
        (time, sun)
        for time, sun in zip(body["times_s"], body["sun"], strict=True)
        if sun["elevation_deg"] > 0
    ]

    assert len(body["sun_directions"]) == len(body["times_s"]) == 145
    # A short January day: up from about half past eight to half past four.
    assert 8 * 3600 < up[0][0] < 9.5 * 3600
    assert 16 * 3600 < up[-1][0] < 17.5 * 3600
    assert up[0][1]["azimuth_deg"] < 180.0 < up[-1][1]["azimuth_deg"]
