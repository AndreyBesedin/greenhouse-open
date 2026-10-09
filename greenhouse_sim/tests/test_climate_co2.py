"""The air's CO2 through a climate run (P06.2): carried and mixed as the
run's third scalar, exchanged with the outside's through open vents, and
otherwise unchanged until something adds or takes it."""

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.services.scenarios import SceneChanges, changed
from greenhouse_sim.world.geometry import Vector3

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
SOLID = cfd.geometry("climate_box").solid()
AIR = ~SOLID


def _vents(openings: dict[str, float]) -> list[Vent]:
    config = changed(CONFIG, SceneChanges(openings=openings))
    geometry = cfd.geometry("climate_box", SceneChanges(openings=openings))
    apertures = {
        opening.opening_id: opening.aperture_area() for opening in config.envelope.openings
    }
    return [
        Vent(opening_id, apertures[opening_id], cells, axis, outward)
        for opening_id, (cells, axis, outward) in geometry.opening_cells().items()
    ]


def _run(start_co2_ppm: float, openings: dict[str, float], levels: dict[str, float]) -> ClimateRun:
    settings = CONFIG.climate.model_copy(update={"start_co2_ppm": start_co2_ppm})
    return ClimateRun(
        base=changed(CONFIG, SceneChanges(openings=openings)).airflow,
        equipment=CONFIG.layout.equipment,
        schedule=Schedule.from_start(levels),
        settings=settings,
        grid=GRID,
        solid=SOLID,
        weather=CONFIG.run_weather(),
        vents=_vents(openings),
    )


def test_with_nothing_to_change_it_the_air_keeps_its_co2_everywhere() -> None:
    run = _run(420.0, {}, {"fan": 1.0, "heater": 1.0, "dehumidifier": 1.0})

    np.testing.assert_allclose(run.air_at(600).co2[AIR], 420.0)


def test_shut_the_house_keeps_its_co2_however_the_fan_stirs_it() -> None:
    run = _run(800.0, {}, {"fan": 1.0})

    assert run.air_at(600).co2[AIR].sum() == pytest.approx(800.0 * AIR.sum(), rel=1e-9)


def test_an_open_vent_draws_the_houses_co2_towards_the_outsides() -> None:
    run = _run(800.0, {"roof_vent": 1.0}, {})
    means = [float(run.air_at(moment).co2[AIR].mean()) for moment in (300, 900, 1800)]

    assert means == sorted(means, reverse=True)
    assert CONFIG.weather.co2_ppm < means[-1] < means[0] < 800.0


def test_the_climate_publishes_its_co2() -> None:
    response = respond("GET", "/api/scenarios/climate_box/fields/climate?t=60")
    field = EnvironmentField.from_document(FieldDocument.model_validate(response.body))

    assert field.sample(AirQuantity.CO2, Vector3(x=6.0, y=3.2, z=1.5)) == pytest.approx(420.0)
