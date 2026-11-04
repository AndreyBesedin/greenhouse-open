"""A run waiting survives a restart (P18.4, decision 0067): the queue is made again
from the manifests a scheduler put in line, in their order, each run once, within
the limit on workers, and each with all its worker needs from the store."""

import contextlib
import json
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import leases, scenario_files, scheduler
from greenhouse_sim.services.errors import Conflict, NotFound
from greenhouse_sim.services.run_store import EpochStore, FolderStore, Status, delete_epoch
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Paced, Stepped, execute, queued

# A worker starts from nothing and imports what it is told to run by name.
sys.path.insert(0, str(Path(__file__).parent))

import claims_support
import workers_support

SHORT: Final = workers_support.SHORT
PACKAGED: Final = "climate_box"
WAIT_S: Final = 120.0
PACE: Final = 0.5
IN_LINE_AT: Final = datetime(2026, 1, 1, tzinfo=UTC)
SPAWN: Final = multiprocessing.get_context("spawn")


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.02)


def _in_line(
    objects: FolderStore, seeds: list[int], *, pace: float | None = None
) -> list[EpochStore]:
    """Epochs a scheduler put in line in the order of `seeds`, as a server left them."""
    with workers_support.short_simulator() as made:
        return [
            queued(
                made,
                objects,
                SHORT,
                seed=seed,
                seconds_per_day=pace,
                queued_at=IN_LINE_AT + timedelta(seconds=place),
            )
            for place, seed in enumerate(seeds)
        ]


def _rewritten(epoch: EpochStore, **changes: Any) -> None:
    written = epoch.manifest().model_copy(update=changes).model_dump_json().encode()
    epoch.objects.put(f"{epoch.run_id}/{epoch.epoch}/manifest.json", written)


def _expired(epoch: EpochStore) -> None:
    """What its holder last wrote of the epoch's claim, long ago."""
    number = leases.newest(epoch.objects, f"{epoch.run_id}/{epoch.epoch}")
    old = json.dumps({"refreshed_at": time.time() - 2 * leases.EXPIRES_AFTER_S}).encode()
    epoch.objects.put(f"{epoch.run_id}/{epoch.epoch}/{leases.CLAIMS}/{number:08d}.json", old)


def _key(epoch: EpochStore) -> tuple[str, int]:
    return epoch.run_id, epoch.epoch


@pytest.fixture
def no_worker_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Scheduler, "_launch", lambda _self: None)


