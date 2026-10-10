"""What shades the sun's beam (P08.5): exact ray tests against boxes and
cylinders, the greenhouse's structure and its light-obstructing fixtures,
and the light inside in their shadows."""

import math
from datetime import UTC, datetime

import numpy as np
import pytest

from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.solar.inside import SHADOW_EVERY_S, Sunlight
from greenhouse_sim.solar.shadows import Shadows
from greenhouse_sim.weather.sources import ConstantWeather, RunWeather
from greenhouse_sim.world.geometry import Box, Cylinder, Quaternion, Transform, Vector3

OVERHEAD = Vector3(x=0.0, y=0.0, z=1.0)
CONFIG = SCENARIO_REGISTRY["climate_box"]


def _towards(azimuth_deg: float, elevation_deg: float) -> Vector3:
    """The unit vector towards the sun, x east and y north."""
    azimuth, elevation = math.radians(azimuth_deg), math.radians(elevation_deg)
    return Vector3(
        x=math.sin(azimuth) * math.cos(elevation),
        y=math.cos(azimuth) * math.cos(elevation),
        z=math.sin(elevation),
    )


def _at(x: float, y: float, z: float) -> Transform:
    return Transform(position=Vector3(x=x, y=y, z=z))


# A bench: a 2 m by 1 m top, 0.1 m thick, 1 m above the floor, its base's
# middle at (5, 5, 1).
BENCH = (_at(5.0, 5.0, 1.0), Box(size_x=2.0, size_y=1.0, size_z=0.1))
# A post: 0.1 m across, 3 m tall, standing at (2, 2).
POST = (_at(2.0, 2.0, 0.0), Cylinder(radius=0.05, height=3.0))


def test_a_box_shades_what_lies_under_it_and_not_beside_it() -> None:
    shadows = Shadows([BENCH])
    points = np.array(
        [
            [5.0, 5.0, 0.2],  # under its middle
            [5.9, 5.4, 0.2],  # under a corner
            [7.0, 5.0, 0.2],  # beside it
            [5.0, 5.0, 1.05],  # inside it
            [5.0, 5.0, 1.1],  # on top of it
            [5.0, 5.0, 2.0],  # above it
        ]
    )

    lit = shadows.lit(points, OVERHEAD)

    assert lit.tolist() == [False, False, True, False, True, True]


def test_a_low_sun_casts_a_long_shadow_the_other_way() -> None:
    shadows = Shadows([BENCH])
    # The sun 30° up in the south: the bench's shadow on the floor lies
    # 1 m / tan 30° = 1.73 m to its north.
    south = _towards(180.0, 30.0)
    behind = 5.0 + 1.0 / math.tan(math.radians(30.0))

    lit = shadows.lit(np.array([[5.0, behind, 0.0], [5.0, 5.0, 0.0], [5.0, 3.0, 0.0]]), south)

    assert lit.tolist() == [False, True, True]


def test_a_cylinder_shades_along_its_shadow() -> None:
    shadows = Shadows([POST])
    # The sun low in the east: the post's shadow runs west of it.
    east = _towards(90.0, 10.0)

    lit = shadows.lit(
        np.array([[1.0, 2.0, 0.5], [1.0, 2.1, 0.5], [3.0, 2.0, 0.5], [1.0, 2.0, 3.5]]), east
    )

    # In its shadow; just past its edge; on the sunny side; and the ray from
    # high enough passes over its top.
    assert lit.tolist() == [False, True, True, True]


def test_a_turned_box_and_a_level_pipe_shade_as_they_lie() -> None:
    # A beam 4 m long and 0.2 m wide, turned 45° about the vertical.
    turned = Quaternion.about(Vector3(x=0.0, y=0.0, z=1.0), math.pi / 4)
    beam = (
        Transform(position=Vector3(x=0.0, y=0.0, z=2.0), rotation=turned),
        Box(size_x=4.0, size_y=0.2, size_z=0.1),
    )
    # A pipe along x, 1 m up: a cylinder turned to lie level.
    level = Quaternion.from_axes(Vector3(x=0.0, y=1.0, z=0.0), Vector3(x=0.0, y=0.0, z=1.0))
    pipe = (
        Transform(position=Vector3(x=10.0, y=0.0, z=1.0), rotation=level),
        Cylinder(radius=0.05, height=4.0),
    )
    shadows = Shadows([beam, pipe])

    lit = shadows.lit(
        np.array(
            [
                [1.0, 1.0, 0.0],  # under the turned beam, along its diagonal
                [1.0, -1.0, 0.0],  # beside it, across its diagonal
                [12.0, 0.0, 0.0],  # under the pipe
                [12.0, 0.2, 0.0],  # beside it
            ]
        ),
        OVERHEAD,
    )

    assert lit.tolist() == [False, True, False, True]


