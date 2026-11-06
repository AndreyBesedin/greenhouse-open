"""Many epochs at once (P17.7, decision 0065): a scheduler runs workers, each
in a process of its own, up to a number, and queues the rest.

A run asked for is an epoch started in the run store, `queued`, and a worker
takes it when there is room: a process given a store's address and an epoch and
nothing else (decision 0067), which builds its own simulator from what the
epoch carries, works the epoch out into the store (`workers.resume`, the same
for one begun and one not) and ends. Several runs of one scenario, at different
seeds as when policies are trained, are several epochs, each a process. The
store is the only channel between a worker and the API, so that whoever reads an
epoch reads it while it is computed, as far as the last commit names
(`stored_playback`).

The queue outlives the process, so that one a scheduler put in line is not among
those: what waits is what the store says waits, with all its worker needs (decision
0067), and `restore` makes the queue again from those manifests, in their order, as a
simulator starts. A worker claims its epoch before it does anything (`leases`), so
that this needs no agreement with whoever else may be looking: of two workers given
one epoch, as when a server starts while one it replaced is still starting a worker,
one takes it and the other leaves.

A process is the worker because P17.1 measured what a thread costs a process
that is working: 46% of its speed against 5% for another process. It runs at a lower
priority than the API (decision 0067), so that a viewer stays responsive beside it.

A run asked for may be refused, saying why, for what the simulator's `limits` allow:
too many waiting, too little disk free, or too much in the store. So may a resume or a
fork, which ask for a worker in the same way. What waits already keeps waiting if the
limits have been lowered since, under them as they are now. `room` says, before any is
asked for, the workers busy, the runs waiting and the disk free beside their limits, and
the refusal a run asked for then would be given.

A worker keeps to the budget of its epoch, which the limits give as it is put in line
(`workers.keep_within_budget`). Past one, it says the epoch failed and why and ends, and
the epoch can be carried on as one interrupted can, if the limit was raised meanwhile.

An epoch whose worker ends without ending it, killed or lost, is told
`interrupted` with what it had committed, and can be asked for again to be
carried on from there (`resume`, P17.9): queued once more, taken by a worker
that resumes it. An epoch still `queued` or `running` when the producer that
started it is gone is found at startup (`interrupted.mark`).

A worker this scheduler started is stopped by a signal, and is gone when the
answer is given. One it did not start, such as a worker left computing by a
server that was killed, is out of reach of any signal and may be on another
machine: it is asked through the store, and stops at its next look. An epoch a
playback of this simulator plays has no worker: its playback is stopped
(`cancel`), and it ends as if it had one.
"""

import logging
import multiprocessing
import threading
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.services import forks, interrupted, scenario_files
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound
from greenhouse_sim.services.interventions import Asked
from greenhouse_sim.services.limits import (
    Budget,
    Limits,
    store_too_large,
    too_little_disk,
    too_many_waiting,
)
from greenhouse_sim.services.playback import stop_epoch
from greenhouse_sim.services.resources import lower_priority, this_process
from greenhouse_sim.services.run_store import (
    ENDED,
    EpochStore,
    FolderStore,
    Status,
    StoredRun,
    held_bytes,
    stored_run,
)
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import (
    Driver,
    Free,
    Paced,
    check_resumable,
    keep_within_budget,
    queued,
    scenario_file_of,
)
from greenhouse_sim.services.workers import resume as carry_on

logger = logging.getLogger(__name__)

# How often the scheduler looks at its workers.
LOOK_EVERY_S: Final = 0.1
# How long a worker told to end has before it is killed.
END_WITHIN_S: Final = 10.0
# What a worker exits with that found its epoch another's, or no longer waiting:
# it has done nothing to it, and nothing is to be said of it.
LEFT_TO_ANOTHER: Final = 3
# What a manifest a scheduler put in line says while it has not ended.
_IN_LINE: Final = (Status.QUEUED, Status.RUNNING)


def work(root: str, run_id: str, epoch: int) -> None:
    """A worker's process: works out the epoch `epoch` of the run `run_id` in
    the store under `root`, from all that the store holds of it, and exits with
    0 if the epoch finished. Only a process started for it gives way to the machine's
    other work: a caller that runs this itself is not lowered for good by doing so."""
    if multiprocessing.parent_process() is not None:
        lower_priority()
    kept = EpochStore(FolderStore(Path(root)), run_id, epoch)
    kept.counted_by(this_process)
    manifest = kept.manifest()
    pace = manifest.seconds_per_day
    if not _taken_up(kept):
        raise SystemExit(LEFT_TO_ANOTHER)
    keep_within_budget(kept)
    with Simulator() as simulator:
        if manifest.scenario_file is not None:
            scenario_files.take_up(simulator, kept.objects, manifest.scenario_file)
        status = carry_on(simulator, kept, Free() if pace is None else Paced(pace))
    raise SystemExit(0 if status == Status.FINISHED else 1)


