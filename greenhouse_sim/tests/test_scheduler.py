"""Workers in processes of their own, and the scheduler that runs them (P17.7,
decision 0065): runs asked for are epochs in the store, executed up to a limit
and queued beyond it, several of one scenario at once, read while they are
computed, and left interrupted where they were committed if their worker dies."""

import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Iterator
from http import HTTPStatus
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Final

import pytest

from greenhouse_sim.api.routes import respond
from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.services import runs_kept, scheduler
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound
from greenhouse_sim.services.run_store import (
    EpochStore,
    FolderStore,
    ObjectStore,
    Status,
    StoredRun,
)
from greenhouse_sim.services.scheduler import Scheduler
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.services.workers import Free, Stepped, execute, queued

# A worker starts from nothing and imports what it is told to build its
# simulator with by name, so that the module is put where its process finds it.
sys.path.insert(0, str(Path(__file__).parent))

import workers_support

SHORT: Final = workers_support.SHORT
LONG: Final = workers_support.LONG
WAIT_S: Final = 240.0


def _until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while not condition():
        assert time.monotonic() < deadline, f"waited for {what}"
        threading.Event().wait(0.05)


def _status(objects: ObjectStore, shown: StoredRun) -> Status:
    return EpochStore(objects, shown.run_id, shown.epoch).manifest().status


def _frontier(objects: ObjectStore, shown: StoredRun) -> float:
    return EpochStore(objects, shown.run_id, shown.epoch).frontier_s()


@pytest.fixture
def simulator(tmp_path: Path) -> Iterator[Simulator]:
    """A simulator whose workers may run two epochs at once, and whose run store
    is a folder."""
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as made:
        made.runs = objects
        made.scheduler = Scheduler(made, tmp_path, limit=2)
        yield made


def _scheduler(simulator: Simulator) -> Scheduler:
    return scheduler.of(simulator)


@pytest.fixture
def objects(simulator: Simulator) -> FolderStore:
    assert isinstance(simulator.runs, FolderStore)
    return simulator.runs


def test_a_run_asked_for_is_executed_by_a_process_and_is_the_epoch_a_free_run_writes(
    simulator: Simulator, objects: FolderStore
) -> None:
    shown = _scheduler(simulator).start(SHORT, seed=3)
    assert shown.status in (Status.QUEUED, Status.RUNNING) and shown.seed == 3
    (worker,) = _scheduler(simulator).workers()
    assert worker.pid not in (0, os.getpid())

    _until(lambda: _status(objects, shown) == Status.FINISHED, "the epoch to finish")

    made = EpochStore(objects, shown.run_id, shown.epoch)
    made.verify()
    # The records are those the same epoch has when it is executed here.
    here = queued(simulator, objects, SHORT, seed=3)
    assert execute(simulator, here, Free()) == Status.FINISHED
    assert [o.model_dump_json() for o in made.observations().records] == [
        o.model_dump_json() for o in here.observations().records
    ]
    assert made.checkpoint_at(2 * DAY_S) == here.checkpoint_at(2 * DAY_S)
    _until(lambda: _scheduler(simulator).workers() == [], "the worker to be let go")


def test_several_runs_of_one_scenario_are_executed_at_once_in_processes_of_their_own(
    simulator: Simulator, objects: FolderStore
) -> None:
    scheduling = _scheduler(simulator)
    first, second = scheduling.start(LONG, seed=1), scheduling.start(LONG, seed=2)

    _until(
        lambda: all(_frontier(objects, s) >= DAY_S for s in (first, second)),
        "both epochs to be committed a day on",
    )

    assert len({w.pid for w in scheduling.workers()}) == 2
    assert {_status(objects, s) for s in (first, second)} == {Status.RUNNING}
    assert first.run_id != second.run_id
    scheduling.cancel(first.run_id, first.epoch)
    scheduling.cancel(second.run_id, second.epoch)


