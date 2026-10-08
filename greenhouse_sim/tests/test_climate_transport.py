"""The air's flow made to conserve mass, and its temperature carried, mixed,
heated and exchanged with the outside (P05.3)."""

import numpy as np
import pytest

from greenhouse_sim.climate.projection import FaceFlows, conserving, face_flows
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.climate.sources import SourceTerms, source_terms
from greenhouse_sim.climate.transport import AirState, Transport
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import cfd
from greenhouse_sim.services.fields import air_grid
from greenhouse_sim.world.equipment import Fan, Heater

CONFIG = SCENARIO_REGISTRY["climate_box"]
GRID = air_grid(CONFIG)
SOLID = cfd.geometry("climate_box").solid()
AIR = ~SOLID
NX, NY, NZ = GRID.shape
XS, YS, ZS = GRID.centres()
FAN = next(piece for piece in CONFIG.layout.equipment if isinstance(piece, Fan))
HEATER = next(piece for piece in CONFIG.layout.equipment if isinstance(piece, Heater))
JET = source_terms(FAN, 1.0, GRID, SOLID).velocity
HEAT_W = source_terms(HEATER, 1.0, GRID, SOLID).heat_w
NO_HEAT = np.zeros((NZ, NY, NX))
STILL = np.zeros((NZ, NY, NX, 3))
START = np.full((NZ, NY, NX), 16.0)
# The climate box's: 8 °C outside, 16 °C to start, single glass.
SETTINGS = CONFIG.climate
SHUT = SETTINGS.model_copy(update={"glazing_u_w_m2k": 0.0})
# The glazing's walls and roof: two 12 by 4 m sides, two 6.4 by 4 m ends,
# and the 12 by 6.4 m top of the grid.
GLASS_M2 = 2 * 12 * 4 + 2 * 6.4 * 4 + 12 * 6.4


def _flows(velocity: np.ndarray) -> FaceFlows:
    return conserving(face_flows(GRID, velocity, SOLID), SOLID)


def _transport(velocity: np.ndarray, settings: ClimateSettings = SETTINGS) -> Transport:
    return Transport(GRID, _flows(velocity), SOLID, settings)


def _advance(
    transport: Transport, temperature: np.ndarray, heat_w: np.ndarray, duration_s: float
) -> np.ndarray:
    """The temperature after `duration_s`, in dry air, where nothing
    condenses."""
    dry = AirState(temperature=temperature, humidity=np.zeros_like(temperature))
    heating = SourceTerms(grid=GRID, velocity=STILL, heat_w=heat_w, water_removed_kg_s=NO_HEAT)
    return transport.advance(dry, heating, duration_s).temperature


def _cell(x: float, y: float, z: float) -> tuple[int, int, int]:
    return (
        int(np.argmin(np.abs(ZS - z))),
        int(np.argmin(np.abs(YS - y))),
        int(np.argmin(np.abs(XS - x))),
    )


def test_a_fans_jet_is_made_to_conserve_the_air() -> None:
    raw = face_flows(GRID, JET, SOLID)
    flows = conserving(raw, SOLID)

    assert np.abs(raw.divergence()).max() > 0.1
    assert np.abs(flows.divergence()).max() < 1e-8


def test_conserving_air_is_left_as_it_is() -> None:
    once = _flows(JET)
    twice = conserving(once, SOLID)

    for first, second in zip(once.flows, twice.flows, strict=True):
        np.testing.assert_allclose(second, first, atol=1e-9)


def test_no_air_flows_into_an_obstacle() -> None:
    flows = _flows(JET)

    for axis, low, high, flow in flows.faces():
        touching = SOLID[low] | SOLID[high]
        assert not flow[touching].any(), axis


def test_the_fan_draws_the_air_it_blows_from_behind_it_and_the_house_returns_it() -> None:
    velocity = _flows(JET).velocity()
    behind = _cell(0.25, 3.2, 2.8)
    in_its_core = _cell(3.25, 3.2, 2.8)
    over_the_floor = _cell(6.0, 3.2, 0.25)

    # The jet alone blew nothing behind the fan.
    assert JET[behind][0] == 0.0
    assert velocity[behind][0] > 0.1
    # Its core keeps most of its speed; the house sends the air back low down.
    assert velocity[in_its_core][0] == pytest.approx(JET[in_its_core][0], rel=0.1)
    assert velocity[over_the_floor][0] < -0.03


