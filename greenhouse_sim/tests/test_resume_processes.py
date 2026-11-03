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
from typing import Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
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
SECONDS_PER_DAY: Final = 8

# Each test starts processes, which import the simulator: tens of seconds.
pytestmark = pytest.mark.slow


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


@pytest.fixture
def simulator(tmp_path: Path) -> Iterator[Simulator]:
    with workers_support.short_simulator() as made:
        made.runs = FolderStore(tmp_path / "runs")
        made.scheduler = Scheduler(
            made, tmp_path / "runs", limit=2, made_by=workers_support.MADE_BY
        )
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
    # The worker that died holds no lease any more: the scheduler told the epoch.
    assert not epoch.worked()

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


def test_an_epoch_whose_resuming_worker_ends_before_taking_it_up_is_still_interrupted(
    simulator: Simulator, tmp_path: Path
) -> None:
    assert simulator.runs is not None
    kept = queued(simulator, simulator.runs, SHORT)
    assert execute(simulator, kept, Stepped([DAY_S])) == Status.INTERRUPTED
    # A worker that cannot build its simulator ends at once, having taken up
    # nothing.
    assert simulator.scheduler is not None
    simulator.scheduler.close()
    simulator.scheduler = Scheduler(
        simulator, tmp_path / "runs", limit=1, made_by="no_such_module:no_such_function"
    )

    resumed = respond(simulator, "POST", f"/api/runs/{kept.run_id}/epochs/{kept.epoch}/resume")

    assert resumed.status == HTTPStatus.OK
    _until(
        lambda: not simulator.scheduler or not simulator.scheduler.workers(),
        "the worker to end",
    )
    _until(lambda: kept.manifest().status != Status.QUEUED, "the epoch to be told")
    assert kept.manifest().status == Status.INTERRUPTED
    assert kept.frontier_s() == DAY_S
