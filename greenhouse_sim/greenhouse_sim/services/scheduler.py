"""Many epochs at once (P17.7, decision 0065): a scheduler runs workers, each
in a process of its own, up to a number, and queues the rest.

A run asked for is an epoch started in the run store, `queued`, and a worker
takes it when there is room: a process that builds its own simulator, executes
the epoch into the store (`workers.execute`) and ends. Several runs of one
scenario, at different seeds as when policies are trained, are several
epochs, each a process. The store is the only channel between a worker and
the API, so that whoever reads an epoch reads it while it is computed, as far
as the last commit names (`stored_playback`).

A process is the worker because P17.1 measured what a thread costs a process
that is working: 46% of its speed against 5% for another process.

An epoch whose worker ends without ending it, killed or lost, is told
`interrupted` with what it had committed, and can be asked for again to be
carried on from there (`resume`, P17.9): queued once more, taken by a worker
that resumes it. An epoch still `queued` or `running` when the producer that
started it is gone is found at startup (`interrupted.mark`).
"""

import importlib
import logging
import multiprocessing
import threading
from collections import deque
from dataclasses import dataclass
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Final

from greenhouse_sim.services import interrupted
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status, StoredRun, stored_run
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import (
    Driver,
    Free,
    Paced,
    check_resumable,
    execute,
    queued,
)
from greenhouse_sim.services.workers import resume as carry_on

logger = logging.getLogger(__name__)

# What a worker builds its simulator with: a name, `module:function`, since a
# worker is a process that starts from nothing. A simulator whose scenarios
# are not the packaged ones names its own.
PACKAGED: Final = "greenhouse_sim.services.simulator:Simulator"
# How often the scheduler looks at its workers.
LOOK_EVERY_S: Final = 0.1
# How long a worker told to end has before it is killed.
END_WITHIN_S: Final = 10.0


def work(
    root: str, run_id: str, epoch: int, driver: Driver, made_by: str, *, resuming: bool = False
) -> None:
    """A worker's process: executes the epoch `epoch` of the run `run_id` in
    the store under `root`, or carries it on if it is `resuming`, with a
    simulator `made_by` makes, and exits with 0 if the epoch finished."""
    module, _, name = made_by.partition(":")
    simulator = getattr(importlib.import_module(module), name)()
    with simulator:
        kept = EpochStore(FolderStore(Path(root)), run_id, epoch)
        status = (carry_on if resuming else execute)(simulator, kept, driver)
    raise SystemExit(0 if status == Status.FINISHED else 1)


@dataclass(frozen=True)
class Worker:
    """An epoch being executed, and the process that executes it."""

    run_id: str
    epoch: int
    pid: int


@dataclass(frozen=True)
class _Job:
    run_id: str
    epoch: int
    driver: Driver
    resuming: bool = False