def test_uniform_air_stays_uniform_however_the_air_flows() -> None:
    temperature = _advance(_transport(JET, SHUT), START, NO_HEAT, 600)

    assert np.abs(temperature - 16.0).max() == 0.0


def test_carried_and_mixed_temperatures_stay_within_those_around_them() -> None:
    rng = np.random.default_rng(5)
    start = np.where(AIR, rng.uniform(10.0, 20.0, size=START.shape), 16.0)

    temperature = _advance(_transport(JET, SHUT), start, NO_HEAT, 300)

    assert temperature[AIR].min() >= start[AIR].min()
    assert temperature[AIR].max() <= start[AIR].max()
    assert temperature[AIR].std() < start[AIR].std()


@pytest.mark.parametrize(
    ("velocity", "tolerance"), [(STILL, 1e-12), (JET, 1e-8)], ids=["still", "fan on"]
)
def test_shut_off_from_the_outside_the_air_gains_the_heaters_energy(
    velocity: np.ndarray, tolerance: float
) -> None:
    transport = _transport(velocity, SHUT)
    temperature = _advance(transport, START, HEAT_W, 600)

    gained = transport.heat_j(temperature) - transport.heat_j(START)
    assert gained == pytest.approx(HEATER.power_w * 600, rel=tolerance)


def test_the_house_settles_where_the_heater_balances_what_the_glass_loses() -> None:
    transport = _transport(STILL)
    temperature = _advance(transport, START, HEAT_W, 2 * 3600)
    later = _advance(transport, temperature, HEAT_W, 600)

    assert transport.envelope_loss_w(later) == pytest.approx(HEATER.power_w, rel=0.01)
    np.testing.assert_allclose(later, temperature, atol=1e-3)
    # About where 10 kW keeps 224 m² of single glass above 8 °C outside.
    balance = SETTINGS.outside_temperature_c + HEATER.power_w / (6.0 * GLASS_M2)
    assert later[AIR].mean() == pytest.approx(balance, abs=0.5)


def test_with_the_outside_warmer_and_nothing_running_the_house_warms_towards_it() -> None:
    warm = SETTINGS.model_copy(update={"outside_temperature_c": 25.0})
    transport = _transport(STILL, warm)
    means = []
    temperature = START
    for _ in range(6):
        temperature = _advance(transport, temperature, NO_HEAT, 300)
        means.append(float(temperature[AIR].mean()))

    assert means == sorted(means)
    assert 16.0 < means[0] < means[-1] < 25.0
    final = _advance(transport, temperature, NO_HEAT, 3 * 3600)
    assert final[AIR].mean() == pytest.approx(25.0, abs=0.01)


def test_a_heaters_warmth_spreads_out_from_it_with_time() -> None:
    transport = _transport(STILL)
    beside = _cell(10.25, 0.75, 0.75)
    across = _cell(8.25, 3.25, 0.75)
    far = _cell(6.25, 3.25, 0.75)
    early = _advance(transport, START, HEAT_W, 30)
    later = _advance(transport, early, HEAT_W, 270)

    # Half a minute in, its corner is warm, and 3 m away barely.
    assert early[beside] > 25.0
    assert early[across] < 17.0
    # Five minutes in, its warmth has reached 3 m away, but not 5 m, where the
    # cold glass still cools the air.
    assert later[across] > early[across] + 1.0
    assert later[far] < early[far] < START[far]
    assert later[beside] > later[across] > later[far]


def test_each_step_keeps_within_the_air_crossing_half_a_cell_and_the_mixing_limit() -> None:
    jet = _transport(JET)
    still = _transport(STILL)
    fastest = float(np.linalg.norm(_flows(JET).velocity(), axis=-1).max())
    cell = min(GRID.cell_size.x, GRID.cell_size.y, GRID.cell_size.z)

    size = GRID.cell_size
    mixing = 2 * SETTINGS.mixing_m2_s * (1 / size.x**2 + 1 / size.y**2 + 1 / size.z**2)

    assert jet.step_s() * fastest <= 0.5 * cell
    assert still.step_s() * mixing <= 0.5 + 1e-9


def test_cells_obstacles_fill_keep_their_temperature() -> None:
    temperature = _advance(_transport(JET), START, HEAT_W, 120)

    np.testing.assert_array_equal(temperature[SOLID], START[SOLID])
    assert SOLID.any()


def test_a_flow_or_solid_cells_of_another_grid_are_refused() -> None:
    with pytest.raises(ValueError, match="cover the grid"):
        Transport(GRID, _flows(STILL), np.zeros((1, 1, 1), dtype=bool), SETTINGS)