def test_runs_beyond_the_limit_wait_for_a_worker_in_the_order_they_were_asked_for(
    simulator: Simulator, objects: FolderStore
) -> None:
    scheduling = Scheduler(simulator, objects.root, limit=1)
    try:
        first, second, third = (scheduling.start(LONG, seed=s) for s in (1, 2, 3))
        assert scheduling.waiting() == [(second.run_id, 0), (third.run_id, 0)]
        assert _status(objects, second) == Status.QUEUED

        scheduling.cancel(first.run_id, first.epoch)

        assert _status(objects, first) == Status.INTERRUPTED
        _until(
            lambda: _status(objects, second) == Status.RUNNING,
            "the next run to be given the worker",
        )
        assert scheduling.waiting() == [(third.run_id, 0)]
        assert _status(objects, third) == Status.QUEUED
        scheduling.cancel(third.run_id, third.epoch)
        assert _status(objects, third) == Status.INTERRUPTED
        assert _frontier(objects, third) == 0.0
    finally:
        scheduling.close()


def test_a_killed_worker_leaves_its_epoch_interrupted_where_it_was_committed(
    simulator: Simulator, objects: FolderStore
) -> None:
    scheduling = Scheduler(simulator, objects.root, limit=1)
    try:
        killed, next_ = scheduling.start(LONG, seed=1), scheduling.start(LONG, seed=2)
        _until(lambda: _frontier(objects, killed) >= DAY_S, "a day to be committed")

        (worker,) = scheduling.workers()
        os.kill(worker.pid, signal.SIGKILL)

        _until(lambda: _status(objects, killed) == Status.INTERRUPTED, "the epoch to be told")
        kept = EpochStore(objects, killed.run_id, killed.epoch)
        assert DAY_S <= kept.frontier_s() < workers_support.LONG_DAYS * DAY_S
        # What was committed is whole, and is what a reader is given.
        kept.verify()
        assert kept.observations().records
        # The worker it left is given to the run waiting.
        _until(lambda: _status(objects, next_) == Status.RUNNING, "the next run to begin")
    finally:
        scheduling.close()


def test_a_run_is_followed_while_it_is_computed(simulator: Simulator, objects: FolderStore) -> None:
    shown = _scheduler(simulator).start(LONG)
    _until(lambda: _frontier(objects, shown) >= DAY_S, "a day to be committed")

    opened = runs_kept.open_position(simulator, shown.run_id, shown.epoch, 1.0)
    seen = runs_kept.follow(simulator, opened.position_id)
    assert seen.status == Status.RUNNING and seen.frontier_s >= DAY_S
    assert seen.time_s <= seen.frontier_s
    # Played over what is computed, it reads what is committed.
    assert runs_kept.position_observations(simulator, opened.position_id, None, None).observations

    _until(
        lambda: runs_kept.position(simulator, opened.position_id).frontier_s > seen.frontier_s,
        "the epoch to go on",
    )
    later = runs_kept.position(simulator, opened.position_id)
    assert later.following and later.time_s >= seen.time_s
    # A moment past what is computed is refused.
    with pytest.raises(InvalidRequest):
        runs_kept.seek(simulator, opened.position_id, workers_support.LONG_DAYS * DAY_S)
    _scheduler(simulator).cancel(shown.run_id, shown.epoch)


def test_closing_the_simulator_ends_its_workers_and_leaves_what_waits_waiting(
    tmp_path: Path,
) -> None:
    objects = FolderStore(tmp_path)
    with workers_support.short_simulator() as simulator:
        simulator.runs = objects
        scheduling = Scheduler(simulator, tmp_path, limit=1)
        simulator.scheduler = scheduling
        running, waiting = scheduling.start(LONG), scheduling.start(LONG, seed=9)
        _until(lambda: _frontier(objects, running) >= DAY_S, "a day to be committed")
        (worker,) = scheduling.workers()

    assert scheduling.workers() == [] and scheduling.waiting() == []
    assert _status(objects, running) == Status.INTERRUPTED
    assert _status(objects, waiting) == Status.QUEUED
    with pytest.raises(ProcessLookupError):
        os.kill(worker.pid, 0)
    with pytest.raises(Conflict):
        scheduling.start(SHORT)


