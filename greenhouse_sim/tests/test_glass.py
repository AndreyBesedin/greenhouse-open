"""The sun's light through the glass (P08.4): how much the glass passes at
each angle, the diffuse sky's share, and which surface each beam crosses."""

import math

import numpy as np
import pytest

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.solar.glass import (
    DIFFUSE_TRANSMITTANCE,
    NORMAL_TRANSMITTANCE,
    Glazing,
    transmittance,
)
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.geometry import Vector3

# The climate box: 12 m by 6.4 m, its eaves 4 m up and its ridge 4.8 m.
BOX = SCENARIO_REGISTRY["climate_box"].envelope
PITCH = math.atan2(0.8, 3.2)


def _towards(azimuth_deg: float, elevation_deg: float) -> Vector3:
    """The unit vector towards the sun, x east and y north."""
    azimuth, elevation = math.radians(azimuth_deg), math.radians(elevation_deg)
    return Vector3(
        x=math.sin(azimuth) * math.cos(elevation),
        y=math.cos(azimuth) * math.cos(elevation),
        z=math.sin(elevation),
    )


def test_the_glass_passes_most_square_on_and_less_as_the_beam_grazes_it() -> None:
    cosines = np.cos(np.radians(np.arange(0.0, 91.0, 1.0)))
    passed = transmittance(cosines)

    assert passed[0] == pytest.approx(NORMAL_TRANSMITTANCE)
    assert np.all((passed >= 0.0) & (passed <= 1.0))
    assert np.all(np.diff(passed) <= 0.0)
    # Nothing beyond about 85°, where the modifier reaches nothing.
    assert passed[86] == 0.0
    assert passed[84] > 0.0
    # ASHRAE's modifier at 60°: 1 − 0.1 (2 − 1) = 0.9.
    assert transmittance(np.array([0.5]))[0] == pytest.approx(0.85 * 0.9)
    # A beam from behind passes nothing.
    assert transmittance(np.array([-0.5]))[0] == 0.0


def test_the_diffuse_sky_passes_the_glass_by_its_mean_over_the_hemisphere() -> None:
    # 2 ∫ τ(θ) cos θ sin θ dθ, numerically, over the cosines.
    cosines = np.linspace(0.0, 1.0, 200_001)
    mean = 2.0 * np.trapezoid(transmittance(cosines) * cosines, cosines)

    assert mean == pytest.approx(DIFFUSE_TRANSMITTANCE, rel=1e-6)
    assert DIFFUSE_TRANSMITTANCE == pytest.approx(0.773, abs=0.001)


def test_a_low_sun_from_the_south_crosses_the_south_wall() -> None:
    glazing = Glazing(BOX)
    # Low in the floor's middle, the sun 15° up in the south: x east, y
    # north, so the right side wall, along y = 0, faces south.
    low = np.array([[6.0, 3.2, 0.25]])

    cosine = glazing.cos_incidence(low, _towards(180.0, 15.0))

    assert cosine[0] == pytest.approx(math.cos(math.radians(15.0)))


def test_a_high_sun_crosses_the_roof_slope_facing_it() -> None:
    glazing = Glazing(BOX)
    under_the_ridge = np.array([[6.0, 3.2, 3.9]])

    # Overhead, the beam meets either slope at the roof's pitch.
    overhead = glazing.cos_incidence(under_the_ridge, Vector3(x=0.0, y=0.0, z=1.0))
    assert overhead[0] == pytest.approx(math.cos(PITCH))
    # From the south, 60° up, it crosses the south slope, which faces it,
    # at 60° + 14° from the level, 16° from its normal.
    south = glazing.cos_incidence(np.array([[6.0, 2.0, 3.9]]), _towards(180.0, 60.0))
    assert south[0] == pytest.approx(math.cos(math.pi / 2 - math.radians(60.0) - PITCH))


def test_a_low_sun_along_the_house_crosses_its_end_wall() -> None:
    glazing = Glazing(BOX)
    # From the east, low: the back end wall, at x = 12 m, faces it.
    cosine = glazing.cos_incidence(np.array([[10.0, 3.2, 1.0]]), _towards(90.0, 10.0))

    assert cosine[0] == pytest.approx(math.cos(math.radians(10.0)))


def test_each_point_crosses_the_glass_through_one_surface_or_none() -> None:
    glazing = Glazing(BOX)
    rng = np.random.default_rng(8)
    points = rng.uniform([0.1, 0.1, 0.1], [11.9, 6.3, 3.9], size=(500, 3))
    for azimuth, elevation in [(90.0, 5.0), (135.0, 20.0), (180.0, 38.0), (250.0, 60.0)]:
        cosine = glazing.cos_incidence(points, _towards(azimuth, elevation))
        # Every ray from inside leaves the house, and meets the glass going
        # out.
        assert np.all((cosine > 0.0) & (cosine <= 1.0))


def test_a_multi_span_house_lets_the_beam_out_through_each_spans_roof() -> None:
    house = Envelope(length=20.0, width=16.0, eave_height=4.0, ridge_height=5.0, spans=4)
    glazing = Glazing(house)
    # Under each span's middle, overhead: the beam meets a slope at its pitch.
    middles = np.array([[10.0, 2.0 + 4.0 * span, 3.95] for span in range(4)])

    cosine = glazing.cos_incidence(middles, Vector3(x=0.0, y=0.0, z=1.0))

    assert np.allclose(cosine, math.cos(math.atan2(1.0, 2.0)))
