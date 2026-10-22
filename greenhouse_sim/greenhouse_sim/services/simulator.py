"""A simulator's state, in one object (decision 0048, AUDIT.15).

A `Simulator` owns what a simulator keeps and runs: the scenarios it knows,
packaged and registered (`scenarios.catalogue`), and its live runs. The
server makes one, or is given one; a test makes its own. Closing it stops
what it runs, waiting for each run's thread, and it starts nothing after.

The rest of what the services keep moves onto it a step at a time, as the
decision says; until then the module's stores are every simulator's.
"""

import threading
from types import TracebackType
from typing import Self

from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.services.live import DEFAULT_SECONDS_PER_DAY, LiveRuns


class Simulator:
    def __init__(
        self,
        catalogue: Catalogue | None = None,
        *,
        seconds_per_day: float = DEFAULT_SECONDS_PER_DAY,
    ) -> None:
        self.catalogue = Catalogue() if catalogue is None else catalogue
        self.live = LiveRuns(seconds_per_day=seconds_per_day)
        self._closing = threading.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Stops the live runs and waits for them; closing again does nothing."""
        with self._closing:
            if self._closed:
                return
            self._closed = True
        self.live.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.close()
