"""The sun's light above each scope of a crop grown by area (P14.9,
decision 0062): the PAR on a level surface at the canopy's height over its
planting positions, their mean, and its hours adding up to its day."""

from typing import Final

import pytest

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.solar.inside import UP, Sunlight
from greenhouse_sim.solar.plants import DAY_EVERY_S, END_WEIGHT, UMOL_PER_MOL
from greenhouse_sim.solar.scopes import ScopeLight
from greenhouse_sim.solar.shadows import Shadows
from greenhouse_sim.solar.sky import PAR_UMOL_M2_S_PER_W_M2
from greenhouse_sim.units import DAY_S, HOUR_S, HOURS_A_DAY
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.scopes import row_scopes

# The reference greenhouse: four rows, each a scope, under its weather.
CONFIG: Final = SCENARIO_REGISTRY["reference_greenhouse"]
SCOPES: Final = row_scopes(CONFIG.layout, CONFIG.envelope)
assert len(SCOPES) == 4
CANOPY_M: Final = 1.2
NOON_S: Final = 12 * HOUR_S


def _light() -> ScopeLight:
    sunlight = Sunlight(
        CONFIG.site,
        CONFIG.run_weather(),
        air_grid(CONFIG),
        CONFIG.envelope,
        Shadows.of(CONFIG.envelope, CONFIG.layout, []),
    )
    return ScopeLight(sunlight, SCOPES, CANOPY_M)


def test_a_scopes_par_is_the_mean_above_its_planting_positions() -> None:
    light = _light()

    for scope in SCOPES:
        above = [
            light.sunlight.on(Vector3(x=p.point.x, y=p.point.y, z=p.point.z + CANOPY_M), UP, NOON_S)
            * PAR_UMOL_M2_S_PER_W_M2
            for p in scope.positions
        ]
        assert light.par_at(NOON_S)[scope.scope_id] == pytest.approx(
            sum(above) / len(above), rel=1e-12
        )
    assert light.par_at(NOON_S)[SCOPES[0].scope_id] > 0.0
    assert light.par_at(0.0) == dict.fromkeys((scope.scope_id for scope in SCOPES), 0.0)


def test_its_hours_add_up_to_its_days_light_integral() -> None:
    """As a plant's daily light integral is summed: every `DAY_EVERY_S`
    through the day, its ends each half a step's worth."""
    light = _light()
    steps = int(DAY_S // DAY_EVERY_S)
    summed = dict.fromkeys((scope.scope_id for scope in SCOPES), 0.0)
    for step in range(steps + 1):
        weight = END_WEIGHT if step in (0, steps) else 1.0
        for scope_id, par in light.par_at(step * DAY_EVERY_S).items():
            summed[scope_id] += weight * par * DAY_EVERY_S / UMOL_PER_MOL

    hours = light.hours_par(0)
    assert {scope_id: len(each) for scope_id, each in hours.items()} == dict.fromkeys(
        summed, HOURS_A_DAY
    )
    assert light.daily_light_integral(0) == pytest.approx(summed, rel=1e-12)
    # Dark at midnight, lit at noon.
    first = hours[SCOPES[0].scope_id]
    assert first[0] == 0.0 and first[11] > 0.0
