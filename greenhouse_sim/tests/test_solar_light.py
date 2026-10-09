"""The sun's and the sky's light (P08.3): the clear sky's, the beam and the
diffuse, PAR from them, outside and inside, through the glass (P08.4), and
the climate field's light."""

import json
import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.transport import AirState
from greenhouse_sim.domain.air import AIR_UNITS, AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.solar.glass import NORMAL_TRANSMITTANCE
from greenhouse_sim.solar.inside import Sunlight
from greenhouse_sim.solar.position import SunPosition, sun_position
from greenhouse_sim.solar.sky import (
    PAR_UMOL_M2_S_PER_W_M2,
    SOLAR_CONSTANT_W_M2,
    clear_sky_ghi_w_m2,
    extraterrestrial_w_m2,
    outside_light,
    par_umol_m2_s,
)
from greenhouse_sim.weather.presets import COLD_SPRING_DAY
from greenhouse_sim.weather.sources import ConstantWeather, RunWeather
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.site import DEFAULT_SITE

EQUINOX = datetime(2026, 3, 20, tzinfo=UTC)
# Solar noon at the default site, 4.5° east, at the March equinox.
EQUINOX_NOON = EQUINOX + timedelta(hours=11, minutes=50)
NOON_S = 11 * 3600 + 50 * 60
UP = Vector3(x=0.0, y=0.0, z=1.0)
# The middle of the climate box's floor, half a metre up.
MIDDLE = Vector3(x=6.0, y=3.2, z=0.5)


def _sun(elevation_deg: float) -> SunPosition:
    return SunPosition(
        elevation_deg=elevation_deg,
        azimuth_deg=180.0,
        declination_deg=0.0,
        equation_of_time_min=0.0,
    )


def _sunlight(weather: ConstantWeather, start: datetime = EQUINOX) -> Sunlight:
    config = SCENARIO_REGISTRY["climate_box"]
    return Sunlight(
        DEFAULT_SITE,
        RunWeather(weather.source(DEFAULT_SITE), start),
        air_grid(config),
        config.envelope,
    )


def test_a_clear_sky_gives_haurwitzs_light_and_none_at_night() -> None:
    # Overhead: 1098 W/m² less the thinnest atmosphere's attenuation.
    assert clear_sky_ghi_w_m2(_sun(90.0)) == pytest.approx(1098.0 * math.exp(-0.057))
    # At the equinox's noon at 52° N, 38° up: about 616 W/m².
    noon = sun_position(EQUINOX_NOON, DEFAULT_SITE)
    assert clear_sky_ghi_w_m2(noon) == pytest.approx(616.0, abs=2.0)
    assert clear_sky_ghi_w_m2(_sun(-5.0)) == 0.0
    # Lower, less.
    lights = [clear_sky_ghi_w_m2(_sun(elevation)) for elevation in (5, 15, 30, 60, 90)]
    assert lights == sorted(lights)


def test_the_sun_gives_most_above_the_atmosphere_at_the_perihelion() -> None:
    january = extraterrestrial_w_m2(datetime(2026, 1, 3, 12, tzinfo=UTC))
    july = extraterrestrial_w_m2(datetime(2026, 7, 4, 12, tzinfo=UTC))

    assert january == pytest.approx(SOLAR_CONSTANT_W_M2 * 1.033, rel=1e-4)
    assert july == pytest.approx(SOLAR_CONSTANT_W_M2 * 0.967, rel=1e-3)


def test_par_is_about_two_point_one_five_micromoles_for_each_watt() -> None:
    assert PAR_UMOL_M2_S_PER_W_M2 == pytest.approx(0.47 * 4.57)
    assert par_umol_m2_s(500.0) == pytest.approx(1074.0, abs=1.0)
    assert AIR_UNITS[AirQuantity.PAR] == "µmol/m²/s"
    assert AIR_UNITS[AirQuantity.IRRADIANCE] == "W/m²"


def test_the_light_is_all_beam_as_far_as_the_beam_carries_it() -> None:
    noon = sun_position(EQUINOX_NOON, DEFAULT_SITE)
    clear = outside_light(clear_sky_ghi_w_m2(noon), noon, EQUINOX_NOON)
    cos_zenith = math.sin(math.radians(noon.elevation_deg))

    assert clear.dhi_w_m2 == pytest.approx(0.0)
    assert clear.dni_w_m2 * cos_zenith == pytest.approx(clear.ghi_w_m2)
    assert clear.par_umol_m2_s == pytest.approx(par_umol_m2_s(clear.ghi_w_m2))
    # A low sun under a bright sky: the beam can carry no more than the sun
    # gives above the atmosphere, and the rest is the sky's.
    low = _sun(3.0)
    bright = outside_light(500.0, low, EQUINOX_NOON)
    assert bright.dni_w_m2 == pytest.approx(extraterrestrial_w_m2(EQUINOX_NOON))
    assert bright.dni_w_m2 * math.sin(math.radians(3.0)) + bright.dhi_w_m2 == pytest.approx(500.0)
    # At night, or with no light, nothing.
    assert outside_light(500.0, _sun(-1.0), EQUINOX_NOON).ghi_w_m2 == 0.0
    assert outside_light(0.0, noon, EQUINOX_NOON).dni_w_m2 == 0.0


