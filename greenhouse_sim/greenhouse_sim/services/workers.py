"""A worker executes one epoch into the run store (P17.7, decision 0065).

`execute(simulator, epoch, driver)` works an epoch out, which has been
started in the store and is `queued`, and writes it there, a span at a time,
one commit each: the store is the only channel between the worker and whoever
reads the epoch. A reader (`stored_playback`) sees as far as the last commit
names, so that an epoch can be played over what is computed while it goes on.

The driver decides how the epoch advances:

- `Free`: as fast as it can be computed, a day at a time;
- `Paced`: by a clock at so many real seconds a simulated day, for a
  consumer on the wall clock; a day is written once the clock has passed it;
- `Stepped`: to the moments an experiment gives, in turn (decision 0061); it
  is in the caller's process, since the barriers come from the caller.

The epoch ends `finished`, `failed` or `interrupted`, as a played run's does.

An epoch `interrupted` can be carried on (`resume`, P17.9): the same epoch,
from the checkpoint its last commit names. Runs are deterministic, so the
epoch it ends as is the one that was never interrupted, and the trajectory
digests of the two are equal. It is carried on from the checkpoint and not
from the start because that is what a checkpoint is for (decision 0065), with
the log of changes given to the epoch applied again, each at the moment it was
given (`Playback.resume_at`).

A change asked of the epoch reaches its worker through the store: the worker
looks between its moments (`Playback.take_changes`). So does a stop, from whoever
cannot signal the worker (`EpochStore.ask_to_stop`): it ends as if told to stop.

An epoch is started with what its worker needs (decision 0067): its scenario's
file, if the scenario is not packaged, and its pace. One written before it kept
them is given them when it is asked to go on, if this simulator still knows the
run it is (`scenario_file_of`).
"""

import json
import logging
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.scenarios.layout_files import DEFAULT_LAYOUT
from greenhouse_sim.services import scenario_files
from greenhouse_sim.services.checkpoints import upload_checkpoint
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.playback import (
    DEFAULT_SECONDS_PER_DAY,
    FIRST_EPOCH,
    WAIT_STEP_S,
    Playback,
    PlaybackCommand,
    check_pace,
)
from greenhouse_sim.services.run_store import (
    CHECKPOINT_TYPE,
    ENDED,
    EpochManifest,
    EpochStore,
    ObjectStore,
    Status,
    decompress,
    failure_reason,
)
from greenhouse_sim.services.run_store import epochs as stored_epochs
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import layout_name, scenario
from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Free:
    """Advances as fast as the epoch can be computed."""


@dataclass(frozen=True)
class Paced:
    """Advances by a clock, `seconds_per_day` real seconds to a simulated day."""

    seconds_per_day: float = DEFAULT_SECONDS_PER_DAY

    def __post_init__(self) -> None:
        check_pace(self.seconds_per_day)


@dataclass(frozen=True)
class Stepped:
    """Advances to each moment `barriers` gives, in seconds into the run, in
    turn, each no earlier than the one before; the epoch is interrupted if
    they end before the run does."""

    barriers: Iterable[float]


Driver = Free | Paced | Stepped


def queued(
    simulator: Simulator,
    objects: ObjectStore,
    scenario_id: str,
    *,
    layout: str | None = None,
    seed: int | None = None,
    seconds_per_day: float | None = None,
    queued_at: datetime | None = None,
) -> EpochStore:
    """A new epoch of the run of `scenario_id` at `layout` and `seed`, in
    `objects`, `queued`: the run's next epoch, its manifest written last, with
    all a worker in another process needs to run it, and `queued_at` if a scheduler
    puts it in line. A scenario, a layout or a seed refused starts nothing, as does
    a scenario that cannot be written as a file. Whoever starts epochs of one store
    does it one at a time, so that two are never given a number."""
    config = scenario(simulator.catalogue, scenario_id)
    chosen = layout_name(layout or DEFAULT_LAYOUT)
    _, run_id = air_through_a_run(simulator, RunRequest(scenario_id, layout=chosen, seed=seed))
    started = stored_epochs(objects, run_id)
    scenario_file = scenario_files.carry(simulator.catalogue, objects, scenario_id)
    return EpochStore.create(
        objects,
        EpochManifest(
            run_id=run_id,
            epoch=started[-1] + 1 if started else FIRST_EPOCH,
            scenario_id=scenario_id,
            seed=seed,
            layout=chosen,
            duration_s=config.duration_days * DAY_S,
            created_at=datetime.now(UTC),
            queued_at=queued_at,
            scenario_file=scenario_file,
            seconds_per_day=seconds_per_day,
        ),
    )