def _taken_up(kept: EpochStore) -> bool:
    """Whether this worker has the epoch, which waited for it: claimed, and read
    after that. An epoch told otherwise while the worker started is left."""
    if not kept.claim():
        return False
    if kept.manifest().status == Status.QUEUED:
        return True
    kept.let_go()
    return False


def _pace(driver: Driver | None) -> float | None:
    """The pace an epoch's manifest gives its worker. A stepped driver takes its
    moments from its caller's process, which a worker is not."""
    if driver is None or isinstance(driver, Free):
        return None
    if isinstance(driver, Paced):
        return driver.seconds_per_day
    raise InvalidRequest("a worker advances its epoch freely or at a pace")


@dataclass(frozen=True)
class Worker:
    """An epoch being executed, and the process that executes it."""

    run_id: str
    epoch: int
    pid: int


class Room(BaseModel):
    """What a simulator has room for as a run is asked for (decision 0067): its
    workers busy and the runs waiting for one, each beside its limit, and what is
    free on the run store's disk beside the floor a run begins above. A limit of
    none is no limit, and a store that cannot say what is free says none.
    `refusal` is what a run, a resume or a fork asked for now would be refused
    with, in the words of that refusal, or none if it would be let in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workers_busy: int
    workers_limit: int
    runs_waiting: int
    runs_waiting_limit: int | None
    disk_free_bytes: int | None
    disk_free_limit_bytes: int | None
    refusal: str | None


def _room_of(
    limits: Limits, objects: FolderStore, *, busy: int, waiting: int, workers: int
) -> Room:
    """The room there is, with `busy` workers of `workers` and `waiting` runs in
    line, and the refusal a run asked for now would be given, the first limit
    that has no room for it."""
    free_workers = max(0, workers - busy)
    free = objects.free_bytes()
    refusal = None
    if limits.waiting_runs is not None and waiting - free_workers >= limits.waiting_runs:
        refusal = too_many_waiting(waiting, limits.waiting_runs)
    elif limits.free_disk_bytes is not None and free is not None and free < limits.free_disk_bytes:
        refusal = too_little_disk(free, limits.free_disk_bytes)
    elif limits.store_bytes is not None:
        held = held_bytes(objects)
        if held >= limits.store_bytes:
            refusal = store_too_large(held, limits.store_bytes)
    return Room(
        workers_busy=busy,
        workers_limit=workers,
        runs_waiting=waiting,
        runs_waiting_limit=limits.waiting_runs,
        disk_free_bytes=free,
        disk_free_limit_bytes=limits.free_disk_bytes,
        refusal=refusal,
    )


@dataclass(frozen=True)
class _Job:
    run_id: str
    epoch: int
    resuming: bool = False


class Scheduler:
    """The workers of a simulator whose run store is a folder: at most `limit`
    at once, the rest waiting in the order they were asked for."""

    def __init__(self, simulator: Simulator, root: Path, *, limit: int) -> None:
        if limit < 1:
            raise ValueError(f"a scheduler runs one worker at least, not {limit}")
        self._simulator = simulator
        self._root = root
        self._objects = FolderStore(root)
        self._limit = limit
        # A worker is a process started from nothing, not a copy of this one
        # with its threads and locks.
        self._context = multiprocessing.get_context("spawn")
        # Re-entrant: finding an epoch no one works asks the scheduler what it
        # holds, and is done under the lock a resume is scheduled under.
        self._lock = threading.RLock()
        self._waiting: deque[_Job] = deque()
        self._running: dict[tuple[str, int], SpawnProcess] = {}
        self._cancelled: set[tuple[str, int]] = set()
        # Epochs a worker this scheduler did not start has: one a server before this
        # left computing, which counts against the limit as long as it is believed.
        self._elsewhere: set[tuple[str, int]] = set()
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
        takes the epoch as fast as it can go, or at a pace."""
        pace = _pace(driver)
        with self._lock:
            if self._closed.is_set():
                raise Conflict("the workers are closed")
            self._check_room()
            epoch = queued(
                self._simulator,
                self._objects,
                scenario_id,
                layout=layout,
                seed=seed,
                seconds_per_day=pace,
                queued_at=datetime.now(UTC),
            )
            epoch.give_budget(self._simulator.limits.budget)
            self._waiting.append(_Job(epoch.run_id, epoch.epoch))
            self._launch()
            return stored_run(self._objects, epoch.run_id, epoch.epoch)

    def resume(self, run_id: str, epoch: int, *, driver: Driver | None = None) -> StoredRun:
        """Asks for an `interrupted` epoch to be carried on from its last
        commit: queued once more, and taken by a worker that resumes it when
        there is room. An epoch the store still calls `running` whose producer
        is gone is found interrupted first, under the lock the epoch is queued
        under, so that two requests for it are told apart: the second finds
        the epoch queued. With no driver it goes on at the pace it was asked
        for, which its manifest holds. Refused, as `workers.check_resumable` and
        `workers.scenario_file_of` say, if it cannot be; the store is not
        changed by a refusal."""
        asked_pace = _pace(driver)
        key = (run_id, epoch)
        if epoch not in stored_epochs(self._objects, run_id):
            raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
        kept = EpochStore(self._objects, run_id, epoch)
        with self._lock:
            if self._closed.is_set():
                raise Conflict("the workers are closed")
            if key in self._running or any((j.run_id, j.epoch) == key for j in self._waiting):
                raise Conflict(f"epoch {epoch} of {run_id} is waiting for a worker or has one")
            # First: all that follows may write, finding the epoch interrupted or
            # giving it its scenario's file, which no refusal for room is to do.
            self._check_room()
            interrupted.mark_epoch(self._simulator, run_id, epoch)
            if not kept.manifest().carries_on:
                raise Conflict(
                    f"epoch {epoch} of {run_id} is {kept.manifest().status}: "
                    "only an interrupted one resumes"
                )
            check_resumable(kept)
            budget = self._simulator.limits.budget
            _check_within(kept, budget)
            # Last, since it may give an epoch from before P18.1 its scenario's file.
            scenario_file = scenario_file_of(self._simulator, kept)
            pace = kept.manifest().seconds_per_day if driver is None else asked_pace
            kept.give_budget(budget)
            kept.queue_again(scenario_file=scenario_file, seconds_per_day=pace)
            self._waiting.append(_Job(run_id, epoch, resuming=True))
            self._launch()
        return stored_run(self._objects, run_id, epoch)

    def fork(
        self,
        run_id: str,
        epoch: int,
        at_s: float,
        *,
        layout: str | None = None,
        changes: Sequence[Asked] = (),
        driver: Driver | None = None,
    ) -> StoredRun:
        """Asks for a fork of an epoch at `at_s` (`forks.fork`): a new epoch,
        taken by a worker when there is room, which carries it on from the
        state it inherits as it carries on an epoch interrupted."""
        pace = _pace(driver)
        with self._lock:
            if self._closed.is_set():
                raise Conflict("the workers are closed")
            self._check_room()
            made = forks.fork(
                self._simulator,
                self._objects,
                run_id,
                epoch,
                at_s,
                layout=layout,
                changes=changes,
                seconds_per_day=pace,
                queued_at=datetime.now(UTC),
            )
            made.give_budget(self._simulator.limits.budget)
            self._waiting.append(_Job(made.run_id, made.epoch, resuming=True))
            self._launch()
            return stored_run(self._objects, made.run_id, made.epoch)

    def _check_room(self) -> None:
        """Under the lock: refuses a run the simulator's limits have no room for,
        before anything of it is written, saying which limit and the figures."""
        refused = self._room().refusal
        if refused is not None:
            raise Conflict(refused)

    def room(self) -> Room:
        """What a run asked for now has room for (`Room`)."""
        with self._lock:
            return self._room()

    def _room(self) -> Room:
        """Under the lock: the room there is, and why a run asked for now would be
        refused, if it would. A run that a free worker takes at once does not wait,
        so is not refused for that. A server's limit may be lower than the workers a
        server before it left, and those are not runs waiting."""
        return _room_of(
            self._simulator.limits,
            self._objects,
            busy=len(self._running) + len(self._elsewhere),
            waiting=len(self._waiting),
            workers=self._limit,
        )

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

    def take_up(self, left: Iterable[EpochStore]) -> None:
        """The epochs in line in the store as this scheduler begins (`restore`): one
        with a worker still is counted against the limit, one that waits is put in
        the queue in its place, and one whose worker could not run it is told
        `interrupted`, for whoever asks to carry it on to be told why."""
        with self._lock:
            for kept in sorted(left, key=_place_in_line):
                if kept.worked():
                    self._elsewhere.add((kept.run_id, kept.epoch))
                elif kept.manifest().status == Status.QUEUED:
                    self._wait_again(kept)
            self._launch()

    def _wait_again(self, kept: EpochStore) -> None:
        try:
            scenario_file_of(self._simulator, kept)
        except Conflict as refused:
            logger.warning("%s: it waits no longer", refused.message)
            kept.end_unless_worked(Status.INTERRUPTED)
            return
        manifest = kept.manifest()
        if kept.budget() != self._simulator.limits.budget:
            kept.give_budget(self._simulator.limits.budget)
        resuming = manifest.resumed or manifest.fork is not None or bool(kept.commits())
        self._waiting.append(_Job(kept.run_id, kept.epoch, resuming=resuming))

    def cancel(self, run_id: str, epoch: int) -> StoredRun:
        """Ends an epoch: one waiting here is taken out of the queue and one
        being executed here has its worker ended, both told `interrupted` with
        what they had committed. Any other is left to `_stop_elsewhere`, and may
        be on its way when this answers, as the epoch answered says: so is one
        waiting here that another server's worker has taken up, or that has ended
        there, since a queue made from the store is not the only one that may."""
        key = (run_id, epoch)
        with self._lock:
            waiting = next((j for j in self._waiting if (j.run_id, j.epoch) == key), None)
            if waiting is not None:
                self._waiting.remove(waiting)
                kept = EpochStore(self._objects, run_id, epoch)
                if self._status(key) != Status.QUEUED or not kept.end_unless_worked(
                    Status.INTERRUPTED
                ):
                    self._stop_elsewhere(run_id, epoch)
            elif key in self._running:
                self._cancelled.add(key)
                self._end(self._running[key])
                self._reap()
            else:
                self._stop_elsewhere(run_id, epoch)
        return stored_run(self._objects, run_id, epoch)

    def _stop_elsewhere(self, run_id: str, epoch: int) -> None:
        """Under the lock: an epoch no worker of this scheduler has. One no one
        works is told `interrupted` now. One whose worker may live is asked to
        stop through the store, which is all there is between them, and is told
        `interrupted` if that worker dies before it looks."""
        if epoch not in stored_epochs(self._objects, run_id):
            raise NotFound(f"run {run_id} has no epoch {epoch} in the store")
        kept = EpochStore(self._objects, run_id, epoch)
        status = kept.manifest().status
        if status in ENDED:
            raise Conflict(f"epoch {epoch} of {run_id} is {status}: it is not being computed")
        if interrupted.mark_epoch(self._simulator, run_id, epoch) is None:
            kept.ask_to_stop()
            interrupted.watch_epoch(self._simulator, run_id, epoch)

    def close(self) -> None:
        """Ends every worker, each epoch told `interrupted`, and starts none after.
        An epoch waiting is left so in the store, for the next scheduler to take up."""
        self._closed.set()
        with self._lock:
            self._waiting.clear()
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
        """Under the lock: a worker for each epoch waiting while there is room. One
        the store no longer has waiting, told otherwise or deleted by another
        process, is passed over, and one another server's worker has begun is counted
        as that worker's until it is told."""
        self._look_elsewhere()
        while self._waiting and len(self._running) + len(self._elsewhere) < self._limit:
            job = self._waiting.popleft()
            key = (job.run_id, job.epoch)
            status = self._status(key)
            if status == Status.RUNNING:
                self._elsewhere.add(key)
            if status != Status.QUEUED:
                continue
            process = self._context.Process(
                target=work,
                args=(str(self._root), job.run_id, job.epoch),
                name=f"worker of {job.run_id}",
                daemon=True,
            )
            try:
                process.start()
            except Exception:
                # The machine's limit of processes, say: this epoch is told,
                # and the ones behind it are given workers as there is room.
                logger.exception("no worker could be started for %s", job.run_id)
                self._say(key, Status.FAILED, reason="no worker could be started")
                continue
            self._running[key] = process
            if job.resuming:
                self._resuming.add(key)

    def _look_elsewhere(self) -> None:
        """Under the lock: an epoch worked elsewhere whose claim is no longer believed
        is told so if it had not ended, and leaves room."""
        for key in list(self._elsewhere):
            if not EpochStore(self._objects, *key).worked():
                self._elsewhere.discard(key)
                interrupted.mark_epoch(self._simulator, *key)

    def _status(self, key: tuple[str, int]) -> Status | None:
        """What the store says of an epoch, if it has it still."""
        if key[1] not in stored_epochs(self._objects, key[0]):
            return None
        return EpochStore(self._objects, *key).manifest().status

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
        if exit_code == LEFT_TO_ANOTHER:
            self._elsewhere.add(key)
            return
        status = self._status(key)
        if status is None or status in (Status.FINISHED, Status.FAILED, Status.INTERRUPTED):
            return
        if cancelled or status == Status.RUNNING or resuming:
            # An epoch asked to be carried on, whose worker ended before it
            # took it up, is as interrupted as it was, with or without a
            # commit.
            self._say(key, Status.INTERRUPTED)
            return
        logger.error("the worker of %s ended with %s before it began", key, exit_code)
        self._say(key, Status.FAILED, reason=f"its worker ended with {exit_code} before it began")

    def _say(self, key: tuple[str, int], status: Status, *, reason: str | None = None) -> None:
        EpochStore(self._objects, *key).set_status(status, reason=reason)

    def _end(self, process: SpawnProcess) -> None:
        """Ends a worker: told to, and killed if it does not within the time."""
        process.terminate()
        process.join(END_WITHIN_S)
        if process.is_alive():
            process.kill()
            process.join()


