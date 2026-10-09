"""The sun's light on each plant (P08.6): the plants' crowns, each plant's
PAR and daily light integral, the plant model grown in its own light, and
PAR sensors reading the sun's light; in the solar lab, at the March
equinox under a clear sky."""

import json
from http import HTTPStatus

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.biology.plant.variation import draw_traits
from greenhouse_sim.biology.tomato.organ.development import develop, emerged, live_day
from greenhouse_sim.biology.tomato.organ.topology import Plant
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services import sensors
from greenhouse_sim.services.plants import DEVELOPMENT, TRANSPLANT_CD, VARIATION
from greenhouse_sim.services.scenarios import DEFAULT_WEATHER, plant_ids
from greenhouse_sim.services.sunlight import plant_light
from greenhouse_sim.solar.plants import (
    CROWN_DIAMETER_M,
    Crown,
    PlantLight,
    SunlitEnvironment,
    crowns,
)
from greenhouse_sim.solar.shadows import Shadows
from greenhouse_sim.world.geometry import Vector3

LAB = SCENARIO_REGISTRY["solar_lab"]
# Solar noon at the default site, 4.5° east, at the March equinox: 11:50
# UTC, 12:50 on the site's clock, the run's.
NOON_S = 12 * 3600 + 50 * 60
# The crates shade the row's first four plants at noon.
SHADED = [f"solar_lab_plant_{n:03d}" for n in range(1, 5)]
EXPOSED = [f"solar_lab_plant_{n:03d}" for n in range(8, 17)]
OVERHEAD = Vector3(x=0.0, y=0.0, z=1.0)
REST = LocalEnvironment(mean_temperature_c=21.0, par_mol_m2_day=0.0, co2_ppm=800.0)
GROWN_DAYS = 10


def _light() -> PlantLight:
    return plant_light("solar_lab", DEFAULT_LAYOUT, DEFAULT_WEATHER)


def _lab_crowns() -> list[Crown]:
    world = SimulationEngine(LAB).initialize(plant_ids(LAB), greenhouse_id=LAB.greenhouse_id)
    return crowns(world.plants, LAB.layout.planting_positions(), LAB.envelope)


def test_each_plant_has_a_crown_about_its_stem_as_tall_as_it_shows() -> None:
    lab_crowns = _lab_crowns()
    positions = LAB.layout.planting_positions()

    assert [crown.plant_id for crown in lab_crowns] == plant_ids(LAB)
    assert [(c.base.x, c.base.y, c.base.z) for c in lab_crowns] == [
        (p.point.x, p.point.y, p.point.z) for p in positions
    ]
    # Before its first day each plant shows 20 cm of stem.
    assert [crown.height_m for crown in lab_crowns] == pytest.approx([0.2] * len(lab_crowns))
    transform, shape = lab_crowns[0].solid()
    assert shape.radius * 2 == pytest.approx(CROWN_DIAMETER_M)
    # A crown shades what lies under it, and its top does not shade itself.
    shadows = Shadows([crown.solid() for crown in lab_crowns])
    base = lab_crowns[0].base
    under = np.array([[base.x + 0.1, base.y, base.z + 0.1]])
    assert not shadows.lit(under, OVERHEAD)[0]
    assert shadows.lit(lab_crowns[0].top(), OVERHEAD).all()


def test_at_noon_the_crates_shade_the_first_plants_and_the_rest_take_the_sun() -> None:
    light = _light()
    par = light.par_at(NOON_S)

    # The equinox's clear noon outside, 616 W/m², through the south roof's
    # glass: about a thousand µmol/m²/s; and in the crates' shade only the
    # sky's light, a fifth of it.
    assert all(1000.0 < par[plant] < 1150.0 for plant in EXPOSED)
    assert all(150.0 < par[plant] < 250.0 for plant in SHADED)
    assert max(par[plant] for plant in SHADED) < 0.25 * min(par[plant] for plant in EXPOSED)


def test_a_shaded_plants_day_takes_less_light() -> None:
    integrals = _light().daily_light_integral()

    shaded = [integrals[plant] for plant in SHADED]
    exposed = [integrals[plant] for plant in EXPOSED]
    assert max(shaded) < 0.5 * min(exposed)
    # A clear equinox day through glass: about 27 mol/m²/d in the open.
    assert all(25.0 < value < 30.0 for value in exposed)


def test_the_plant_model_takes_each_plants_own_light() -> None:
    environment = SunlitEnvironment(_light(), REST)
    shaded = environment.local(SHADED[0], 0)
    exposed = environment.local(EXPOSED[-1], 0)

    assert shaded.par_mol_m2_day < exposed.par_mol_m2_day
    assert (shaded.mean_temperature_c, shaded.co2_ppm) == (21.0, 800.0)
    with pytest.raises(LookupError, match="no plant"):
        environment.local("nobody", 0)


def _length_cm(plant: Plant) -> float:
    """How long the plant's internodes and leaves are, together."""
    return sum(getattr(organ, "length_cm", 0.0) for _, _, _, organ in plant.organs())


def _grown(plant_id: str, environment: SunlitEnvironment) -> Plant:
    """The lab's first transplant, grown in the light where `plant_id`
    stands, so that two grown so differ only by their light."""
    traits = draw_traits(LAB.random_seed, "p01", VARIATION)
    plant = develop(
        emerged("p01", DEVELOPMENT, LAB.random_seed, traits), TRANSPLANT_CD, DEVELOPMENT
    )
    for day in range(GROWN_DAYS):
        plant = live_day(plant, environment.local(plant_id, day), DEVELOPMENT)
    return plant


def test_a_plant_grown_in_its_own_light_grows_less_where_it_is_shaded() -> None:
    environment = SunlitEnvironment(_light(), REST)

    shaded = _grown(SHADED[1], environment)
    exposed = _grown(EXPOSED[-1], environment)

    assert _length_cm(shaded) < _length_cm(exposed)


def test_the_api_serves_each_plants_light() -> None:
    response = respond("GET", f"/api/scenarios/solar_lab/climate/plants?t={NOON_S}")
    body = json.loads(json.dumps(response.body))

    assert response.status == HTTPStatus.OK
    assert body["time_s"] == NOON_S
    assert set(body["par_umol_m2_s"]) == set(plant_ids(LAB))
    assert 150.0 < body["par_umol_m2_s"][SHADED[0]] < 250.0
    assert body["daily_light_integral_mol_m2_d"][EXPOSED[0]] > 25.0
    refused = respond("GET", "/api/scenarios/solar_lab/climate/plants?t=90000")
    assert refused.status == HTTPStatus.BAD_REQUEST


def test_par_sensors_read_the_light_in_the_sun_and_in_the_shade() -> None:
    truth = sensors.truth("solar_lab", until_s=NOON_S)
    read = {sensor.sensor_id: sensor.values[-1] for sensor in truth.sensors}

    assert read["par_open"] is not None and read["par_shade"] is not None
    assert read["par_open"] > 900.0
    # In the crates' shade, only the sky's light.
    assert 0.0 < read["par_shade"] < 0.3 * read["par_open"]
