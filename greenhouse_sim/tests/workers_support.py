"""What the scheduler's tests run: the climate box cut to two runs of a few
days, registered with a test's simulator, whose worker has them from the store;
and workers that end at once or are killed, which a process imports by name."""

import os
import signal
from pathlib import Path
from typing import Final

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status
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


def takes_it_up_and_is_killed(root: str, run_id: str, epoch: int) -> None:
    """A worker killed outright, with no chance to write why: its epoch is
    `running`, with one commit, as it left them."""
    kept = EpochStore(FolderStore(Path(root)), run_id, epoch)
    kept.set_status(Status.RUNNING)
    kept.commit(0.0, DAY_S)
    os.kill(os.getpid(), signal.SIGKILL)