@pytest.fixture
def workers_end_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker that ends at once leaves a new epoch `failed`: it was given its turn."""
    monkeypatch.setattr(scheduler, "work", workers_support.ends_at_once)


@pytest.mark.usefixtures("no_worker_starts")
def test_the_queue_comes_back_in_the_order_it_was_in_and_not_by_its_names(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    left = _in_line(objects, [5, 3, 9, 1, 7])
    assert sorted(left, key=_key) != left

    with Simulator(runs=objects) as simulator:
        assert simulator.scheduler is not None
        assert simulator.scheduler.waiting() == [_key(epoch) for epoch in left]


@pytest.mark.usefixtures("no_worker_starts")
def test_a_scheduler_puts_all_it_is_asked_for_in_line_in_that_order(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        made.runs = objects
        begun = queued(made, objects, SHORT, seed=1)
        assert execute(made, begun, Stepped([DAY_S])) == Status.INTERRUPTED
        scheduling = Scheduler(made, tmp_path, limit=1)
        started = scheduling.start(SHORT, seed=2)
        forked = scheduling.fork(begun.run_id, begun.epoch, DAY_S)
        scheduling.resume(begun.run_id, begun.epoch)
        asked = [(r.run_id, r.epoch) for r in (started, forked)] + [_key(begun)]
        assert scheduling.waiting() == asked
        scheduling.close()

    with Simulator(runs=objects) as simulator:
        assert simulator.scheduler is not None
        assert simulator.scheduler.waiting() == asked


def test_closed_with_runs_waiting_a_server_finds_them_again_and_runs_each_once_within_its_limit(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as first:
        first.runs = objects
        first.scheduler = Scheduler(first, tmp_path, limit=1)
        computing = first.scheduler.start(workers_support.LONG)
        waiting = [first.scheduler.start(SHORT, seed=seed) for seed in (1, 2)]
        whole = queued(first, FolderStore(tmp_path / "whole"), SHORT, seed=1)
        assert execute(first, whole, Free()) == Status.FINISHED
    kept = [EpochStore(objects, shown.run_id, shown.epoch) for shown in waiting]
    told = EpochStore(objects, computing.run_id, computing.epoch).manifest().status
    assert told == Status.INTERRUPTED
    assert {epoch.manifest().status for epoch in kept} == {Status.QUEUED}

    most = 0
    # A simulator that knows the scenario only from the store.
    with Simulator(runs=objects, workers=1) as second:
        made = second.scheduler
        assert made is not None
        assert made.waiting() == [_key(kept[1])]

        def all_ended() -> bool:
            nonlocal most
            statuses = [epoch.manifest().status for epoch in kept]
            most = max(most, statuses.count(Status.RUNNING), len(made.workers()))
            return statuses == [Status.FINISHED, Status.FINISHED]

        _until(all_ended, "both runs to end")
        _until(lambda: not made.workers(), "the workers to be let go")

    assert most == 1
    assert [c.digest for c in kept[0].commits()] == [c.digest for c in whole.commits()]
    for epoch in kept:
        assert len(epoch.commits()) == workers_support.SHORT_DAYS
        epoch.verify()
        # One worker claimed it, and let go: no one else ever had it.
        assert leases.newest(objects, f"{epoch.run_id}/{epoch.epoch}") == 1


def test_two_servers_finding_one_queue_work_each_run_once(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])
    with workers_support.short_simulator() as made:
        whole = queued(made, FolderStore(tmp_path / "whole"), SHORT, seed=1)
        assert execute(made, whole, Free()) == Status.FINISHED

    with Simulator(runs=objects) as one, Simulator(runs=objects) as other:
        _until(lambda: left.manifest().status == Status.FINISHED, "the run to end")
        servers = [server.scheduler for server in (one, other)]
        _until(lambda: not any(s is not None and s.workers() for s in servers), "both to end")
        # The one that lost said nothing of the run.
        assert left.manifest().status == Status.FINISHED

    assert [c.digest for c in left.commits()] == [c.digest for c in whole.commits()]
    left.verify()


@pytest.mark.parametrize("status", [Status.QUEUED, Status.RUNNING])
@pytest.mark.usefixtures("workers_end_at_once")
def test_a_run_whose_worker_is_alive_is_left_to_it_and_counted_against_the_limit(
    tmp_path: Path, status: Status
) -> None:
    objects = FolderStore(tmp_path)
    worked, behind = _in_line(objects, [1, 2])
    assert worked.claim()
    if status == Status.RUNNING:
        worked.set_status(status)

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        assert made.waiting() == [_key(behind)]
        assert made.workers() == []
        threading.Event().wait(5 * scheduler.LOOK_EVERY_S)
        assert behind.manifest().status == Status.QUEUED
        assert worked.manifest().status == status

        worked.set_status(Status.FINISHED)

        _until(lambda: behind.manifest().status == Status.FAILED, "the next run's worker")


@pytest.mark.usefixtures("workers_end_at_once")
def test_a_worker_gone_since_the_restart_is_told_interrupted_and_leaves_room(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    worked, behind = _in_line(objects, [1, 2])
    _rewritten(worked, created_at=IN_LINE_AT)
    # A worker's claim, which nothing here writes again.
    assert leases.claim(objects, f"{worked.run_id}/{worked.epoch}") == 0

    with Simulator(runs=objects, workers=1):
        assert behind.manifest().status == Status.QUEUED

        _expired(worked)

        _until(lambda: worked.manifest().status == Status.INTERRUPTED, "the epoch to be told")
        _until(lambda: behind.manifest().status == Status.FAILED, "the next run's worker")


def test_a_worker_that_found_its_run_anothers_counts_that_run_until_it_is_told(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whoever won is watched by no one else, and may die: this server looks."""
    monkeypatch.setattr(scheduler, "work", claims_support.leaves_to_another)
    objects = FolderStore(tmp_path)
    left, behind = _in_line(objects, [1, 2])
    _rewritten(left, created_at=IN_LINE_AT)

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        _until(lambda: left.worked() and not made.workers(), "the worker to leave")
        threading.Event().wait(5 * scheduler.LOOK_EVERY_S)
        assert made.waiting() == [_key(behind)]

        _expired(left)

        _until(lambda: left.manifest().status == Status.INTERRUPTED, "the epoch to be told")
        _until(lambda: not made.waiting(), "the next run's worker")


