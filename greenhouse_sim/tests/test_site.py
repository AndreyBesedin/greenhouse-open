"""Where the world lies on the Earth (P07.1): its compass, its day, and the
standard atmosphere at its elevation."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import DEFAULT_SITE, Site, bearing

# The x axis to the north, so the y axis is to the west.
NORTHWARD = DEFAULT_SITE.model_copy(update={"x_bearing_deg": 0.0})


def _close(a: Vector3, b: Vector3) -> bool:
    return (a.x, a.y, a.z) == pytest.approx((b.x, b.y, b.z), abs=1e-12)


def test_by_default_x_points_east_and_y_north() -> None:
    assert _close(DEFAULT_SITE.towards(90.0), Vector3(x=1.0, y=0.0, z=0.0))
    assert _close(DEFAULT_SITE.towards(0.0), Vector3(x=0.0, y=1.0, z=0.0))
    assert _close(DEFAULT_SITE.towards(180.0), Vector3(x=0.0, y=-1.0, z=0.0))


def test_y_points_a_quarter_turn_anticlockwise_of_x() -> None:
    assert _close(NORTHWARD.towards(0.0), Vector3(x=1.0, y=0.0, z=0.0))
    assert _close(NORTHWARD.towards(270.0), Vector3(x=0.0, y=1.0, z=0.0))


@pytest.mark.parametrize("site", [DEFAULT_SITE, NORTHWARD])
@pytest.mark.parametrize("compass", [0.0, 45.0, 135.0, 225.0, 300.0, 359.5])
def test_a_bearing_is_found_from_the_direction_it_points_to(site: Site, compass: float) -> None:
    assert site.bearing_of(site.towards(compass)) == pytest.approx(compass)


def test_a_bearing_lies_within_a_turn() -> None:
    assert bearing(370.0) == pytest.approx(10.0)
    assert bearing(-90.0) == pytest.approx(270.0)
    # A hair below north, which the remainder would round up to 360.
    assert bearing(-1e-17) == 0.0


def test_a_day_starts_at_midnight_at_the_site() -> None:
    # Amsterdam is an hour ahead of UTC in winter, two in summer.
    assert DEFAULT_SITE.midnight(date(2026, 1, 1)) == datetime(2025, 12, 31, 23, tzinfo=UTC)
    assert DEFAULT_SITE.midnight(date(2026, 7, 1)) == datetime(2026, 6, 30, 22, tzinfo=UTC)


def test_an_unknown_time_zone_is_refused() -> None:
    with pytest.raises(ValidationError, match="no time zone is called"):
        Site(latitude_deg=52.0, longitude_deg=4.5, time_zone="Europe/Atlantis")


def test_the_standard_atmosphere_thins_with_height() -> None:
    assert DEFAULT_SITE.standard_pressure_hpa() == pytest.approx(1013.25)
    # The International Standard Atmosphere's table, at 1000 m.
    high = DEFAULT_SITE.model_copy(update={"elevation_m": 1000.0})
    assert high.standard_pressure_hpa() == pytest.approx(898.76, abs=0.05)


@pytest.mark.parametrize("scenario_id", SCENARIO_REGISTRY)
def test_every_scenario_lies_near_the_recorded_greenhouse_and_starts_at_its_midnight(
    scenario_id: str,
) -> None:
    config = SCENARIO_REGISTRY[scenario_id]

    assert config.site == DEFAULT_SITE
    assert config.run_start() == DEFAULT_SITE.midnight(config.start_date)