def _check_within(kept: EpochStore, budget: Budget) -> None:
    """Refuses to carry on an epoch that would end again at once, for what it has
    already: its bytes and its time, which do not come back. A worker's memory is its
    own, and the next may hold less."""
    usage = kept.usage()
    if usage is None:
        return
    reason = budget.bytes_past(usage.bytes_kept) or budget.time_past(
        cpu_s=usage.cpu_s, wall_s=usage.wall_s
    )
    if reason is not None:
        raise Conflict(f"epoch {kept.epoch} of {kept.run_id}: {reason}")


def _place_in_line(kept: EpochStore) -> tuple[datetime, str, int]:
    queued_at = kept.manifest().queued_at
    assert queued_at is not None  # all that `restore` gives
    return queued_at, kept.run_id, kept.epoch


def restore(simulator: Simulator) -> None:
    """Gives a simulator starting on a folder the queue its store says it has: every
    epoch a scheduler put in line that has not ended (`Scheduler.take_up`), for which
    a scheduler is made. An epoch no scheduler put in line says nothing of who was to
    take it up, as one kept from before this does, or one a process of its own was to
    work: `interrupted` finds it."""
    objects = simulator.runs
    if not isinstance(objects, FolderStore):
        return
    left = []
    for run_id in objects.children():
        for number in stored_epochs(objects, run_id):
            kept = EpochStore(objects, run_id, number)
            manifest = kept.manifest()
            if manifest.queued_at is not None and manifest.status in _IN_LINE:
                left.append(kept)
    if left:
        of(simulator).take_up(left)


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
            simulator.scheduler = Scheduler(
                simulator, simulator.runs.root, limit=simulator.limits.workers
            )
        return simulator.scheduler