def test_the_greenhouse_is_shaded_by_its_structure_and_fixtures_but_not_its_equipment() -> None:
    shadows = Shadows.of(CONFIG.envelope, CONFIG.layout)
    envelope = CONFIG.envelope
    fixtures = CONFIG.layout.obstructing(Obstruction.LIGHT)

    assert shadows.count == len(envelope.gutters()) + len(envelope.members()) + len(fixtures)
    assert not {"fan", "heater", "dehumidifier"} & {f.fixture_id for f in fixtures}
    # Under the first row's crop gutter, overhead: in its shadow.
    assert not shadows.lit(np.array([[6.0, 2.4, 0.25]]), OVERHEAD)[0]
    # Under a rafter, the sun overhead: the frame at x = 4 m, 1 m in from
    # the south wall.
    assert not shadows.lit(np.array([[4.0, 1.0, 3.9]]), OVERHEAD)[0]
    assert shadows.lit(np.array([[4.5, 1.0, 3.9]]), OVERHEAD)[0]
    # Beside the heater, the sun beyond it: its body casts nothing.
    heater = next(f for f in CONFIG.layout.equipment_fixtures() if f.fixture_id == "heater")
    low, high = heater.bounds()
    beside = np.array([[(low.x + high.x) / 2, high.y + 0.5, 0.2]])
    assert shadows.lit(beside, _towards(180.0, 10.0))[0]


def _equinox_sunlight() -> Sunlight:
    """The climate box at the March equinox under 600 W/m², a clear sky's
    light at noon: a fifth of it the sky's."""
    equinox = datetime(2026, 3, 20, tzinfo=UTC)
    weather = RunWeather(ConstantWeather(global_radiation_w_m2=600.0).source(CONFIG.site), equinox)
    return Sunlight(
        CONFIG.site,
        weather,
        air_grid(CONFIG),
        CONFIG.envelope,
        Shadows.of(CONFIG.envelope, CONFIG.layout),
    )


NOON_S = 11 * 3600 + 50 * 60


def test_inside_the_shaded_floor_takes_only_the_skys_light_and_the_rest_the_beam_too() -> None:
    sunlight = _equinox_sunlight()
    sky = sunlight.outside_at(NOON_S).dhi_w_m2 * sunlight.diffuse_passed

    floor = sunlight.at(NOON_S).irradiance_w_m2[0]
    shaded = floor < 0.5 * floor.max()

    assert 0.02 < shaded.mean() < 0.3
    # In the shade, the sky's light alone; in the sun, the beam besides.
    assert np.allclose(floor[shaded], sky)
    assert floor[~shaded].min() > 0.85 * floor.max()
    # The crop gutters' shadow lies north of them at noon: on the floor
    # cells' level, 0.25 m up, from 0.3 to 0.55 m north of the first row,
    # which spans y = 2.25 to 2.55 m. The cell just north of it is shaded,
    # the one south of it lit.
    grid = sunlight.grid
    xs, ys, _ = grid.centres()
    column = int(np.argmin(np.abs(xs - 6.0)))
    north = int(np.argmin(np.abs(ys - 2.8)))
    south = int(np.argmin(np.abs(ys - 1.75)))
    assert floor[north, column] == pytest.approx(sky)
    assert floor[south, column] > 0.85 * floor.max()
    # The same five minutes of sun shade the same cells.
    assert sunlight.cells_lit(NOON_S) is sunlight.cells_lit(NOON_S + SHADOW_EVERY_S / 3)


def test_a_point_on_a_surface_is_shaded_exactly() -> None:
    sunlight = _equinox_sunlight()
    sky = sunlight.outside_at(NOON_S).dhi_w_m2 * sunlight.diffuse_passed

    # On the first row's slab, and low in its shadow, north of it.
    on_the_slab = sunlight.on(Vector3(x=6.0, y=2.4, z=0.676), OVERHEAD, NOON_S)
    behind = sunlight.on(Vector3(x=6.0, y=2.8, z=0.25), OVERHEAD, NOON_S)
    beyond = sunlight.on(Vector3(x=6.0, y=3.3, z=0.25), OVERHEAD, NOON_S)

    assert on_the_slab > 3 * sky
    assert behind == pytest.approx(sky)
    assert beyond == pytest.approx(on_the_slab, rel=0.05)
