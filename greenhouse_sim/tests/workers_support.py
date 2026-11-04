"""What the scheduler's tests run: a short run and a long one of the one-plant box
(`short_runs`), registered with a test's simulator, whose worker has them from the
store; and a worker that ends at once, which a process imports by its name."""

from typing import Final

import short_runs

from greenhouse_sim.services.simulator import Simulator

SHORT: Final = "climate_box_short"
LONG: Final = "climate_box_long"
SHORT_DAYS: Final = 2
# Far longer than any test lets it go on: what a test does while it is running
# takes a few of its days, and a day takes a fraction of a second.
LONG_DAYS: Final = 120


def short_simulator() -> Simulator:
    made = Simulator()
    for name, days in ((SHORT, SHORT_DAYS), (LONG, LONG_DAYS)):
        made.catalogue.register(short_runs.one_plant_box(name, days))
    return made


def ends_at_once(root: str, run_id: str, epoch: int) -> None:
    raise SystemExit(1)