def room(simulator: Simulator) -> Room:
    """What a run asked of a simulator now has room for (`Room`): from its
    scheduler, or, before one is made, with no worker busy and none waiting.
    Refused as a run is if the simulator keeps no runs, or not in a folder."""
    if simulator.runs is None:
        raise NotFound("this simulator keeps no runs: it was made with no run store")
    if not isinstance(simulator.runs, FolderStore):
        raise Conflict("workers need the run store in a folder")
    with simulator.scheduling:
        made = simulator.scheduler
    if made is not None:
        return made.room()
    limits = simulator.limits
    return _room_of(limits, simulator.runs, busy=0, waiting=0, workers=limits.workers)


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
    """An interrupted epoch asked to be carried on (`Scheduler.resume`): at
    `seconds_per_day`, or at the pace it was asked for."""
    driver = None if seconds_per_day is None else Paced(seconds_per_day)
    return of(simulator).resume(run_id, epoch, driver=driver)


def fork(
    simulator: Simulator,
    run_id: str,
    epoch: int,
    at_s: float,
    *,
    layout: str | None = None,
    changes: Sequence[Asked] = (),
    seconds_per_day: float | None = None,
) -> StoredRun:
    """A fork of a stored epoch asked for (`Scheduler.fork`)."""
    driver = None if seconds_per_day is None else Paced(seconds_per_day)
    return of(simulator).fork(run_id, epoch, at_s, layout=layout, changes=changes, driver=driver)


def cancel(simulator: Simulator, run_id: str, epoch: int) -> StoredRun:
    """An epoch ended, or asked to end: by stopping the playback that has it, which
    needs no scheduler, on a store of any kind (`playback.stop_epoch`), or else by
    its scheduler (`Scheduler.cancel`)."""
    stopped = stop_epoch(simulator, run_id, epoch)
    return of(simulator).cancel(run_id, epoch) if stopped is None else stopped
