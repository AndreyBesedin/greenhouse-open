"""Open doors and vents driven by the wind and the stack effect (P07.6): the
pressure across each, the house's own pressure balancing what enters and
leaves, the flow carried across the house, and an opening alone exchanging
both ways."""

import numpy as np
import pytest

from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.house import WholeHouse
from greenhouse_sim.climate.openings import (
    OpeningSite,
    opening_flows,
    opening_sites,
    pressure_coefficient,
)
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import air_grid, climate_vents
from greenhouse_sim.services.scenarios import SceneChanges, changed
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.weather.state import WeatherState
from greenhouse_sim.world.geometry import Vector3

BOX = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(BOX)
BOTH_SIDES = {"side_vent": 1.0, "side_vent_left": 1.0}
CALM = WeatherState(
    air_temperature_c=8.0, relative_humidity_pct=90.0, barometric_pressure_hpa=1013.25
)
# The climate box faces south on its right and north on its left: its x
# axis points east.
SOUTHERLY = CALM.model_copy(update={"wind_speed_m_s": 4.0, "wind_direction_deg": 180.0})
NORTHERLY = SOUTHERLY.model_copy(update={"wind_direction_deg": 0.0})


def _sites(openings: dict[str, float]) -> dict[str, OpeningSite]:
    config = changed(BOX, SceneChanges(openings=openings))
    return opening_sites(config.envelope, config.site)


def _flows(openings: dict[str, float], inside_c: float, outside: WeatherState) -> dict[str, float]:
    sites = list(_sites(openings).values())
    return {flow.opening_id: flow.net_m3_s for flow in opening_flows(sites, inside_c, outside)}


def test_a_wall_facing_the_wind_is_pushed_and_one_in_its_lee_drawn() -> None:
    wall = _sites(BOTH_SIDES)["side_vent"]

    assert wall.facing_deg == pytest.approx(180.0)
    assert pressure_coefficient(wall, 180.0) == pytest.approx(0.7)
    assert pressure_coefficient(wall, 0.0) == pytest.approx(-0.2)
    assert pressure_coefficient(wall, 90.0) == pytest.approx(-0.5)
    assert pressure_coefficient(wall, 202.5) == pytest.approx((0.7 + 0.35) / 2)


def test_a_shallow_roof_is_drawn_whichever_way_the_wind_blows() -> None:
    roof = _sites({"roof_vent": 1.0})["roof_vent"]

    assert roof.roof
    assert all(pressure_coefficient(roof, wind) < 0 for wind in (0.0, 90.0, 180.0, 270.0))


def test_the_climate_boxs_openings_are_where_its_walls_and_roof_put_them() -> None:
    sites = _sites({**BOTH_SIDES, "roof_vent": 1.0})

    assert sites["side_vent"].facing_deg == pytest.approx(180.0)
    assert sites["side_vent_left"].facing_deg == pytest.approx(0.0)
    assert sites["side_vent"].height_m == pytest.approx(2.5)
    assert sites["roof_vent"].height_m > BOX.envelope.eave_height
    assert sites["side_vent"].extent_m == pytest.approx(0.6)


def test_still_and_isothermal_nothing_flows() -> None:
    flows = opening_flows(list(_sites({**BOTH_SIDES, "roof_vent": 1.0}).values()), 8.0, CALM)

    assert all(flow.net_m3_s == 0.0 and flow.exchange_m3_s == 0.0 for flow in flows)


def test_reversing_the_wind_reverses_which_side_takes_air_in() -> None:
    from_the_south = _flows(BOTH_SIDES, 8.0, SOUTHERLY)
    from_the_north = _flows(BOTH_SIDES, 8.0, NORTHERLY)

    assert from_the_south["side_vent"] > 0 > from_the_south["side_vent_left"]
    assert from_the_north["side_vent"] == pytest.approx(-from_the_south["side_vent"])
    assert from_the_north["side_vent_left"] == pytest.approx(-from_the_south["side_vent_left"])


def test_a_warm_house_draws_air_in_low_and_lets_it_out_high() -> None:
    flows = _flows({"side_vent": 1.0, "roof_vent": 1.0}, 16.0, CALM)

    assert flows["side_vent"] > 0 > flows["roof_vent"]


def test_as_much_air_leaves_as_enters() -> None:
    flows = _flows({**BOTH_SIDES, "roof_vent": 1.0}, 16.0, SOUTHERLY)

    assert sum(flows.values()) == pytest.approx(0.0, abs=1e-12)
    assert max(abs(net) for net in flows.values()) > 1.0


def test_an_opening_alone_passes_nothing_net_and_exchanges_both_ways() -> None:
    (alone,) = opening_flows(list(_sites({"side_vent": 1.0}).values()), 16.0, SOUTHERLY)

    assert alone.net_m3_s == 0.0
    # The wind's turbulence, beating the stack over its 0.6 m.
    aperture = _sites({"side_vent": 1.0})["side_vent"].aperture_m2
    assert alone.exchange_m3_s == pytest.approx(0.025 * aperture * 4.0)


def _run(openings: dict[str, float], weather: ConstantWeather) -> ClimateRun:
    config = changed(BOX, SceneChanges(openings=openings))
    geometry = cfd.geometry("climate_box", SceneChanges(openings=openings))
    return ClimateRun(
        base=config.airflow,
        equipment=config.layout.equipment,
        schedule=Schedule.from_start({}),
        settings=config.climate,
        grid=GRID,
        solid=geometry.solid(),
        weather=config.model_copy(update={"weather": weather}).run_weather(),
        vents=climate_vents(config, geometry),
    )


WINDY = ConstantWeather(
    air_temperature_c=8.0, relative_humidity_pct=90.0, wind_speed_m_s=4.0, wind_direction_deg=180.0
)


def test_the_flow_through_carries_the_air_across_the_house_and_conserves_it() -> None:
    run = _run(BOTH_SIDES, WINDY)
    air = run.air_at(0.0)
    openings = run.openings_for(air, run.weather.at(0.0))
    flows = run.flows_at(0.0, openings)
    entering = sum(vent.spread(openings[vent.opening_id].net_m3_s) for vent in run.vents)

    # What enters each cell from outside leaves it through its faces.
    np.testing.assert_allclose(flows.divergence(), entering, atol=1e-8)
    # In the middle of the house, the air goes from the south side to the
    # north: from y = 0 towards y = width.
    middle = run.field("f", GRID, 0.0).sample(AirQuantity.VELOCITY, Vector3(x=6.0, y=3.2, z=2.0))
    assert isinstance(middle, Vector3)
    assert middle.y > 0.05


def test_a_wind_across_the_house_cools_it_faster_through_two_vents_than_one() -> None:
    across = _run(BOTH_SIDES, WINDY)
    one = _run({"side_vent": 1.0}, WINDY)
    air = ~across.solid

    # Across, it is at the outside's 8 °C in ten minutes; through one, not.
    assert across.temperature_at(600.0)[air].mean() < one.temperature_at(600.0)[air].mean() - 0.5
    # As the whole house has it too.
    assert (
        WholeHouse(across).air_at(600.0).temperature_c
        < WholeHouse(one).air_at(600.0).temperature_c - 0.5
    )