class Scheduler:
    """The workers of a simulator whose run store is a folder: at most `limit`
    at once, the rest waiting in the order they were asked for."""

    def __init__(
        self, simulator: Simulator, root: Path, *, limit: int, made_by: str = PACKAGED
    ) -> None:
        if limit < 1:
            raise ValueError(f"a scheduler runs one worker at least, not {limit}")
        self._simulator = simulator
        self._root = root
        self._objects = FolderStore(root)
        self._limit = limit
        self._made_by = made_by
        # A worker is a process started from nothing, not a copy of this one
        # with its threads and locks.
        self._context = multiprocessing.get_context("spawn")
        # Re-entrant: finding an epoch no one works asks the scheduler what it
        # holds, and is done under the lock a resume is scheduled under.
        self._lock = threading.RLock()
        self._waiting: deque[_Job] = deque()
        self._running: dict[tuple[str, int], SpawnProcess] = {}
        self._cancelled: set[tuple[str, int]] = set()
        # The running workers that were asked to carry an epoch on.
        self._resuming: set[tuple[str, int]] = set()
        self._closed = threading.Event()
        self._watcher = threading.Thread(target=self._watch, name="workers", daemon=True)
        self._watcher.start()

    def start(
        self,
        scenario_id: str,
        *,
        layout: str | None = None,
        seed: int | None = None,
        driver: Driver | None = None,
    ) -> StoredRun:
        """Asks for a run of `scenario_id` at `layout` and `seed`: a new epoch
        of it, started in the store, executed when a worker is free. A driver
        takes the epoch as fast as it can go, or at a pace; a stepped one
        takes its moments from its caller's process, which a worker is not."""
        chosen = Free() if driver is None else driver
        if not isinstance(chosen, Free | Paced):
            raise InvalidRequest("a worker advances its epoch freely or at a pace")
        with self._lock:
            if self._closed.is_set():
                raise Conflict("the workers are closed")
            epoch = queued(self._simulator, self._objects, scenario_id, layout=layout, seed=seed)
            self._waiting.append(_Job(epoch.run_id, epoch.epoch, chosen))
            self._launch()
            return stored_run(self._objects, epoch.run_id, epoch.epoch)

    def resume(self, run_id: str, epoch: int, *, driver: Driver | None = None) -> StoredRun:
        """Asks for an `interrupted` epoch to be carried on from its last
        commit: queued once more, and taken by a worker that resumes it when
        there is room. An epoch the store still calls `running` whose producer
        is gone is found interrupted first, under the lock the epoch is queued
        under, so that two requests for it are told apart: the second finds
        the epoch queued. Refused, as `workers.check_resumable` says, if it
        cannot be; the store is not changed by a refusal."""
        chosen = Free() if driver is None else driver
        if not isinstance(chosen, Free | Paced):
            raise InvalidRequest("a worker advances its epoch freely or at a pace")
        key = (run_id, epoch)
        if epoch not in stored_epochs(self._objects, run_id):
            raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
        kept = EpochStore(self._objects, run_id, epoch)
        with self._lock:
            if self._closed.is_set():
                raise Conflict("the workers are closed")
            if key in self._running or any((j.run_id, j.epoch) == key for j in self._waiting):
                raise Conflict(f"epoch {epoch} of {run_id} is waiting for a worker or has one")
            interrupted.mark_epoch(self._simulator, run_id, epoch)
            if kept.manifest().status != Status.INTERRUPTED:
                raise Conflict(
                    f"epoch {epoch} of {run_id} is {kept.manifest().status}: "
                    "only an interrupted one resumes"
                )
            check_resumable(kept)
            kept.set_status(Status.QUEUED)
            self._waiting.append(_Job(run_id, epoch, chosen, resuming=True))
            self._launch()
        return stored_run(self._objects, run_id, epoch)

    def workers(self) -> list[Worker]:
        """The epochs being executed now."""
        with self._lock:
            return [
                Worker(run_id, epoch, process.pid or 0)
                for (run_id, epoch), process in self._running.items()
            ]

    def waiting(self) -> list[tuple[str, int]]:
        """The epochs waiting for a worker, the next first."""
        with self._lock:
            return [(job.run_id, job.epoch) for job in self._waiting]

    def cancel(self, run_id: str, epoch: int) -> StoredRun:
        """Ends an epoch this scheduler runs or holds: one waiting is taken
        out of the queue, one being executed has its worker ended, and both
        are told `interrupted`, with what they had committed."""
        key = (run_id, epoch)
        with self._lock:
            waiting = next((j for j in self._waiting if (j.run_id, j.epoch) == key), None)
            if waiting is not None:
                self._waiting.remove(waiting)
                self._say(key, Status.INTERRUPTED)
            elif key in self._running:
                self._cancelled.add(key)
                self._end(self._running[key])
                self._reap()
            else:
                raise NotFound(f"epoch {epoch} of run {run_id} is neither waiting nor executed")
        return stored_run(self._objects, run_id, epoch)

    def close(self) -> None:
        """Ends every worker and takes every epoch waiting out of the queue,
        each told `interrupted`; starts none after."""
        self._closed.set()
        with self._lock:
            while self._waiting:
                job = self._waiting.popleft()
                self._say((job.run_id, job.epoch), Status.INTERRUPTED)
            self._cancelled.update(self._running)
            for process in self._running.values():
                process.terminate()
            for process in self._running.values():
                self._end(process)
            self._reap()
        self._watcher.join(END_WITHIN_S)

    def _watch(self) -> None:
        while not self._closed.wait(LOOK_EVERY_S):
            try:
                with self._lock:
                    self._reap()
                    self._launch()
            except Exception:
                # Whatever a look found wrong, the next finds the workers still.
                logger.exception("the workers' scheduler could not look at them")

    def _launch(self) -> None:
        """Under the lock: a worker for each epoch waiting while there is room."""
        while self._waiting and len(self._running) < self._limit:
            job = self._waiting.popleft()
            process = self._context.Process(
                target=work,
                args=(str(self._root), job.run_id, job.epoch, job.driver, self._made_by),
                kwargs={"resuming": job.resuming},
                name=f"worker of {job.run_id}",
                daemon=True,
            )
            try:
                process.start()
            except Exception:
                # The machine's limit of processes, say: this epoch is told,
                # and the ones behind it are given workers as there is room.
                logger.exception("no worker could be started for %s", job.run_id)
                self._say((job.run_id, job.epoch), Status.FAILED)
                continue
            self._running[(job.run_id, job.epoch)] = process
            if job.resuming:
                self._resuming.add((job.run_id, job.epoch))

    def _reap(self) -> None:
        """Under the lock: says how each epoch ended whose worker has."""
        for key, process in list(self._running.items()):
            if process.exitcode is None:
                continue
            process.join()
            del self._running[key]
            self._ended(
                key,
                process.exitcode,
                cancelled=key in self._cancelled,
                resuming=key in self._resuming,
            )
            self._cancelled.discard(key)
            self._resuming.discard(key)

    def _ended(
        self, key: tuple[str, int], exit_code: int, *, cancelled: bool, resuming: bool
    ) -> None:
        """An epoch whose worker has ended: left as it says if it ended
        itself; else interrupted, if it had begun, was cancelled or was being
        carried on, failed if its worker never began it."""
        status = EpochStore(self._objects, *key).manifest().status
        if status in (Status.FINISHED, Status.FAILED, Status.INTERRUPTED):
            return
        if cancelled or status == Status.RUNNING or resuming:
            # An epoch asked to be carried on, whose worker ended before it
            # took it up, is as interrupted as it was, with or without a
            # commit.
            self._say(key, Status.INTERRUPTED)
            return
        logger.error("the worker of %s ended with %s before it began", key, exit_code)
        self._say(key, Status.FAILED)

    def _say(self, key: tuple[str, int], status: Status) -> None:
        EpochStore(self._objects, *key).set_status(status)

    def _end(self, process: SpawnProcess) -> None:
        """Ends a worker: told to, and killed if it does not within the time."""
        process.terminate()
        process.join(END_WITHIN_S)
        if process.is_alive():
            process.kill()
            process.join()


