"""The air's water through a climate run (P05.4): carried and mixed as its
humidity ratio, taken by a dehumidifier, never more than the air holds,
condensing beyond saturation, and published as relative humidity."""

import numpy as np
import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.climate.projection import conserving, face_flows
from greenhouse_sim.climate.psychrometrics import (
    humidity_ratio_g_kg,
    relative_humidity_pct,
    saturation_pressure_pa,
    saturation_ratio_g_kg,
)
from greenhouse_sim.climate.sources import SECONDS_PER_HOUR, source_terms
from greenhouse_sim.climate.transport import AirState, Transport
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldDocument
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.world.equipment import Dehumidifier, Fan
from greenhouse_sim.world.geometry import Vector3

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
SOLID = cfd.geometry("climate_box").solid()
AIR = ~SOLID
NX, NY, NZ = GRID.shape
FAN = next(piece for piece in CONFIG.layout.equipment if isinstance(piece, Fan))
DEHUMIDIFIER = next(piece for piece in CONFIG.layout.equipment if isinstance(piece, Dehumidifier))
STILL = np.zeros((NZ, NY, NX, 3))
# The climate box's starting air: 16 °C at 85%.
START = AirState(
    temperature=np.full((NZ, NY, NX), 16.0),
    humidity=np.full((NZ, NY, NX), float(humidity_ratio_g_kg(16.0, 85.0))),
    co2=np.full((NZ, NY, NX), 420.0),
)
# Sealed: its glass passes nothing, and it leaks nothing.
SHUT = CONFIG.climate.model_copy(
    update={"glazing_u_w_m2k": 0.0, "infiltration_per_h": 0.0, "infiltration_per_h_per_m_s": 0.0}
)
OUTSIDE = CONFIG.run_weather().at(0.0)


def _transport(velocity: np.ndarray, settings: object = SHUT) -> Transport:
    flows = conserving(face_flows(GRID, velocity, SOLID), SOLID)
    return Transport(GRID, flows, SOLID, settings)  # type: ignore[arg-type]


# ASHRAE Handbook, Fundamentals: the saturation pressure of water (kPa), and
# the humidity ratio of saturated air at 101.325 kPa (g/kg).
TABLE = [
    (0.0, 0.6112, 3.789),
    (10.0, 1.2282, 7.661),
    (20.0, 2.3392, 14.758),
    (30.0, 4.2467, 27.329),
]


@pytest.mark.parametrize(("temperature", "pressure_kpa", "saturated_g_kg"), TABLE)
def test_moist_air_agrees_with_the_psychrometric_tables(
    temperature: float, pressure_kpa: float, saturated_g_kg: float
) -> None:
    assert saturation_pressure_pa(temperature) == pytest.approx(pressure_kpa * 1000, rel=0.001)
    # The tables count the small part pressure plays in the vapour's share,
    # which the run leaves out.
    assert saturation_ratio_g_kg(temperature) == pytest.approx(saturated_g_kg, rel=0.01)


def test_relative_humidity_and_the_humidity_ratio_are_one_anothers_inverse() -> None:
    temperatures = np.array([5.0, 16.0, 25.0])
    relative = np.array([30.0, 85.0, 100.0])

    ratio = humidity_ratio_g_kg(temperatures, relative)

    np.testing.assert_allclose(relative_humidity_pct(temperatures, ratio), relative)
    # Air at 20 °C and 50% holds about 7.3 g/kg.
    assert float(humidity_ratio_g_kg(20.0, 50.0)) == pytest.approx(7.3, abs=0.05)


@pytest.mark.parametrize("velocity", [STILL, None], ids=["still", "fan on"])
def test_shut_off_the_air_loses_what_the_dehumidifier_takes(velocity: np.ndarray | None) -> None:
    jet = source_terms(FAN, 1.0, GRID, SOLID).velocity
    transport = _transport(jet if velocity is None else velocity)
    terms = source_terms(DEHUMIDIFIER, 1.0, GRID, SOLID)

    after = transport.advance(START, terms, 600, OUTSIDE)

    rate_kg = DEHUMIDIFIER.removal_kg_h * 600 / SECONDS_PER_HOUR
    lost = transport.water_kg(START.humidity) - transport.water_kg(after.humidity)
    assert after.removed_kg == pytest.approx(rate_kg, rel=1e-9)
    assert after.condensed_kg == 0.0
    assert lost == pytest.approx(rate_kg, rel=1e-6)


def test_a_dehumidifier_never_takes_more_than_the_air_holds() -> None:
    thirsty = DEHUMIDIFIER.model_copy(update={"removal_kg_h": 1000.0})
    terms = source_terms(thirsty, 1.0, GRID, SOLID)
    transport = _transport(STILL)

    after = transport.advance(START, terms, 600, OUTSIDE)

    assert after.humidity.min() >= 0.0
    assert after.removed_kg <= transport.water_kg(START.humidity)
    # Its own cells are dry; the rest of the house is drying into them.
    assert after.humidity[terms.water_removed_kg_s > 0].max() < 0.01
    assert after.removed_kg < 1000.0 * 600 / SECONDS_PER_HOUR


def test_cooling_air_condenses_what_it_can_no_longer_hold() -> None:
    # Through its glass, its gaps sealed so that its water stays.
    unleaking = {"infiltration_per_h": 0.0, "infiltration_per_h_per_m_s": 0.0}
    transport = _transport(STILL, CONFIG.climate.model_copy(update=unleaking))
    nothing = source_terms(DEHUMIDIFIER, 0.0, GRID, SOLID)

    after = transport.advance(START, nothing, 600, OUTSIDE)

    relative = relative_humidity_pct(after.temperature, after.humidity)
    assert relative[AIR].max() <= 100.0 + 1e-9
    assert after.condensed_kg > 0.0
    budget = transport.water_kg(after.humidity) + after.condensed_kg
    assert budget == pytest.approx(transport.water_kg(START.humidity), rel=1e-9)


def test_uniform_water_stays_uniform_in_the_fans_flow() -> None:
    jet = source_terms(FAN, 1.0, GRID, SOLID).velocity
    nothing = source_terms(DEHUMIDIFIER, 0.0, GRID, SOLID)

    after = _transport(jet).advance(START, nothing, 300, OUTSIDE)

    np.testing.assert_array_equal(after.humidity[AIR], START.humidity[AIR])


def _climate(query: str) -> EnvironmentField:
    response = respond("GET", f"/api/scenarios/climate_box/fields/climate{query}")
    assert response.status == 200, response.body
    return EnvironmentField.from_document(FieldDocument.model_validate(response.body))


def _relative(field: EnvironmentField, x: float, y: float, z: float) -> float:
    value = field.sample(AirQuantity.HUMIDITY, Vector3(x=x, y=y, z=z))
    assert isinstance(value, float)
    return value


def test_the_climate_publishes_relative_humidity_drying_around_a_running_dehumidifier() -> None:
    start = _climate("")
    dried = _climate("?set=dehumidifier:1&t=600")
    beside, far = (6.0, 5.3, 0.75), (2.0, 1.0, 0.75)

    assert start.channels[AirQuantity.HUMIDITY] == pytest.approx(85.0)
    # Ten minutes in, the unheated house has cooled to saturation, but not
    # the air the dehumidifier dries and warms.
    assert _relative(dried, *far) > 99.0
    assert _relative(dried, *beside) < 90.0