def execute(
    simulator: Simulator,
    epoch: EpochStore,
    driver: Driver | None = None,
    *,
    stop: threading.Event | None = None,
) -> Status:
    """Works `epoch` out into its store as `driver` advances it, and says how
    it ended. Told to `stop` between moments, or asked to through the store,
    it ends `interrupted`. An epoch is executed once: one that has begun is
    refused (`resume` carries it on), as is one whose run is not the one its
    manifest names."""
    manifest = epoch.manifest()
    if manifest.status != Status.QUEUED or epoch.commits():
        raise Conflict(f"epoch {epoch.epoch} of {epoch.run_id} has begun: it is {manifest.status}")
    if not epoch.claimed():
        _claim(epoch)
        try:
            # Read again under the claim: what was read may be another's work by now.
            return execute(simulator, epoch, driver, stop=stop)
        finally:
            epoch.let_go()
    return _drive(simulator, epoch, Free() if driver is None else driver, stop, 0.0)


def _claim(epoch: EpochStore) -> None:
    if not epoch.claim():
        raise Conflict(f"epoch {epoch.epoch} of {epoch.run_id} is worked by a process still")


def check_resumable(epoch: EpochStore) -> float:
    """How far the epoch is kept, in seconds, if it can be carried on from
    there; else why it cannot, as a conflict. An epoch is carried on from the
    checkpoint of its last commit, which must be one this build reads, for the
    run its scenario still is. All its commits name must be there: a list counts
    folders and can miss a lost file, and an epoch carried on past one would stay
    one that cannot be read whole, its days worked out for nothing."""
    status = epoch.manifest().status
    if status not in (Status.INTERRUPTED, Status.QUEUED):
        raise Conflict(
            f"epoch {epoch.epoch} of {epoch.run_id} is {status}: only an interrupted one resumes"
        )
    if epoch.worked() and not epoch.claimed():
        raise Conflict(f"epoch {epoch.epoch} of {epoch.run_id} is worked by a process still")
    commits = epoch.commits()
    if epoch.damaged(commits):
        raise Conflict(
            f"files of run {epoch.run_id}, epoch {epoch.epoch} are missing: it cannot be "
            "carried on, and its run is to be asked for again as a new epoch"
        )
    if not commits:
        return epoch.start_s()
    last = commits[-1]
    if last.checkpoint is None or last.checkpoint_type != CHECKPOINT_TYPE:
        raise Conflict(
            f"epoch {epoch.epoch} of {epoch.run_id} keeps no checkpoint at its frontier, "
            "from which to carry it on"
        )
    return last.end_s


def scenario_file_of(simulator: Simulator, epoch: EpochStore) -> str | None:
    """The scenario file a worker of this epoch is to read: the one it names,
    which must be there and read as the run the epoch is, or none if its scenario
    is packaged. An epoch started before epochs named one is given it now if this
    simulator knows its scenario as the run it is, so that its id never moves;
    else a worker could not run it, and it is refused, saying why."""
    manifest = epoch.manifest()
    which = f"epoch {epoch.epoch} of {epoch.run_id}"
    asked = RunRequest(manifest.scenario_id, layout=manifest.layout, seed=manifest.seed)
    if manifest.scenario_file is not None:
        if epoch.objects.size(scenario_files.kept_name(manifest.scenario_file)) is None:
            raise Conflict(f"{which}: the scenario file it names is gone from the store")
        # As its worker will read it, with nothing else, which would fail on another run.
        with Simulator() as worker:
            scenario_files.take_up(worker, epoch.objects, manifest.scenario_file)
            if air_through_a_run(worker, asked)[1] != manifest.run_id:
                raise Conflict(
                    f"{which}: its scenario's file is now another run, and it cannot be "
                    "carried on: its run is to be asked for again as a new epoch"
                )
        return manifest.scenario_file
    entry = simulator.catalogue.entry(manifest.scenario_id)
    if entry is None:
        raise Conflict(
            f"{which} keeps no file of its scenario {manifest.scenario_id!r}, which this "
            "simulator does not know: upload the scenario's file to carry it on"
        )
    if entry.packaged:
        return None
    if air_through_a_run(simulator, asked)[1] != manifest.run_id:
        raise Conflict(
            f"{which} keeps no file of its scenario {manifest.scenario_id!r}, which this "
            "simulator knows as another run"
        )
    return scenario_files.carry(simulator.catalogue, epoch.objects, manifest.scenario_id)


