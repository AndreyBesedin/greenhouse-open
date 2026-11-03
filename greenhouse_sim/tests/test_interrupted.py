"""Epochs that no one works are found (P17.9, decision 0065): at startup and
when asked, an epoch the store calls `running` that holds no lease, nor sits in
this simulator's queue, is told `interrupted`; one that is worked is left."""

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from greenhouse_sim.services import interrupted, leases
from greenhouse_sim.services.run_store import EpochManifest, EpochStore, FolderStore, Status
from greenhouse_sim.services.scheduler import Worker
from greenhouse_sim.services.simulator import Simulator

LONG_AGO = timedelta(seconds=leases.EXPIRES_AFTER_S * 10)


def _epoch(
    objects: FolderStore, status: Status, *, number: int = 0, age: timedelta = LONG_AGO
) -> EpochStore:
    """An epoch as a producer that died leaves it: told `status`, with no lease."""
    return EpochStore.create(
        objects,
        EpochManifest(
            run_id="run",
            epoch=number,
            scenario_id="s",
            layout="default",
            status=status,
            created_at=datetime.now(UTC) - age,
        ),
    )


def test_epochs_no_one_works_are_told_interrupted_as_a_simulator_starts(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    running = _epoch(objects, Status.RUNNING)
    queued = _epoch(objects, Status.QUEUED, number=1)
    done = _epoch(objects, Status.FINISHED, number=2)

    with Simulator(runs=objects) as simulator:
        assert running.manifest().status == Status.INTERRUPTED
        assert queued.manifest().status == Status.INTERRUPTED
        assert done.manifest().status == Status.FINISHED
        assert interrupted.mark(simulator) == []


def test_a_running_epoch_whose_lease_is_written_is_left(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    running = _epoch(objects, Status.RUNNING)
    leases.hold(objects, "run/0")
    try:
        with Simulator(runs=objects):
            assert running.manifest().status == Status.RUNNING
    finally:
        leases.release(objects, "run/0")


def test_a_lease_that_has_expired_is_not_a_worker(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    running = _epoch(objects, Status.RUNNING)
    leases.hold(objects, "run/0")
    try:
        with Simulator(runs=objects) as simulator:
            later = time.time() + leases.EXPIRES_AFTER_S * 2
            (found,) = interrupted.mark(simulator, now=later)
            assert (found.run_id, found.epoch, found.status) == ("run", 0, Status.INTERRUPTED)
            assert running.manifest().status == Status.INTERRUPTED
    finally:
        leases.release(objects, "run/0")


def test_an_epoch_just_asked_for_is_given_time_to_be_taken_up(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    fresh = _epoch(objects, Status.QUEUED, age=timedelta(seconds=1))

    with Simulator(runs=objects):
        assert fresh.manifest().status == Status.QUEUED


def test_an_epoch_in_the_schedulers_queue_or_with_a_worker_is_left(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with Simulator(runs=objects) as simulator:
        waiting = _epoch(objects, Status.QUEUED)
        working = _epoch(objects, Status.RUNNING, number=1)
        simulator.scheduler = SimpleNamespace(  # type: ignore[assignment]
            waiting=lambda: [("run", 0)], workers=lambda: [Worker("run", 1, 1)]
        )
        try:
            assert interrupted.mark(simulator) == []
            assert waiting.manifest().status == Status.QUEUED
            assert working.manifest().status == Status.RUNNING
        finally:
            simulator.scheduler = None


def test_a_simulator_with_no_run_store_finds_nothing() -> None:
    with Simulator() as simulator:
        assert interrupted.mark(simulator) == []
        assert interrupted.mark_epoch(simulator, "run", 0) is None
