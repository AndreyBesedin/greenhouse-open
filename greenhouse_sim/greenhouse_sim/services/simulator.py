"""A simulator's state, in one object (decision 0048, AUDIT.15).

A `Simulator` owns what a simulator keeps and runs: the scenarios it knows,
packaged and registered (`scenarios.catalogue`), its live runs, the runs it
plays back, and the cursors it has given consumers. The server makes one,
or is given one; a test makes its own. Closing it stops what it runs,
waiting for each run's thread, and it starts nothing after.

The services that keep runs reach what they keep through it: its climate
runs, crops, sunlight, checkpoints and the states runs take over from them.
Until the decision's last step these are the services' module stores,
every simulator's; then each simulator makes its own.
"""

import threading
from types import TracebackType
from typing import Self

from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.services import checkpoints, crop, fields, kept_states, sunlight
from greenhouse_sim.services.consumer import Cursors
from greenhouse_sim.services.live import DEFAULT_SECONDS_PER_DAY, LiveRuns
from greenhouse_sim.services.playback import Playbacks


class Simulator:
    def __init__(
        self,
        catalogue: Catalogue | None = None,
        *,
        seconds_per_day: float = DEFAULT_SECONDS_PER_DAY,
    ) -> None:
        self.catalogue = Catalogue() if catalogue is None else catalogue
        self.live = LiveRuns(self.catalogue, seconds_per_day=seconds_per_day)
        self.playbacks = Playbacks()
        self.cursors = Cursors()
        # What the services keep: the modules' stores, every simulator's,
        # until each simulator makes its own (decision 0048).
        self.climate_runs = fields.CLIMATE_RUNS
        self.crops = crop.CROPS
        self.sunlight = sunlight.SUNLIGHT
        self.checkpoints = checkpoints.CHECKPOINTS
        self.states = kept_states.STATES
        self._closing = threading.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Stops the live runs and the playbacks, and waits for them. A close
        asked for while another is under way waits for it; one asked for
        after does nothing."""
        with self._closing:
            if self._closed:
                return
            try:
                self.live.close()
                self.playbacks.close()
            finally:
                self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()
