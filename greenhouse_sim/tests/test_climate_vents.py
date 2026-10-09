"""Open doors and vents in a climate run (P05.5): exchanging the air against
them with the outside's through their aperture, nothing when closed, and a
draught out when the house is warmer, in when it is cooler."""

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.commands import Schedule
from greenhouse_sim.climate.run import ClimateRun
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.climate.vents import Vent
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.services.scenarios import SceneChanges, changed
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.geometry import Vector3

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
SOLID = cfd.geometry("climate_box").solid()
AIR = ~SOLID
# The glass shut, so that only the vents exchange anything with the outside.
SHUT = CONFIG.climate.model_copy(update={"glazing_u_w_m2k": 0.0})
SPEED_M_S = CONFIG.climate.vent_exchange_m_s
# Under the roof vent, in the top layer of the house's air.
UNDER_THE_VENT = Vector3(x=6.0, y=2.5, z=3.75)


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


def _run(
    openings: dict[str, float],
    settings: ClimateSettings = SHUT,
    levels: dict[str, float] | None = None,
    weather: ConstantWeather = CONFIG.weather,
) -> ClimateRun:
    return ClimateRun(
        base=CONFIG.airflow,
        equipment=CONFIG.layout.equipment,
        schedule=Schedule.from_start(levels or {}),
        settings=settings,
        grid=GRID,
        solid=SOLID,
        weather=CONFIG.model_copy(update={"weather": weather}).run_weather(),
        vents=_vents(openings),
    )


def test_a_closed_door_or_vent_exchanges_nothing() -> None:
    shut = _run({"roof_vent": 0.0, "side_vent": 0.0, "door": 0.0})

    assert shut.vents == ()
    np.testing.assert_array_equal(
        shut.temperature_at(600), np.full(SOLID.shape, SHUT.start_temperature_c)
    )


@pytest.mark.parametrize("opening", ["roof_vent", "side_vent", "door"])
def test_the_exchange_grows_with_the_aperture_the_geometry_gives(opening: str) -> None:
    half, full = _vents({opening: 0.5}), _vents({opening: 1.0})
    config = changed(CONFIG, SceneChanges(openings={opening: 1.0}))
    (aperture,) = [o.aperture_area() for o in config.envelope.openings if o.opening_id == opening]

    full_m3_s = float(full[0].exchange_m3_s(SPEED_M_S).sum())
    half_m3_s = float(half[0].exchange_m3_s(SPEED_M_S).sum())

    assert full_m3_s == pytest.approx(SPEED_M_S * aperture)
    assert 0.0 < half_m3_s < full_m3_s
    assert half_m3_s / full_m3_s == pytest.approx(half[0].aperture_m2 / full[0].aperture_m2)


def test_with_the_outside_cooler_an_open_vent_cools_the_house_towards_it() -> None:
    venting = _run({"roof_vent": 1.0})
    means = [float(venting.temperature_at(moment)[AIR].mean()) for moment in (300, 900, 1800)]

    assert means == sorted(means, reverse=True)
    assert CONFIG.weather.air_temperature_c < means[-1] < means[0] < SHUT.start_temperature_c
    assert venting.temperature_at(3600)[AIR].mean() < means[-1]


def test_an_open_vent_lets_the_outsides_drier_air_in() -> None:
    venting = _run({"roof_vent": 1.0})
    start = venting.air_at(0).humidity[AIR].mean()

    # 8 °C and 90% outside hold 6.0 g/kg; 16 °C and 85% inside, 9.6.
    assert venting.air_at(1800).humidity[AIR].mean() < start - 0.5


def _draught(run: ClimateRun) -> float:
    field = run.field("climate_box_climate", GRID, 600)
    velocity = field.sample(AirQuantity.VELOCITY, UNDER_THE_VENT)
    assert isinstance(velocity, Vector3)
    return velocity.z


def test_the_draught_goes_out_of_a_warmer_house_and_into_a_cooler_one() -> None:
    heated = _run({"roof_vent": 1.0}, CONFIG.climate, {"heater": 1.0})
    warm_outside = CONFIG.weather.model_copy(update={"air_temperature_c": 25.0})
    cooler = _run({"roof_vent": 1.0}, SHUT, weather=warm_outside)
    (vent,) = heated.vents
    face_m2 = GRID.cell_size.x * GRID.cell_size.y * int(vent.cells.sum())

    assert _draught(heated) == pytest.approx(SPEED_M_S * vent.aperture_m2 / face_m2)
    assert _draught(cooler) == pytest.approx(-_draught(heated))
    assert _draught(_run({})) == 0.0


def _climate(query: str) -> EnvironmentField:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def test_a_climate_is_served_with_its_vents_open_as_asked() -> None:
    closed = _climate("?set=heater:1&t=600")
    opened = _climate("?set=heater:1&t=600&open=roof_vent:1")

    closed_t = closed.sample(AirQuantity.TEMPERATURE, UNDER_THE_VENT)
    opened_t = opened.sample(AirQuantity.TEMPERATURE, UNDER_THE_VENT)
    assert isinstance(closed_t, float) and isinstance(opened_t, float)
    assert opened_t < closed_t - 3.0
    response = respond("GET", "/api/scenarios/climate_box/fields/climate?open=skylight:1")
    assert (response.status, response.body) == (
        400,
        {"error": "climate_box has no opening 'skylight'"},
    )


def test_each_vents_cells_lie_against_its_face_and_it_knows_its_way_out() -> None:
    vents = {vent.opening_id: vent for vent in _vents({"roof_vent": 1, "side_vent": 1, "door": 1})}
    nx, ny, nz = GRID.shape

    # The roof vent over the top layer, out upwards; the side vent in the
    # right side wall, at y = 0; the door in the front gable, at x = 0.
    expected = {"roof_vent": (0, 1, nz - 1), "side_vent": (1, -1, 0), "door": (2, -1, 0)}
    for opening_id, (axis, outward, layer) in expected.items():
        vent = vents[opening_id]
        assert (vent.axis, vent.outward) == (axis, outward)
        assert set(np.argwhere(vent.cells)[:, axis]) == {layer}