def of(simulator: Simulator) -> Scheduler:
    """A simulator's scheduler, made when the first run is asked for: the
    simulator must keep its runs in a folder, which a worker's process
    reaches by its path."""
    with simulator.scheduling:
        if simulator.scheduling_closed:
            raise Conflict("the simulator is closed")
        if simulator.scheduler is None:
            if simulator.runs is None:
                raise NotFound("this simulator keeps no runs: it was made with no run store")
            if not isinstance(simulator.runs, FolderStore):
                raise Conflict("workers need the run store in a folder")
            simulator.scheduler = Scheduler(simulator, simulator.runs.root, limit=simulator.workers)
        return simulator.scheduler


def start(
    simulator: Simulator,
    scenario_id: str,
    *,
    layout: str | None = None,
    seed: int | None = None,
    seconds_per_day: float | None = None,
) -> StoredRun:
    """A run of a scenario asked for: freely, or at `seconds_per_day`."""
    driver = None if seconds_per_day is None else Paced(seconds_per_day)
    return of(simulator).start(scenario_id, layout=layout, seed=seed, driver=driver)


def resume(
    simulator: Simulator, run_id: str, epoch: int, *, seconds_per_day: float | None = None
) -> StoredRun:
    """An interrupted epoch asked to be carried on (`Scheduler.resume`)."""
    driver = None if seconds_per_day is None else Paced(seconds_per_day)
    return of(simulator).resume(run_id, epoch, driver=driver)


def cancel(simulator: Simulator, run_id: str, epoch: int) -> StoredRun:
    """An epoch the simulator's workers run or hold, ended."""
    return of(simulator).cancel(run_id, epoch)