def test_a_level_surface_takes_the_beam_by_the_suns_height_and_one_facing_it_all() -> None:
    sunlight = _sunlight(ConstantWeather(global_radiation_w_m2=400.0))
    light = sunlight.outside_at(NOON_S)
    sun = sunlight.sun_at(NOON_S)
    towards = sun.direction(DEFAULT_SITE)
    cos_zenith = math.sin(math.radians(sun.elevation_deg))
    # What the glass passes on the way to the middle of the floor.
    passed = float(sunlight.glazing.beam_transmittance(np.array([[6.0, 3.2, 0.5]]), towards)[0])

    assert sunlight.on(MIDDLE, UP, NOON_S) == pytest.approx(light.dni_w_m2 * cos_zenith * passed)
    assert sunlight.on(MIDDLE, UP, NOON_S) == pytest.approx(400.0 * passed)
    assert sunlight.on(MIDDLE, towards, NOON_S) == pytest.approx(light.dni_w_m2 * passed)
    # Facing north, away from the noon sun, a wall takes none of the beam.
    assert sunlight.on(MIDDLE, Vector3(x=0.0, y=1.0, z=0.0), NOON_S) == pytest.approx(0.0)


def test_inside_the_light_reaches_every_cell_through_the_glass() -> None:
    sunlight = _sunlight(ConstantWeather(global_radiation_w_m2=400.0))
    inside = sunlight.at(NOON_S)
    nx, ny, nz = sunlight.grid.shape

    assert inside.irradiance_w_m2.shape == (nz, ny, nx)
    # Less than outside, but most of it: more under the south roof slope,
    # which the noon sun meets at 38°, than the north one, at 66°.
    assert inside.irradiance_w_m2.max() == pytest.approx(331.0, abs=1.0)
    assert inside.irradiance_w_m2.min() == pytest.approx(290.0, abs=1.0)
    assert np.allclose(inside.par_umol_m2_s, inside.irradiance_w_m2 * PAR_UMOL_M2_S_PER_W_M2)
    # Constant weather's light is only while the sun is up.
    assert np.allclose(sunlight.at(0.0).par_umol_m2_s, 0.0)


def test_a_synthetic_day_has_a_clear_skys_sunshine_by_day_and_none_by_night() -> None:
    source = COLD_SPRING_DAY.source(DEFAULT_SITE, seed=0)
    noon = source.at(EQUINOX_NOON)
    midnight = source.at(EQUINOX)

    assert noon.global_radiation_w_m2 == pytest.approx(
        clear_sky_ghi_w_m2(sun_position(EQUINOX_NOON, DEFAULT_SITE))
    )
    assert midnight.global_radiation_w_m2 == 0.0


def test_constant_weathers_radiation_is_only_while_the_sun_is_up() -> None:
    source = ConstantWeather(global_radiation_w_m2=300.0).source(DEFAULT_SITE)

    assert source.at(EQUINOX_NOON).global_radiation_w_m2 == 300.0
    assert source.at(EQUINOX).global_radiation_w_m2 == 0.0
    assert ConstantWeather().source(DEFAULT_SITE).at(EQUINOX_NOON).global_radiation_w_m2 == 0.0


def test_a_climate_runs_field_carries_the_light() -> None:
    config = SCENARIO_REGISTRY["climate_box"]
    grid = air_grid(config)
    weather = RunWeather(ConstantWeather(global_radiation_w_m2=400.0).source(config.site), EQUINOX)
    nx, ny, nz = grid.shape
    run = ClimateRun(
        base=config.airflow,
        equipment=config.layout.equipment,
        schedule=Schedule.from_start({}),
        settings=config.climate,
        grid=grid,
        solid=np.zeros((nz, ny, nx), dtype=bool),
        weather=weather,
        sunlight=Sunlight(config.site, weather, grid, config.envelope),
    )
    air = AirState(
        temperature=np.full((nz, ny, nx), 16.0),
        humidity=np.full((nz, ny, nx), 8.0),
        co2=np.full((nz, ny, nx), 420.0),
    )
    noon = run.field_of(air, "lit", NOON_S)
    night = run.field_of(air, "dark", 0.0)
    level = noon.sample(AirQuantity.IRRADIANCE, MIDDLE)
    assert isinstance(level, float)
    assert 0.75 * 400.0 < level < NORMAL_TRANSMITTANCE * 400.0
    assert noon.sample(AirQuantity.PAR, MIDDLE) == pytest.approx(par_umol_m2_s(level))
    assert night.sample(AirQuantity.PAR, MIDDLE) == pytest.approx(0.0)


def test_the_api_serves_the_climates_light_and_the_skys() -> None:
    # 10:00 in Amsterdam on 1 January, a low sun, under a clear spring sky.
    response = respond(
        "GET", "/api/scenarios/climate_box/fields/climate?t=36000&weather=cold_spring_day"
    )
    document = FieldDocument.model_validate(response.body)
    field = EnvironmentField.from_document(document)
    weather = json.loads(
        json.dumps(
            respond(
                "GET", "/api/scenarios/climate_box/weather?t=36000&weather=cold_spring_day"
            ).body
        )
    )
    light = weather["light"]
    # In the open south of the first row: the plants' crowns and the crop
    # gutters shade the middle of the floor from a low sun.
    par = field.sample(AirQuantity.PAR, Vector3(x=5.75, y=1.2, z=0.25))

    # About 9° up, so a little over 100 W/m².
    assert 80.0 < light["ghi_w_m2"] < 150.0
    assert light["par_umol_m2_s"] == pytest.approx(par_umol_m2_s(light["ghi_w_m2"]))
    # Inside, through the south wall's glass, a low sun's beam meets it
    # squarely enough for the glass to pass nearly all it can.
    assert isinstance(par, float)
    assert 0.8 * light["par_umol_m2_s"] < par < NORMAL_TRANSMITTANCE * light["par_umol_m2_s"]
    channels = {channel.quantity: channel.unit for channel in document.channels}
    assert channels[AirQuantity.PAR] == "µmol/m²/s"
    assert channels[AirQuantity.IRRADIANCE] == "W/m²"
