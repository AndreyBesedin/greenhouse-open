"""A scenario's sunlight (P08.5, P08.6): the sun's and the sky's light inside
its greenhouse, shaded by its structure, its fixtures and its plants'
crowns, as its climate run's field carries it, and the light on each
plant.

Its plants stand as its crop does before its first day, each at its
planting position. A scenario's sunlight is kept for each of its layouts
and weathers, so that the cells and the plants it has worked out the light
of are found again.

Each plant's light is asked for at a moment of a run, as a climate field
is (`greenhouse_sim.services.fields`): its PAR then, and its daily light
integral on the run's first day.
"""

import threading
from collections import OrderedDict
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.climate.day import LONGEST_RUN_S
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.scenarios import (
    DEFAULT_WEATHER,
    SceneChanges,
    changed,
    plant_ids,
    scenario,
)
from greenhouse_sim.solar.inside import Sunlight
from greenhouse_sim.solar.plants import PlantLight, crowns
from greenhouse_sim.solar.shadows import Shadows

# How many scenarios' sunlight, under a layout and a weather, are kept.
KEPT_SUNLIGHT: Final = 8

_KEPT: OrderedDict[tuple[str, str, str], PlantLight] = OrderedDict()
_KEEPING = threading.Lock()


def plant_light(scenario_id: str, layout: str, weather: str) -> PlantLight:
    """A scenario's sunlight with one of its layouts, under a weather, and the
    light on each of its plants: one of those kept, or a new one."""
    key = (scenario_id, layout, weather)
    with _KEEPING:
        kept = _KEPT.get(key)
        if kept is not None:
            _KEPT.move_to_end(key)
            return kept
    config = changed(scenario(scenario_id), SceneChanges(layout=layout, weather=weather))
    world = SimulationEngine(config).initialize(
        plant_ids(config), greenhouse_id=config.greenhouse_id
    )
    plant_crowns = crowns(world.plants, config.layout.planting_positions(), config.envelope)
    sunlight = Sunlight(
        config.site,
        config.run_weather(),
        air_grid(config),
        config.envelope,
        Shadows.of(config.envelope, config.layout, [crown.solid() for crown in plant_crowns]),
    )
    light = PlantLight(sunlight, plant_crowns)
    with _KEEPING:
        light = _KEPT.setdefault(key, light)
        _KEPT.move_to_end(key)
        if len(_KEPT) > KEPT_SUNLIGHT:
            _KEPT.popitem(last=False)
    return light


class PlantsLight(BaseModel):
    """The light on each of a scenario's plants at a moment of a run, in
    seconds from its start: its PAR then, in µmol/m²/s, and its daily light
    integral on the run's first day, in mol/m²/d, by plant."""

    model_config = ConfigDict(frozen=True)

    time_s: float
    par_umol_m2_s: dict[str, float]
    daily_light_integral_mol_m2_d: dict[str, float]


def plants_light(
    scenario_id: str,
    layout: str | None = None,
    time_s: float = 0.0,
    weather: str | None = None,
) -> PlantsLight:
    """The light on each of a scenario's plants `time_s` into a run, with one
    of its layouts, by default its own, under a weather, by default its own.
    A moment outside a run is refused."""
    if not 0.0 <= time_s <= LONGEST_RUN_S:
        raise InvalidRequest(f"a run lasts from 0 to {LONGEST_RUN_S:g} s, not {time_s:g}")
    light = plant_light(scenario_id, layout or DEFAULT_LAYOUT, weather or DEFAULT_WEATHER)
    try:
        return PlantsLight(
            time_s=time_s,
            par_umol_m2_s=light.par_at(time_s),
            daily_light_integral_mol_m2_d=light.daily_light_integral(0),
        )
    except ValueError as unknown:
        raise InvalidRequest(str(unknown)) from unknown
