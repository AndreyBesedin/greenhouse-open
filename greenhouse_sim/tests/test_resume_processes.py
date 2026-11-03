"""A worker killed in the middle of its epoch, and the epoch carried on by
another (P17.9, decision 0065): found interrupted at its last commit, resumed
over the API, and ending as the epoch that was never killed does."""

import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import interrupted, leases, scheduler
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status, StoredRun
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Stepped, execute, queued

# A worker starts from nothing and imports what it is told to build its
# simulator with by name, so that the module is put where its process finds it.
sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
WAIT_S: Final = 240.0
# Slow enough that the first day is committed well before the second.
SECONDS_PER_DAY: Final = 3


@pytest.fixture(autouse=True)
def leases_written_often(monkeypatch: pytest.MonkeyPatch) -> None:
    """So that `workers_support.lease_let_go` does not wait for a lease's thread to
    wake, from this test or the one before it."""
    monkeypatch.setattr(leases, "REFRESH_EVERY_S", workers_support.LEASE_BEAT_S)


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


@pytest.fixture
def simulator(tmp_path: Path) -> Iterator[Simulator]:
    with workers_support.short_simulator() as made:
        made.runs = FolderStore(tmp_path / "runs")
        made.scheduler = Scheduler(made, tmp_path / "runs", limit=2)
        yield made


def _epoch(simulator: Simulator, shown: StoredRun) -> EpochStore:
    assert simulator.runs is not None
    return EpochStore(simulator.runs, shown.run_id, shown.epoch)


def test_a_worker_killed_mid_epoch_is_resumed_over_the_api_and_ends_as_an_epoch_never_killed(
    simulator: Simulator, tmp_path: Path
) -> None:
    with workers_support.short_simulator() as reference:
        whole = queued(reference, FolderStore(tmp_path / "whole"), SHORT)
        assert execute(reference, whole, Free()) == Status.FINISHED

    asked = respond(
        simulator, "POST", f"/api/scenarios/{SHORT}/runs?seconds_per_day={SECONDS_PER_DAY}"
    )
    assert asked.status == HTTPStatus.OK and isinstance(asked.body, dict)
    shown = StoredRun.model_validate(asked.body)
    epoch = _epoch(simulator, shown)
    assert shown.epoch == whole.epoch and shown.run_id == whole.run_id
    _until(lambda: epoch.frontier_s() >= DAY_S, "a day to be committed")

    assert simulator.scheduler is not None
    (worker,) = simulator.scheduler.workers()
    os.kill(worker.pid, signal.SIGKILL)
    _until(lambda: epoch.manifest().status == Status.INTERRUPTED, "the epoch to be told")
    assert epoch.frontier_s() == DAY_S
    # The worker that died holds no lease any more: the scheduler told the epoch,
    # and lets go of the lease just after writing what it told.
    _until(lambda: not epoch.worked(), "the lease to be let go")

    path = f"/api/runs/{shown.run_id}/epochs/{shown.epoch}/resume"
    resumed = respond(simulator, "POST", path)
    assert resumed.status == HTTPStatus.OK
    _until(lambda: epoch.manifest().status == Status.FINISHED, "the epoch to end")

    assert [c.digest for c in epoch.commits()] == [c.digest for c in whole.commits()]
    epoch.verify()
    assert respond(simulator, "POST", path).status == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/runs/no_such_run/epochs/0/resume", HTTPStatus.NOT_FOUND),
        ("/api/runs/{run}/epochs/9/resume", HTTPStatus.NOT_FOUND),
        ("/api/runs/{run}/epochs/0/resume?seconds_per_day=0", HTTPStatus.BAD_REQUEST),
        ("/api/runs/{run}/epochs/0/resume", HTTPStatus.CONFLICT),
    ],
)
def test_an_epoch_asked_to_be_resumed_wrongly_is_refused(
    simulator: Simulator, path: str, status: HTTPStatus
) -> None:
    assert simulator.runs is not None
    # An epoch that finished: not one to resume.
    done = queued(simulator, simulator.runs, SHORT)
    assert execute(simulator, done, Free()) == Status.FINISHED

    answered = respond(simulator, "POST", path.format(run=done.run_id))

    assert answered.status == status
    assert done.manifest().status == Status.FINISHED


def _workers_that_end_at_once(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Scheduler:
    """Workers that each end at once, having taken up nothing."""
    assert simulator.scheduler is not None
    simulator.scheduler.close()
    monkeypatch.setattr(scheduler, "work", workers_support.ends_at_once)
    simulator.scheduler = Scheduler(simulator, tmp_path / "runs", limit=1)
    return simulator.scheduler


def _resume_path(kept: EpochStore) -> str:
    return f"/api/runs/{kept.run_id}/epochs/{kept.epoch}/resume"


@pytest.mark.parametrize("days", [1, 0])
def test_an_epoch_whose_resuming_worker_ends_before_taking_it_up_is_still_interrupted(
    simulator: Simulator, tmp_path: Path, days: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert simulator.runs is not None
    kept = queued(simulator, simulator.runs, SHORT)
    assert execute(simulator, kept, Stepped([DAY_S][:days])) == Status.INTERRUPTED
    assert len(kept.commits()) == days
    workers_support.lease_let_go(kept)
    scheduling = _workers_that_end_at_once(simulator, tmp_path, monkeypatch)

    resumed = respond(simulator, "POST", _resume_path(kept))

    assert resumed.status == HTTPStatus.OK
    _until(lambda: not scheduling.workers(), "the worker to end")
    _until(lambda: kept.manifest().status != Status.QUEUED, "the epoch to be told")
    # Not failed, with a commit or with none: it can be asked for again.
    assert kept.manifest().status == Status.INTERRUPTED
    assert kept.frontier_s() == days * DAY_S
    assert respond(simulator, "POST", _resume_path(kept)).status == HTTPStatus.OK


def test_two_requests_to_resume_an_epoch_are_never_looking_for_its_producer_together(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert simulator.runs is not None
    # The lease of the epoch executed here is written again while its manifest
    # says it is worked: it is let end before the manifest is made to say so.
    kept = queued(simulator, simulator.runs, SHORT)
    assert execute(simulator, kept, Stepped([DAY_S])) == Status.INTERRUPTED
    workers_support.lease_let_go(kept)
    # As a producer that died leaves it: running, and no lease.
    running = kept.manifest().model_copy(update={"status": Status.RUNNING})
    simulator.runs.put(
        f"{kept.run_id}/{kept.epoch}/manifest.json", running.model_dump_json().encode()
    )
    _workers_that_end_at_once(simulator, tmp_path, monkeypatch)
    # Each look for the producer takes a while, and counts who else is looking.
    looking = {"now": 0, "most": 0}
    counting = threading.Lock()
    real = interrupted._worked

    def slowly(*args: Any) -> bool:
        with counting:
            looking["now"] += 1
            looking["most"] = max(looking["most"], looking["now"])
        time.sleep(0.3)
        try:
            return real(*args)
        finally:
            with counting:
                looking["now"] -= 1

    monkeypatch.setattr(interrupted, "_worked", slowly)
    answers = []
    askers = [
        threading.Thread(
            target=lambda: answers.append(respond(simulator, "POST", _resume_path(kept)).status)
        )
        for _ in range(2)
    ]

    for asker in askers:
        asker.start()
    for asker in askers:
        asker.join(WAIT_S)

    # One request at a time looks, under the lock the epoch is queued under, so
    # that the second finds what the first did.
    assert looking["most"] == 1
    assert HTTPStatus.OK in answers
