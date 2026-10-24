"""A scenario's sunlight (P08.5, P08.6): the sun's and the sky's light inside
its greenhouse, shaded by its structure, its fixtures and its plants'
crowns, as its climate run's field carries it, and the light on each
plant.

Its plants stand as its crop does before its first day, each at its
planting position: as the simple model starts them, or as its transplants
stand where it grows its crop organ by organ. A scenario's sunlight is
kept for each of its layouts and weathers, so that the cells and the
plants it has worked out the light of are found again. How each plant's
light is asked for at a moment of a run is the crop's
(`greenhouse_sim.services.crop`).
"""

from typing import TYPE_CHECKING, Final

from greenhouse_sim.core.crop import crowns
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.grid import air_grid
from greenhouse_sim.services.scenarios import SceneChanges, changed, plant_ids, scenario
from greenhouse_sim.services.stores import Store
from greenhouse_sim.solar.inside import Sunlight
from greenhouse_sim.solar.plants import Crown, PlantLight
from greenhouse_sim.solar.shadows import Shadows

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

# How many scenarios' sunlight, under a layout and a weather, are kept.
KEPT_SUNLIGHT: Final = 8


def new_store() -> Store[tuple[str, str, str], PlantLight]:
    """A simulator's sunlight: the latest `KEPT_SUNLIGHT` (decision 0048)."""
    return Store("sunlight", KEPT_SUNLIGHT, label="/".join)


def first_crowns(config: ScenarioConfig) -> list[Crown]:
    """A scenario's plants' crowns before its first day: its transplants', as
    the model its rows grow starts and stands them
    (`greenhouse_sim.services.crop_models`)."""
    rung = registration(config).rung(config)
    transplants = [rung.transplant(plant_id) for plant_id in plant_ids(config)]
    return crowns(rung, transplants, config.layout.trainings(), config.envelope)


def plant_light(simulator: Simulator, scenario_id: str, layout: str, weather: str) -> PlantLight:
    """A scenario's sunlight with one of its layouts, under a weather, and the
    light on each of its plants: one of those kept, or a new one."""

    def make(_: object) -> PlantLight:
        config = changed(
            simulator.catalogue,
            scenario(simulator.catalogue, scenario_id),
            SceneChanges(layout=layout, weather=weather),
        )
        plant_crowns = first_crowns(config)
        sunlight = Sunlight(
            config.site,
            config.run_weather(),
            air_grid(config),
            config.envelope,
            Shadows.of(config.envelope, config.layout, [crown.solid() for crown in plant_crowns]),
        )
        return PlantLight(sunlight, plant_crowns)

    return simulator.sunlight.made_once((scenario_id, layout, weather), make)