def test_a_run_another_server_started_while_it_waited_here_counts_until_it_is_told(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "work", workers_support.ends_at_once)
    objects = FolderStore(tmp_path)
    holding, started, behind = _in_line(objects, [1, 2, 3])
    assert holding.claim()

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        assert made.waiting() == [_key(started), _key(behind)]
        # Another server's worker takes it, and will write nothing more.
        assert leases.claim(objects, f"{started.run_id}/{started.epoch}") == 0
        _rewritten(started, status=Status.RUNNING)

        holding.set_status(Status.FINISHED)

        _until(lambda: _key(started) not in made.waiting(), "its turn to come here")
        threading.Event().wait(5 * scheduler.LOOK_EVERY_S)
        assert made.waiting() == [_key(behind)] and made.workers() == []

        _expired(started)

        _until(lambda: started.manifest().status == Status.INTERRUPTED, "it to be told")
        _until(lambda: behind.manifest().status == Status.FAILED, "the next run's worker")


def test_a_server_killed_leaves_a_worker_computing_which_the_next_counts_and_a_run_waiting(
    tmp_path: Path,
) -> None:
    """Nothing faked but a claim's age once its worker is killed: the server and the
    worker are processes, and only the store is between them and the next server."""
    told = SPAWN.Queue()
    server = SPAWN.Process(target=claims_support.a_server, args=(str(tmp_path), told, PACE))
    server.start()
    objects = FolderStore(tmp_path)
    computing = EpochStore(objects, *told.get(timeout=WAIT_S))
    waiting = EpochStore(objects, *told.get(timeout=WAIT_S))
    _, worker = told.get(timeout=WAIT_S)
    os.kill(server.pid or 0, signal.SIGKILL)
    server.join(WAIT_S)
    try:
        before = computing.frontier_s()
        _until(lambda: computing.frontier_s() > before, "its worker to go on with no server")

        with Simulator(runs=objects, workers=1) as second:
            made = second.scheduler
            assert made is not None
            # Its one worker is the one that was left.
            assert made.waiting() == [_key(waiting)] and made.workers() == []
            assert waiting.manifest().status == Status.QUEUED
            assert computing.manifest().status == Status.RUNNING
            assert computing.worked()

            os.kill(worker, signal.SIGKILL)
            _expired(computing)

            _until(lambda: computing.manifest().status == Status.INTERRUPTED, "it to be told")
            _until(lambda: waiting.manifest().status == Status.FINISHED, "the run waiting to end")
            waiting.verify()
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(worker, signal.SIGKILL)


def test_an_epoch_from_before_epochs_were_put_in_line_is_told_interrupted(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    objects.put(
        "run/0/manifest.json",
        json.dumps(
            {
                "run_id": "run",
                "epoch": 0,
                "scenario_id": "s",
                "layout": "default",
                "status": "queued",
            }
        ).encode(),
    )

    with Simulator(runs=objects) as simulator:
        assert simulator.scheduler is None
        assert EpochStore(objects, "run", 0).manifest().status == Status.INTERRUPTED


def test_an_epoch_a_process_of_its_own_was_to_work_is_not_taken_by_a_scheduler(
    tmp_path: Path,
) -> None:
    """Started with no scheduler, as an experiment that steps it does."""
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        own = queued(made, objects, SHORT)

    with Simulator(runs=objects) as simulator:
        assert simulator.scheduler is None
        assert own.manifest().status == Status.QUEUED


def test_an_epoch_deleted_while_it_waits_is_passed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(scheduler, "work", claims_support.says_it_was_given)
    objects = FolderStore(tmp_path)
    worked, deleted, behind = _in_line(objects, [1, 2, 3])
    assert worked.claim()

    with caplog.at_level(logging.ERROR), Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        assert made.waiting() == [_key(deleted), _key(behind)]
        # By another process: no route here deletes an epoch that waits.
        delete_epoch(objects, deleted.run_id, deleted.epoch)

        worked.set_status(Status.FINISHED)

        _until(lambda: behind.manifest().status == Status.FAILED, "the run behind it")
        assert made.waiting() == []

    assert objects.names("given/") == [f"given/{behind.run_id}-{behind.epoch}"]
    assert "could not look" not in caplog.text


def test_an_epoch_deleted_under_its_worker_is_told_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(scheduler, "work", claims_support.deletes_its_epoch)
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])

    with caplog.at_level(logging.ERROR), Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        _until(lambda: not made.workers() and not made.waiting(), "the worker to be let go")

    assert caplog.text == ""
    assert objects.get(f"{left.run_id}/{left.epoch}/manifest.json") is None


