"""What the scheduler's tests run: the climate box cut to two runs of a few
days, registered with a test's simulator, whose worker has them from the store;
and a worker that ends at once, which a process imports by its name."""

from typing import Final

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.simulator import Simulator

BOX: Final = "climate_box"
SHORT: Final = "climate_box_short"
LONG: Final = "climate_box_long"
SHORT_DAYS: Final = 2
LONG_DAYS: Final = 8


def short_simulator() -> Simulator:
    made = Simulator()
    for name, days in ((SHORT, SHORT_DAYS), (LONG, LONG_DAYS)):
        made.catalogue.register(
            SCENARIO_REGISTRY[BOX].model_copy(update=dict(greenhouse_id=name, duration_days=days))
        )
    return made


def ends_at_once(root: str, run_id: str, epoch: int) -> None:
    raise SystemExit(1)