def test_a_worker_that_cannot_begin_leaves_its_epoch_failed(
    simulator: Simulator, objects: FolderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduler, "work", workers_support.ends_at_once)
    broken = Scheduler(simulator, objects.root, limit=1)
    try:
        shown = broken.start(SHORT)
        _until(lambda: _status(objects, shown) == Status.FAILED, "the epoch to be told")
    finally:
        broken.close()


def test_a_run_is_asked_for_over_the_api_and_stopped_there(
    simulator: Simulator, objects: FolderStore
) -> None:
    asked = respond(simulator, "POST", f"/api/scenarios/{LONG}/runs?seed=4&layout=default")
    assert asked.status == HTTPStatus.OK and isinstance(asked.body, dict)
    shown = StoredRun.model_validate(asked.body)
    assert shown.seed == 4 and shown.scenario_id == LONG
    listed = respond(simulator, "GET", f"/api/scenarios/{LONG}/runs").body
    assert isinstance(listed, list)
    assert [StoredRun.model_validate(item).run_id for item in listed] == [shown.run_id]

    stopped = respond(simulator, "POST", f"/api/runs/{shown.run_id}/epochs/{shown.epoch}/stop")
    assert stopped.status == HTTPStatus.OK
    assert _status(objects, shown) == Status.INTERRUPTED
    # A worker of its own is gone by the answer, with nothing asked through the store.
    assert not EpochStore(objects, shown.run_id, shown.epoch).stop_asked()
    again = respond(simulator, "POST", f"/api/runs/{shown.run_id}/epochs/{shown.epoch}/stop")
    assert again.status == HTTPStatus.CONFLICT


def test_a_run_is_asked_for_over_the_api_under_a_weather_for_fewer_days(
    simulator: Simulator, objects: FolderStore
) -> None:
    """Decision 0075: the list and a position over it say both, and the same
    asked again, at its seed, is the same run."""
    path = f"/api/scenarios/{SHORT}/runs?seed=4&weather=cold_spring_day&duration_days=1"
    asked = respond(simulator, "POST", path)
    assert asked.status == HTTPStatus.OK and isinstance(asked.body, dict)
    shown = StoredRun.model_validate(asked.body)
    assert (shown.weather, shown.duration_s, shown.seed) == ("cold_spring_day", DAY_S, 4)
    _until(lambda: _status(objects, shown) == Status.FINISHED, "the epoch to finish")
    assert _frontier(objects, shown) == DAY_S

    opened = respond(simulator, "POST", f"/api/runs/{shown.run_id}/epochs/0/positions")
    assert isinstance(opened.body, dict)
    assert (opened.body["weather"], opened.body["duration_s"]) == ("cold_spring_day", DAY_S)
    again = StoredRun.model_validate(respond(simulator, "POST", path).body)
    assert (again.run_id, again.epoch) == (shown.run_id, 1)
    own = StoredRun.model_validate(respond(simulator, "POST", f"/api/scenarios/{SHORT}/runs").body)
    assert own.run_id != shown.run_id and own.weather is None
    assert own.duration_s == workers_support.SHORT_DAYS * DAY_S


@pytest.mark.parametrize(
    ("path", "status"),
    [
        (f"/api/scenarios/{SHORT}/runs?seed=x", HTTPStatus.BAD_REQUEST),
        (f"/api/scenarios/{SHORT}/runs?weather=no_such_weather", HTTPStatus.NOT_FOUND),
        (f"/api/scenarios/{SHORT}/runs?weather=default%237", HTTPStatus.BAD_REQUEST),
        (f"/api/scenarios/{SHORT}/runs?duration_days=x", HTTPStatus.BAD_REQUEST),
        (f"/api/scenarios/{SHORT}/runs?duration_days=0", HTTPStatus.BAD_REQUEST),
        (f"/api/scenarios/{SHORT}/runs?duration_days=3", HTTPStatus.BAD_REQUEST),
        (f"/api/scenarios/{SHORT}/runs?seconds_per_day=0", HTTPStatus.BAD_REQUEST),
        (f"/api/scenarios/{SHORT}/runs?layout=no_such_layout", HTTPStatus.NOT_FOUND),
        ("/api/scenarios/no_such_scenario/runs", HTTPStatus.NOT_FOUND),
    ],
)
def test_a_run_asked_for_wrongly_starts_nothing(
    simulator: Simulator, objects: FolderStore, path: str, status: HTTPStatus
) -> None:
    assert respond(simulator, "POST", path).status == status
    assert objects.children() == []
    assert _scheduler(simulator).workers() == []