@pytest.mark.usefixtures("no_worker_starts")
def test_an_epoch_that_waits_is_not_deleted_after_a_restart_either(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])

    with Simulator(runs=objects) as simulator:
        deleted = respond(simulator, "POST", f"/api/runs/{left.run_id}/epochs/{left.epoch}/delete")
        assert deleted.status == HTTPStatus.CONFLICT
        assert simulator.scheduler is not None
        assert simulator.scheduler.waiting() == [_key(left)]


@pytest.mark.usefixtures("no_worker_starts")
def test_a_run_waiting_keeps_its_pace_and_its_scenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1], pace=PACE)
    given: list[Any] = []

    def carries_on(simulator: Simulator, kept: EpochStore, driver: Any) -> Status:
        given.append((driver, simulator.catalogue.entry(SHORT) is not None, kept.claimed()))
        kept.let_go()
        return Status.FINISHED

    monkeypatch.setattr(scheduler, "carry_on", carries_on)

    with Simulator(runs=objects) as simulator:
        assert simulator.catalogue.entry(SHORT) is not None
        with pytest.raises(SystemExit):
            scheduler.work(str(tmp_path), left.run_id, left.epoch)

    assert given == [(Paced(PACE), True, True)]


@pytest.mark.parametrize(
    ("lost", "words"),
    [("its file", "gone from the store"), ("its name", "upload the scenario's file")],
)
@pytest.mark.usefixtures("no_worker_starts")
def test_a_run_waiting_that_this_simulator_cannot_run_is_told_interrupted_and_says_why(
    tmp_path: Path, lost: str, words: str
) -> None:
    objects = FolderStore(tmp_path)
    (cannot,) = _in_line(objects, [1])
    with Simulator() as made:
        behind = queued(made, objects, PACKAGED, queued_at=IN_LINE_AT + timedelta(days=1))
    if lost == "its file":
        for name in objects.names(scenario_files.KEPT_FOLDER):
            objects.delete(name)
    else:
        _rewritten(cannot, scenario_id="no_such_scenario", scenario_file=None)

    with Simulator(runs=objects) as simulator:
        made_again = simulator.scheduler
        assert made_again is not None
        assert made_again.waiting() == [_key(behind)]
        assert cannot.manifest().status == Status.INTERRUPTED
        with pytest.raises(Conflict, match=words):
            made_again.resume(cannot.run_id, cannot.epoch)


