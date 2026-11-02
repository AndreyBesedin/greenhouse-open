"""What a worker's process builds its simulator with in the scheduler's tests:
the climate box cut to two runs of a few days, since a worker starts from
nothing and does not see the scenarios a test registers in its own process."""

from typing import Final

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.simulator import Simulator

BOX: Final = "climate_box"
SHORT: Final = "climate_box_short"
LONG: Final = "climate_box_long"
SHORT_DAYS: Final = 2
LONG_DAYS: Final = 8

MADE_BY: Final = "workers_support:short_simulator"


def short_simulator() -> Simulator:
    made = Simulator()
    for name, days in ((SHORT, SHORT_DAYS), (LONG, LONG_DAYS)):
        made.catalogue.register(
            SCENARIO_REGISTRY[BOX].model_copy(update=dict(greenhouse_id=name, duration_days=days))
        )
    return made