def resume(
    simulator: Simulator,
    epoch: EpochStore,
    driver: Driver | None = None,
    *,
    stop: threading.Event | None = None,
) -> Status:
    """Carries an `interrupted` epoch on to its end, as `execute` would have
    had it go: from the checkpoint of its last commit, after what a crash left
    past that commit is removed. One with nothing committed begins again. The
    epoch is the same epoch, the same run: its trajectory is the one it would
    have had. A model that keeps no checkpoint at the frontier cannot be
    carried on from it, and the epoch is refused (`check_resumable`), its
    run to be asked for again as a new epoch. A caller's barriers are in the
    caller's process, which is not here to be asked for them again."""
    chosen = Free() if driver is None else driver
    if isinstance(chosen, Stepped):
        raise InvalidRequest("an epoch stepped by a caller is carried on by that caller")
    check_resumable(epoch)
    _claim(epoch)
    try:
        # Read again: until the claim, all that was read may be another's work by now.
        return _carry_on(simulator, epoch, chosen, stop, check_resumable(epoch))
    finally:
        epoch.let_go()


def _carry_on(
    simulator: Simulator,
    epoch: EpochStore,
    driver: Driver,
    stop: threading.Event | None,
    frontier_s: float,
) -> Status:
    """Under the epoch's claim: all of `resume` that writes."""
    removed = epoch.discard_uncommitted()
    if removed:
        logger.warning("%d objects past the last commit of %s removed", len(removed), epoch.run_id)
    if frontier_s:
        # The checkpoint is checked against its commit as it is read.
        data = epoch.checkpoint_at(frontier_s)
        assert data is not None  # check_resumable saw the last commit name one
        end_s = scenario(simulator.catalogue, epoch.manifest().scenario_id).duration_days * DAY_S
        if frontier_s >= end_s:
            # Its last day was committed and the crash came before the epoch
            # was told it finished: nothing is left to work out.
            epoch.set_status(Status.FINISHED)
            return Status.FINISHED
        upload_checkpoint(simulator, json.loads(decompress(data[0])))
    epoch.set_status(Status.QUEUED)
    return _drive(simulator, epoch, driver, stop, frontier_s)


def _drive(
    simulator: Simulator,
    epoch: EpochStore,
    driver: Driver,
    stop: threading.Event | None,
    from_s: float,
) -> Status:
    """Works `epoch`, `queued`, out from `from_s` into its run, which is the
    end of its last commit, and says how it ended."""
    manifest = epoch.manifest()
    stopping = threading.Event() if stop is None else stop
    run = Playback(
        simulator,
        manifest.scenario_id,
        layout=manifest.layout,
        seed=manifest.seed,
        seconds_per_day=driver.seconds_per_day
        if isinstance(driver, Paced)
        else DEFAULT_SECONDS_PER_DAY,
        epoch=epoch,
    )
    if from_s or epoch.logged():
        run.resume_at(from_s)
    epoch.set_status(Status.RUNNING)
    try:
        if isinstance(driver, Paced):
            _paced(run, epoch, stopping)
        else:
            _stepped(
                run,
                epoch,
                _days(run, from_s) if isinstance(driver, Free) else driver.barriers,
                stopping,
            )
    except Exception as error:
        logger.exception("the epoch %s of %s failed", epoch.epoch, epoch.run_id)
        epoch.set_status(Status.FAILED, reason=failure_reason(error))
    status = epoch.manifest().status
    if status == Status.RUNNING:
        status = Status.INTERRUPTED
        epoch.set_status(status)
    return status


def _days(run: Playback, after_s: float = 0.0) -> Iterable[float]:
    """The moments a free epoch is worked out to: the end of each day after
    `after_s`."""
    return (
        min((day + 1) * DAY_S, run.end_s)
        for day in range(round(after_s / DAY_S), round(run.end_s / DAY_S))
    )


def _stepped(
    run: Playback, epoch: EpochStore, barriers: Iterable[float], stopping: threading.Event
) -> None:
    """Works the epoch out to each barrier and writes the days it has passed,
    until the run ends (the epoch is finished by the last day written), the
    barriers do, or it is told to stop."""
    for barrier in barriers:
        if stopping.is_set() or epoch.stop_asked():
            return
        run.take_changes()
        run.step_to(barrier)
        run.keep()
        if epoch.manifest().status in ENDED:
            return


def _paced(run: Playback, epoch: EpochStore, stopping: threading.Event) -> None:
    """Lets the playback's own worker work the epoch out ahead of its clock,
    which plays at the pace, until it ends or it is told to stop."""
    run.begin()
    try:
        run.command(PlaybackCommand.PLAY)
        while not (epoch.manifest().status in ENDED or stopping.is_set() or epoch.stop_asked()):
            run.take_changes()
            stopping.wait(WAIT_STEP_S)
    finally:
        run.stop()
