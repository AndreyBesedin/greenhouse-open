"""A simulator's state, in one object (decision 0048, AUDIT.15).

A `Simulator` owns what a simulator keeps and runs: the scenarios it knows,
packaged and registered (`scenarios.catalogue`), the positions over its stored
runs, the installations' drafts it is given a store of (`builder.drafts`,
decision 0051), who may act on its runs (`authorisation`, decision 0052), and
what its runs may use (`limits`, decision 0067). The server makes one, or is
given one; a test makes its own. Closing it stops what it runs, ending each
worker's process (`scheduler`), and it starts nothing after. It keeps no book
of playbacks (decision 0074): whoever plays a run makes its `Playback`.

The services that keep runs reach what they keep through it: its climate
runs, crops, sunlight, checkpoints and the states runs take over from them,
each a store of its own, which no other simulator shares. Forgetting them
(`forget`) lets everything kept go, those that build on others first.
"""

import threading
from types import TracebackType
from typing import TYPE_CHECKING, Self

from greenhouse_protocol.authorisation import AuthorisationConfig

from greenhouse_sim.builder.drafts import DraftStore
from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.services import (
    checkpoints,
    climate_runs,
    crop,
    interrupted,
    interventions,
    kept_states,
    scenario_files,
    sunlight,
)
from greenhouse_sim.services.gateway import LOCAL_AUTHORISATION, NO_CREW, Crew
from greenhouse_sim.services.limits import Limits
from greenhouse_sim.services.run_store import ObjectStore
from greenhouse_sim.services.stored_playback import Positions

if TYPE_CHECKING:
    from greenhouse_sim.services.scheduler import Scheduler


class Simulator:
    def __init__(
        self,
        catalogue: Catalogue | None = None,
        *,
        drafts: DraftStore | None = None,
        authorisation: AuthorisationConfig = LOCAL_AUTHORISATION,
        crew: Crew = NO_CREW,
        runs: ObjectStore | None = None,
        limits: Limits | None = None,
    ) -> None:
        self.catalogue = Catalogue() if catalogue is None else catalogue
        # Who may do what on its runs: each run's gateway enforces it. One
        # change of it at a time, so that every epoch begun meanwhile begins
        # under one or is asked to take it.
        self.authorisation = authorisation
        self.authorising = threading.Lock()
        # Who carries its runs' crop actions out (P13.6): so many at once,
        # each taking its kind's time; every run it plays has it.
        self.crew = crew
        # Where the drafts it is asked for are kept, if anywhere: a file of
        # its user's, which outlives it, and which it never forgets.
        self.drafts = drafts
        # Where the runs it plays are kept, and read back, if anywhere: the
        # run store (decision 0065), which outlives it, and the scenario
        # files uploaded to it (P17.11).
        self.runs = runs
        # What its runs may use, and the scheduler that runs them, made when
        # the first is asked for.
        self.limits = Limits() if limits is None else limits
        self.scheduler: Scheduler | None = None
        self.scheduling = threading.Lock()
        # Set under `scheduling` when it closes: no scheduler is made after.
        self.scheduling_closed = False
        self.positions = Positions()
        # What the services keep, this simulator's alone.
        self.states = kept_states.new_store()
        self.sunlight = sunlight.new_store()
        self.climate_runs = climate_runs.new_store()
        self.crops = crop.new_store()
        self.checkpoints = checkpoints.new_store(self.states)
        self._closing = threading.Lock()
        self._closed = False
        # The scenarios uploaded as files beside the run store are known
        # again (P17.11).
        scenario_files.restore(self)
        # The runs left waiting wait again (P18.4), before anything else is said
        # of them. Imported here, as a worker's process makes a simulator.
        from greenhouse_sim.services import scheduler

        scheduler.restore(self)
        # Epochs a producer that crashed left `running` are interrupted, and
        # can be resumed (P17.9).
        interrupted.watch(self)

    @property
    def closed(self) -> bool:
        return self._closed

    def authorise(self, authorisation: AuthorisationConfig) -> None:
        """Who may do what on its runs from now on: a run started later takes
        it from the start, and an epoch in its store that a worker computes,
        will compute or may carry on is asked to take it through the store,
        from the moment its worker takes it (decision 0072). Changes made at
        once are made one after the other, every epoch's in the same order."""
        with self.authorising:
            self.authorisation = authorisation
            interventions.authorise_kept(self, authorisation)

    def forget(self) -> None:
        """Lets go of everything kept, those that build on others first: a
        checkpoint takes its state with it. The scenarios it knows stay."""
        self.positions.forget()
        self.checkpoints.forget()
        self.crops.forget()
        self.climate_runs.forget()
        self.sunlight.forget()
        self.states.forget()

    def close(self) -> None:
        """Stops its scheduler, ending its workers, and lets go of everything
        kept. A close asked for while another is under way
        waits for it; one asked for after does nothing."""
        with self._closing:
            if self._closed:
                return
            try:
                with self.scheduling:
                    self.scheduling_closed = True
                    scheduler = self.scheduler
                if scheduler is not None:
                    scheduler.close()
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
