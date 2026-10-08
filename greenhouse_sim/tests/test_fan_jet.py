"""A fan's jet (P05.2): a round free jet along the fan's heading, carrying
the fan's flow at its core speed for six diameters, then spreading and
slowing, and nothing behind the fan or with it off."""

import math

import numpy as np
import pytest

from greenhouse_sim.climate.jets import JET_DECAY, jet_velocity
from greenhouse_sim.climate.sources import source_terms
from greenhouse_sim.fields.field import CellCounts, FieldGrid
from greenhouse_sim.world.equipment import Fan
from greenhouse_sim.world.geometry import Vector3

# The climate box's fan: 1 m3/s through a 0.5 m rotor, 2.8 m up, blowing
# down the house.
FAN = Fan(
    actuator_id="fan",
    position=Vector3(x=1.0, y=3.2, z=2.8),
    diameter_m=0.5,
    flow_m3_s=1.0,
)
CORE_SPEED_M_S = 1.0 / (math.pi * 0.25**2)
# Its core reaches six rotor diameters downstream.
CORE_M = 3.0
# Fine enough across the jet to integrate it: 2.5 cm cells across a block of
# air centred on the fan's axis, 3.6 m square, wider than the jet reaches
# within 7 m; 10 cm cells along it, a plane's centre 1 cm in front of the
# rotor, and cells behind it.
FINE = FieldGrid(
    origin=Vector3(x=0.06, y=3.2 - 1.8125, z=2.8 - 1.8125),
    cell_size=Vector3(x=0.1, y=0.025, z=0.025),
    cells=CellCounts(x=80, y=145, z=145),
)
OPEN = np.zeros(tuple(reversed(FINE.shape)), dtype=bool)
XS, YS, ZS = FINE.centres()
CELL_AREA_M2 = FINE.cell_size.y * FINE.cell_size.z


def _plane(velocity: np.ndarray, x: float) -> np.ndarray:
    """The velocity along x through the plane of cells nearest `x`."""
    i = int(np.argmin(np.abs(XS - x)))
    plane: np.ndarray = velocity[:, :, i, 0]
    return plane


def test_at_its_rotor_the_jet_carries_the_fans_flow_at_its_core_speed() -> None:
    plane = _plane(jet_velocity(FAN, 1.0, FINE, OPEN), FAN.position.x + 0.01)

    assert plane.sum() * CELL_AREA_M2 == pytest.approx(1.0, rel=0.01)
    assert plane.max() == pytest.approx(CORE_SPEED_M_S, rel=0.01)


def test_over_its_core_it_keeps_its_flow_and_speed() -> None:
    velocity = jet_velocity(FAN, 1.0, FINE, OPEN)

    for distance in (1.0, 2.0, CORE_M - 0.05):
        plane = _plane(velocity, FAN.position.x + distance)
        assert plane.sum() * CELL_AREA_M2 == pytest.approx(1.0, rel=0.01)
        assert plane.max() == pytest.approx(CORE_SPEED_M_S, rel=0.01)


def test_beyond_its_core_it_draws_in_air_and_slows_but_keeps_its_momentum() -> None:
    velocity = jet_velocity(FAN, 1.0, FINE, OPEN)
    distances = (0.01, 4.0, 5.5, 7.0)
    planes = [_plane(velocity, FAN.position.x + distance) for distance in distances]
    flows = [plane.sum() * CELL_AREA_M2 for plane in planes]
    speeds = [plane.max() for plane in planes]
    momenta = [(plane**2).sum() * CELL_AREA_M2 for plane in planes]

    assert flows == sorted(flows)
    assert speeds == sorted(speeds, reverse=True)
    assert momenta == pytest.approx([momenta[0]] * len(distances), rel=0.01)


def test_beyond_its_core_its_speed_falls_as_a_round_jets_does() -> None:
    velocity = jet_velocity(FAN, 1.0, FINE, OPEN)

    for distance in (4.0, 5.5, 7.0):
        plane = _plane(velocity, FAN.position.x + distance)
        # K U0 D / x, to the plane's cell.
        assert plane.max() == pytest.approx(JET_DECAY * CORE_SPEED_M_S * 0.5 / distance, rel=0.01)


def test_it_blows_along_the_fans_heading() -> None:
    velocity = jet_velocity(FAN, 1.0, FINE, OPEN)
    turned = FAN.model_copy(update={"heading": math.pi / 2, "position": Vector3(x=4, y=2, z=2.8)})
    across = jet_velocity(turned, 1.0, FINE, OPEN)

    assert np.abs(velocity[..., 1:]).max() == 0.0
    assert velocity[..., 0].min() >= 0.0
    assert np.abs(across[..., 0]).max() < 1e-12
    assert across[..., 1].max() == pytest.approx(velocity[..., 0].max(), rel=0.05)


def test_nothing_changes_behind_the_fan_or_far_beside_it() -> None:
    velocity = jet_velocity(FAN, 1.0, FINE, OPEN)
    behind = XS < FAN.position.x

    assert not velocity[:, :, behind].any()
    # 1.8 m beside its axis, 3 m downstream: beyond three widths.
    j = int(np.argmin(np.abs(YS - (FAN.position.y + 1.8))))
    i = int(np.argmin(np.abs(XS - (FAN.position.x + 3.0))))
    assert not velocity[:, j, i].any()


def test_it_scales_with_the_fans_level_and_vanishes_when_off() -> None:
    full = jet_velocity(FAN, 1.0, FINE, OPEN)

    np.testing.assert_allclose(jet_velocity(FAN, 0.4, FINE, OPEN), 0.4 * full)
    assert not jet_velocity(FAN, 0.0, FINE, OPEN).any()


def test_it_adds_nothing_where_obstacles_stand() -> None:
    solid = OPEN.copy()
    i = int(np.argmin(np.abs(XS - 3.0)))
    solid[:, :, i] = True

    blocked = jet_velocity(FAN, 1.0, FINE, solid)

    assert not blocked[:, :, i].any()
    assert blocked[:, :, i + 1].any()


def test_a_fans_source_terms_are_its_jet_and_nothing_else() -> None:
    terms = source_terms(FAN, 0.5, FINE, OPEN)

    np.testing.assert_array_equal(terms.velocity, jet_velocity(FAN, 0.5, FINE, OPEN))
    assert terms.total_heat_w() == 0.0
    assert terms.total_water_removed_kg_s() == 0.0