def test_workers_need_a_run_store_in_a_folder() -> None:
    with Simulator() as keeps_none, pytest.raises(NotFound):
        scheduler.start(keeps_none, SHORT)
    with Simulator(runs=_Elsewhere()) as elsewhere, pytest.raises(Conflict):
        scheduler.start(elsewhere, SHORT)


def test_a_worker_does_not_take_a_stepped_driver(simulator: Simulator) -> None:
    with pytest.raises(InvalidRequest):
        _scheduler(simulator).start(SHORT, driver=Stepped([DAY_S]))


class _Elsewhere:
    """A run store that is not a folder."""

    def __init__(self) -> None:
        self._held: dict[str, bytes] = {}

    def put(self, name: str, data: bytes) -> None:
        self._held[name] = data

    def create(self, name: str, data: bytes) -> bool:
        return self._held.setdefault(name, data) is data

    def get(self, name: str) -> bytes | None:
        return self._held.get(name)

    def names(self, prefix: str = "") -> list[str]:
        return sorted(n for n in self._held if n.startswith(prefix))

    def children(self, prefix: str = "") -> list[str]:
        return []

    def size(self, name: str) -> int | None:
        return len(self._held[name]) if name in self._held else None

    def delete(self, name: str) -> None:
        self._held.pop(name, None)

    def free_bytes(self) -> int | None:
        return None


def test_no_scheduler_is_made_after_the_simulator_is_closed(tmp_path: Path) -> None:
    """A simulator closed before its first run asked for would otherwise make a
    scheduler no close will end."""
    objects = FolderStore(tmp_path)
    simulator = workers_support.short_simulator()
    simulator.runs = objects
    simulator.close()

    with pytest.raises(Conflict):
        scheduler.start(simulator, SHORT)

    assert simulator.scheduler is None
    assert objects.children() == []


def _refusing_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The next process to start is refused, as the machine's limit would."""
    real = SpawnProcess.start
    refusals = [True]

    def starting(self: SpawnProcess) -> None:
        if refusals:
            refusals.pop()
            raise OSError("too many processes")
        real(self)

    monkeypatch.setattr(SpawnProcess, "start", starting)


def test_a_worker_that_cannot_be_started_leaves_its_epoch_failed_and_the_queue_going(
    simulator: Simulator, objects: FolderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The epoch is told, nothing is left of it in the scheduler, and the next
    run asked for is given a worker."""
    _refusing_once(monkeypatch)
    scheduling = Scheduler(simulator, objects.root, limit=1)
    try:
        refused = scheduling.start(SHORT, seed=1)
        assert _status(objects, refused) == Status.FAILED
        assert scheduling.workers() == [] and scheduling.waiting() == []

        followed = scheduling.start(SHORT, seed=2)
        _until(lambda: _status(objects, followed) == Status.FINISHED, "the next run to finish")
    finally:
        scheduling.close()


def test_a_worker_that_cannot_be_started_by_the_watcher_does_not_end_it(
    simulator: Simulator, objects: FolderStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    scheduling = Scheduler(simulator, objects.root, limit=1)
    try:
        running = scheduling.start(LONG, seed=1)
        waiting, behind = scheduling.start(SHORT, seed=2), scheduling.start(SHORT, seed=3)
        _refusing_once(monkeypatch)
        scheduling.cancel(running.run_id, running.epoch)

        _until(lambda: _status(objects, waiting) == Status.FAILED, "the refused run to be told")
        _until(lambda: _status(objects, behind) == Status.FINISHED, "the run behind it to finish")
    finally:
        scheduling.close()
