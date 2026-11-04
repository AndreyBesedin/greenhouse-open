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
from greenhouse_sim.services import interrupted, scheduler
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status, StoredRun
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Stepped, execute, queued

# A worker starts from nothing and imports what it is told to build its
# simulator with by name, so that the module is put where its process finds it.
sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
SHORT_DAYS: Final = workers_support.SHORT_DAYS
WAIT_S: Final = 240.0
# Slow enough that the first day is committed well before the second.
SECONDS_PER_DAY: Final = 3


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


def _reported_days(epoch: EpochStore) -> float:
    usage = epoch.usage()
    return 0.0 if usage is None else usage.days_computed


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
    # A worker writes its report just after its commit: killed between them, what it
    # used is lost, so this waits for the report and not for the commit.
    _until(lambda: _reported_days(epoch) >= 1.0, "a day to be committed and reported")

    assert simulator.scheduler is not None
    (worker,) = simulator.scheduler.workers()
    os.kill(worker.pid, signal.SIGKILL)
    _until(lambda: epoch.manifest().status == Status.INTERRUPTED, "the epoch to be told")
    assert epoch.frontier_s() == DAY_S
    # The worker that died holds no lease any more: the scheduler told the epoch,
    # and lets go of the lease just after writing what it told.
    _until(lambda: not epoch.worked(), "the lease to be let go")
    # Killed outright, it had no chance to say why, and it is not said to have
    # failed. What it reported at its commit stays, for the next worker to add to.
    assert epoch.manifest().reason is None
    killed = epoch.usage()
    assert killed is not None and killed.cpu_s is not None and killed.peak_memory_bytes is not None
    assert killed.cpu_s > 0 and killed.peak_memory_bytes > 0 and killed.days_computed == 1.0

    path = f"/api/runs/{shown.run_id}/epochs/{shown.epoch}/resume"
    resumed = respond(simulator, "POST", path)
    assert resumed.status == HTTPStatus.OK
    _until(lambda: epoch.manifest().status == Status.FINISHED, "the epoch to end")

    assert [c.digest for c in epoch.commits()] == [c.digest for c in whole.commits()]
    epoch.verify()
    assert respond(simulator, "POST", path).status == HTTPStatus.CONFLICT
    carried = epoch.usage()
    assert carried is not None and carried.cpu_s is not None
    assert carried.cpu_s > killed.cpu_s
    assert carried.peak_memory_bytes is not None
    assert carried.peak_memory_bytes >= killed.peak_memory_bytes
    assert carried.days_computed == SHORT_DAYS and carried.commits == SHORT_DAYS


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
    scheduling = _workers_that_end_at_once(simulator, tmp_path, monkeypatch)

    resumed = respond(simulator, "POST", _resume_path(kept))

    assert resumed.status == HTTPStatus.OK
    _until(lambda: not scheduling.workers(), "the worker to end")
    _until(lambda: kept.manifest().status != Status.QUEUED, "the epoch to be told")
    # Not failed, with a commit or with none: it can be asked for again.
    assert kept.manifest().status == Status.INTERRUPTED
    assert kept.frontier_s() == days * DAY_S
    assert respond(simulator, "POST", _resume_path(kept)).status == HTTPStatus.OK


@pytest.mark.parametrize(
    "paces",
    [(20.0, "", 20.0), (20.0, "?seconds_per_day=5", 5.0), (None, "", None)],
)
def test_an_epoch_resumed_with_no_pace_goes_on_at_the_one_it_was_asked_for(
    simulator: Simulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    paces: tuple[float | None, str, float | None],
) -> None:
    asked_at, query, resumed_at = paces
    assert simulator.runs is not None
    kept = queued(simulator, simulator.runs, SHORT, seconds_per_day=asked_at)
    assert execute(simulator, kept, Stepped([DAY_S])) == Status.INTERRUPTED
    # A worker reads its pace from the manifest (`scheduler.work`).
    scheduling = _workers_that_end_at_once(simulator, tmp_path, monkeypatch)

    answered = respond(simulator, "POST", _resume_path(kept) + query)

    assert answered.status == HTTPStatus.OK
    assert kept.manifest().seconds_per_day == resumed_at
    _until(lambda: not scheduling.workers(), "the worker to end")


def test_an_epoch_given_a_free_driver_on_resuming_goes_as_fast_as_it_computes(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert simulator.runs is not None
    kept = queued(simulator, simulator.runs, SHORT, seconds_per_day=20.0)
    assert execute(simulator, kept, Stepped([DAY_S])) == Status.INTERRUPTED
    scheduling = _workers_that_end_at_once(simulator, tmp_path, monkeypatch)

    scheduling.resume(kept.run_id, kept.epoch, driver=Free())

    assert kept.manifest().seconds_per_day is None
    _until(lambda: not scheduling.workers(), "the worker to end")


def test_two_requests_to_resume_an_epoch_are_never_looking_for_its_producer_together(
    simulator: Simulator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert simulator.runs is not None
    kept = queued(simulator, simulator.runs, SHORT)
    assert execute(simulator, kept, Stepped([DAY_S])) == Status.INTERRUPTED
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