@pytest.mark.parametrize("kind", ["new", "carried on", "carried on with nothing kept", "fork"])
@pytest.mark.usefixtures("workers_end_at_once")
def test_a_worker_that_ends_before_taking_up_a_run_found_again_says_what_it_says_otherwise(
    tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run asked for fails; one with days kept, or a fork, stays to be asked again."""
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made, monkeypatch.context() as stopped:
        stopped.setattr(Scheduler, "_launch", lambda _self: None)
        made.runs = objects
        scheduling = Scheduler(made, tmp_path, limit=1)
        if kind == "new":
            shown = scheduling.start(SHORT)
            left = EpochStore(objects, shown.run_id, shown.epoch)
        else:
            left = queued(made, objects, SHORT)
            kept = [] if kind == "carried on with nothing kept" else [DAY_S]
            assert execute(made, left, Stepped(kept)) == Status.INTERRUPTED
            if kind == "fork":
                shown = scheduling.fork(left.run_id, left.epoch, DAY_S)
                left = EpochStore(objects, shown.run_id, shown.epoch)
            else:
                scheduling.resume(left.run_id, left.epoch)
        scheduling.close()

    with Simulator(runs=objects, workers=1):
        _until(lambda: left.manifest().status != Status.QUEUED, "the epoch to be told")

    assert left.manifest().status == (Status.FAILED if kind == "new" else Status.INTERRUPTED)


@pytest.mark.parametrize("status", [Status.QUEUED, Status.RUNNING])
@pytest.mark.usefixtures("no_worker_starts")
def test_a_stop_of_a_run_waiting_here_that_another_server_took_up_asks_its_worker(
    tmp_path: Path, status: Status
) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        assert made.waiting() == [_key(left)]
        # Another server's worker, between this server's restoring it and this stop.
        worker = EpochStore(objects, left.run_id, left.epoch)
        assert worker.claim()
        if status == Status.RUNNING:
            worker.set_status(status)

        shown = made.cancel(left.run_id, left.epoch)

        assert (shown.status, shown.stopping) == (status, True)
        assert worker.claimed() and left.stop_asked()
        assert made.waiting() == []
        worker.set_status(Status.INTERRUPTED)


@pytest.mark.usefixtures("no_worker_starts")
def test_a_stop_of_a_run_waiting_here_that_ended_elsewhere_changes_nothing(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        _rewritten(left, status=Status.FINISHED)

        with pytest.raises(Conflict, match="not being computed"):
            made.cancel(left.run_id, left.epoch)

        assert left.manifest().status == Status.FINISHED
        assert made.waiting() == []


@pytest.mark.usefixtures("no_worker_starts")
def test_a_stop_of_a_run_waiting_here_that_was_deleted_is_not_found(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        delete_epoch(objects, left.run_id, left.epoch)

        with pytest.raises(NotFound):
            made.cancel(left.run_id, left.epoch)

        assert made.waiting() == []


def test_a_run_whose_worker_is_alive_is_asked_through_the_store_to_stop(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (worked,) = _in_line(objects, [1])
    assert worked.claim()

    with Simulator(runs=objects, workers=1) as simulator:
        path = f"/api/runs/{worked.run_id}/epochs/{worked.epoch}/stop"
        stopped = respond(simulator, "POST", path)

        assert stopped.status == HTTPStatus.OK
        assert worked.stop_asked()
        assert worked.manifest().status == Status.QUEUED
        worked.set_status(Status.INTERRUPTED)


def test_a_run_found_waiting_with_a_stop_asked_ends_at_its_workers_first_look(
    tmp_path: Path,
) -> None:
    """Asked of it while no server had it: the request is in the store, as the run is."""
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])
    left.ask_to_stop()

    with Simulator(runs=objects, workers=1) as simulator:
        made = simulator.scheduler
        assert made is not None
        _until(lambda: left.manifest().status == Status.INTERRUPTED, "its worker to look")
        _until(lambda: not made.workers(), "the worker to be let go")

    assert left.commits() == []
    assert not left.worked()


@pytest.mark.usefixtures("no_worker_starts")
def test_a_run_found_again_can_be_stopped_while_it_waits(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])

    with Simulator(runs=objects) as simulator:
        stopped = respond(simulator, "POST", f"/api/runs/{left.run_id}/epochs/{left.epoch}/stop")
        assert stopped.status == HTTPStatus.OK
        assert simulator.scheduler is not None
        assert simulator.scheduler.waiting() == []

    assert left.manifest().status == Status.INTERRUPTED


class _NotAFolder:
    """A store of another kind than a folder, for which there are no workers yet."""

    def __init__(self, root: Path) -> None:
        self._folder = FolderStore(root)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._folder, name)


def test_on_a_store_that_is_not_a_folder_a_run_waiting_is_told_interrupted(tmp_path: Path) -> None:
    objects = FolderStore(tmp_path)
    (left,) = _in_line(objects, [1])
    _rewritten(left, created_at=IN_LINE_AT)

    with Simulator(runs=_NotAFolder(tmp_path)) as simulator:
        assert simulator.scheduler is None

    assert left.manifest().status == Status.INTERRUPTED
