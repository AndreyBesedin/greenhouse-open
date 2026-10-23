"""A simulator's state, in one object (decision 0048, AUDIT.15).

A `Simulator` owns what a simulator keeps and runs: the scenarios it knows,
packaged and registered (`scenarios.catalogue`), its live runs, the runs it
plays back, the cursors it has given consumers, and the installations'
drafts it is given a store of (`builder.drafts`, decision 0051). The server makes one,
or is given one; a test makes its own. Closing it stops what it runs,
waiting for each run's thread, and it starts nothing after.

The services that keep runs reach what they keep through it: its climate
runs, crops, sunlight, checkpoints and the states runs take over from them,
each a store of its own, which no other simulator shares. Forgetting them
(`forget`) lets everything kept go, those that build on others first.
"""

import threading
from types import TracebackType
from typing import Self

from greenhouse_sim.builder.drafts import DraftStore
from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.services import checkpoints, climate_runs, crop, kept_states, sunlight
from greenhouse_sim.services.consumer import Cursors
from greenhouse_sim.services.live import DEFAULT_SECONDS_PER_DAY, LiveRuns
from greenhouse_sim.services.playback import Playbacks


class Simulator:
    def __init__(
        self,
        catalogue: Catalogue | None = None,
        *,
        seconds_per_day: float = DEFAULT_SECONDS_PER_DAY,
        drafts: DraftStore | None = None,
    ) -> None:
        self.catalogue = Catalogue() if catalogue is None else catalogue
        # Where the drafts it is asked for are kept, if anywhere: a file of
        # its user's, which outlives it, and which it never forgets.
        self.drafts = drafts
        self.live = LiveRuns(self.catalogue, seconds_per_day=seconds_per_day)
        self.playbacks = Playbacks()
        self.cursors = Cursors()
        # What the services keep, this simulator's alone.
        self.states = kept_states.new_store()
        self.sunlight = sunlight.new_store()
        self.climate_runs = climate_runs.new_store()
        self.crops = crop.new_store()
        self.checkpoints = checkpoints.new_store(self.states)
        self._closing = threading.Lock()
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def forget(self) -> None:
        """Lets go of everything kept, those that build on others first: the
        playbacks, which work days out from the runs kept, stop before the
        runs go; a checkpoint takes its state with it; the cursors given go
        too. The scenarios it knows stay."""
        self.playbacks.stop()
        self.checkpoints.forget()
        self.crops.forget()
        self.climate_runs.forget()
        self.sunlight.forget()
        self.states.forget()
        self.cursors.forget()

    def close(self) -> None:
        """Stops the live runs and the playbacks, waits for them, and lets go
        of everything kept. A close asked for while another is under way
        waits for it; one asked for after does nothing."""
        with self._closing:
            if self._closed:
                return
            try:
                self.live.close()
                self.playbacks.close()
                self.forget()
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
